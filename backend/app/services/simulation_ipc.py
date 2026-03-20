"""
SimulareIPC通信Modul
用于Flask后端șiSimulare脚本之间进程间通信

通过FișierSistem实现Simplu命令/Răspuns模式：
1. Flask写入命令la commands/ Director
2. Simulare脚本轮询命令Director，执行命令并写入Răspunsla responses/ Director
3. Flask轮询RăspunsDirectorObținereRezultat
"""

import os
import json
import time
import uuid
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from ..utils.logger import get_logger

logger = get_logger('mirofish.simulation_ipc')


class CommandType(str, Enum):
    """命令Tip"""
    INTERVIEW = "interview"           # IndividualAgentInterviu
    BATCH_INTERVIEW = "batch_interview"  # În lotInterviu
    CLOSE_ENV = "close_env"           # ÎnchidereMediu


class CommandStatus(str, Enum):
    """命令Stare"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class IPCCommand:
    """IPC命令"""
    command_id: str
    command_type: CommandType
    args: Dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "command_id": self.command_id,
            "command_type": self.command_type.value,
            "args": self.args,
            "timestamp": self.timestamp
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'IPCCommand':
        return cls(
            command_id=data["command_id"],
            command_type=CommandType(data["command_type"]),
            args=data.get("args", {}),
            timestamp=data.get("timestamp", datetime.now().isoformat())
        )


@dataclass
class IPCResponse:
    """IPCRăspuns"""
    command_id: str
    status: CommandStatus
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "command_id": self.command_id,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "timestamp": self.timestamp
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'IPCResponse':
        return cls(
            command_id=data["command_id"],
            status=CommandStatus(data["status"]),
            result=data.get("result"),
            error=data.get("error"),
            timestamp=data.get("timestamp", datetime.now().isoformat())
        )


class SimulationIPCClient:
    """
    SimulareIPC客户端（Flask端使用）
    
    用于cătreSimulare进程发送命令并等待Răspuns
    """
    
    def __init__(self, simulation_dir: str):
        """
        InițializareIPC客户端
        
        Args:
            simulation_dir: SimulareDateDirector
        """
        self.simulation_dir = simulation_dir
        self.commands_dir = os.path.join(simulation_dir, "ipc_commands")
        self.responses_dir = os.path.join(simulation_dir, "ipc_responses")
        
        # 确保Director存în
        os.makedirs(self.commands_dir, exist_ok=True)
        os.makedirs(self.responses_dir, exist_ok=True)
    
    def send_command(
        self,
        command_type: CommandType,
        args: Dict[str, Any],
        timeout: float = 60.0,
        poll_interval: float = 0.5
    ) -> IPCResponse:
        """
        发送命令并等待Răspuns
        
        Args:
            command_type: 命令Tip
            args: 命令Parametru
            timeout: 超时Timp（秒）
            poll_interval: 轮询间隔（秒）
            
        Returns:
            IPCResponse
            
        Raises:
            TimeoutError: 等待Răspuns超时
        """
        command_id = str(uuid.uuid4())
        command = IPCCommand(
            command_id=command_id,
            command_type=command_type,
            args=args
        )
        
        # 写入命令Fișier
        command_file = os.path.join(self.commands_dir, f"{command_id}.json")
        with open(command_file, 'w', encoding='utf-8') as f:
            json.dump(command.to_dict(), f, ensure_ascii=False, indent=2)
        
        logger.info(f"发送IPC命令: {command_type.value}, command_id={command_id}")
        
        # 等待Răspuns
        response_file = os.path.join(self.responses_dir, f"{command_id}.json")
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if os.path.exists(response_file):
                try:
                    with open(response_file, 'r', encoding='utf-8') as f:
                        response_data = json.load(f)
                    response = IPCResponse.from_dict(response_data)
                    
                    # 清理命令șiRăspunsFișier
                    try:
                        os.remove(command_file)
                        os.remove(response_file)
                    except OSError:
                        pass
                    
                    logger.info(f"收laIPCRăspuns: command_id={command_id}, status={response.status.value}")
                    return response
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning(f"解析RăspunsEșec: {e}")
            
            time.sleep(poll_interval)
        
        # 超时
        logger.error(f"等待IPCRăspuns超时: command_id={command_id}")
        
        # 清理命令Fișier
        try:
            os.remove(command_file)
        except OSError:
            pass
        
        raise TimeoutError(f"等待命令Răspuns超时 ({timeout}秒)")
    
    def send_interview(
        self,
        agent_id: int,
        prompt: str,
        platform: str = None,
        timeout: float = 60.0
    ) -> IPCResponse:
        """
        发送IndividualAgentInterviu命令
        
        Args:
            agent_id: Agent ID
            prompt: Interviu问题
            platform: 指定Platformă（可选）
                - "twitter": 只InterviuTwitterPlatformă
                - "reddit": 只InterviuRedditPlatformă  
                - None: 双PlatformăSimulare时同时Interviu两个Platformă，单PlatformăSimulare时Interviu该Platformă
            timeout: 超时Timp
            
        Returns:
            IPCResponse，result字段包含InterviuRezultat
        """
        args = {
            "agent_id": agent_id,
            "prompt": prompt
        }
        if platform:
            args["platform"] = platform
            
        return self.send_command(
            command_type=CommandType.INTERVIEW,
            args=args,
            timeout=timeout
        )
    
    def send_batch_interview(
        self,
        interviews: List[Dict[str, Any]],
        platform: str = None,
        timeout: float = 120.0
    ) -> IPCResponse:
        """
        发送În lotInterviu命令
        
        Args:
            interviews: InterviuListă，每个元素包含 {"agent_id": int, "prompt": str, "platform": str(可选)}
            platform: ImplicitPlatformă（可选，会被每个Interviu项platform覆盖）
                - "twitter": Implicit只InterviuTwitterPlatformă
                - "reddit": Implicit只InterviuRedditPlatformă
                - None: 双PlatformăSimulare时每个Agent同时Interviu两个Platformă
            timeout: 超时Timp
            
        Returns:
            IPCResponse，result字段包含所有InterviuRezultat
        """
        args = {"interviews": interviews}
        if platform:
            args["platform"] = platform
            
        return self.send_command(
            command_type=CommandType.BATCH_INTERVIEW,
            args=args,
            timeout=timeout
        )
    
    def send_close_env(self, timeout: float = 30.0) -> IPCResponse:
        """
        发送ÎnchidereMediu命令
        
        Args:
            timeout: 超时Timp
            
        Returns:
            IPCResponse
        """
        return self.send_command(
            command_type=CommandType.CLOSE_ENV,
            args={},
            timeout=timeout
        )
    
    def check_env_alive(self) -> bool:
        """
        VerificareSimulareMediuDaNu存活
        
        通过Verificare env_status.json Fișier来判断
        """
        status_file = os.path.join(self.simulation_dir, "env_status.json")
        if not os.path.exists(status_file):
            return False
        
        try:
            with open(status_file, 'r', encoding='utf-8') as f:
                status = json.load(f)
            return status.get("status") == "alive"
        except (json.JSONDecodeError, OSError):
            return False


class SimulationIPCServer:
    """
    SimulareIPCServiciu器（Simulare脚本端使用）
    
    轮询命令Director，执行命令并ReturnareRăspuns
    """
    
    def __init__(self, simulation_dir: str):
        """
        InițializareIPCServiciu器
        
        Args:
            simulation_dir: SimulareDateDirector
        """
        self.simulation_dir = simulation_dir
        self.commands_dir = os.path.join(simulation_dir, "ipc_commands")
        self.responses_dir = os.path.join(simulation_dir, "ipc_responses")
        
        # 确保Director存în
        os.makedirs(self.commands_dir, exist_ok=True)
        os.makedirs(self.responses_dir, exist_ok=True)
        
        # MediuStare
        self._running = False
    
    def start(self):
        """标记Serviciu器为RulareStare"""
        self._running = True
        self._update_env_status("alive")
    
    def stop(self):
        """标记Serviciu器为OprireStare"""
        self._running = False
        self._update_env_status("stopped")
    
    def _update_env_status(self, status: str):
        """ActualizareMediuStareFișier"""
        status_file = os.path.join(self.simulation_dir, "env_status.json")
        with open(status_file, 'w', encoding='utf-8') as f:
            json.dump({
                "status": status,
                "timestamp": datetime.now().isoformat()
            }, f, ensure_ascii=False, indent=2)
    
    def poll_commands(self) -> Optional[IPCCommand]:
        """
        轮询命令Director，Returnare第一个待Procesare命令
        
        Returns:
            IPCCommand sau None
        """
        if not os.path.exists(self.commands_dir):
            return None
        
        # 按Timp排序Obținere命令Fișier
        command_files = []
        for filename in os.listdir(self.commands_dir):
            if filename.endswith('.json'):
                filepath = os.path.join(self.commands_dir, filename)
                command_files.append((filepath, os.path.getmtime(filepath)))
        
        command_files.sort(key=lambda x: x[1])
        
        for filepath, _ in command_files:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return IPCCommand.from_dict(data)
            except (json.JSONDecodeError, KeyError, OSError) as e:
                logger.warning(f"读取命令FișierEșec: {filepath}, {e}")
                continue
        
        return None
    
    def send_response(self, response: IPCResponse):
        """
        发送Răspuns
        
        Args:
            response: IPCRăspuns
        """
        response_file = os.path.join(self.responses_dir, f"{response.command_id}.json")
        with open(response_file, 'w', encoding='utf-8') as f:
            json.dump(response.to_dict(), f, ensure_ascii=False, indent=2)
        
        # Ștergere命令Fișier
        command_file = os.path.join(self.commands_dir, f"{response.command_id}.json")
        try:
            os.remove(command_file)
        except OSError:
            pass
    
    def send_success(self, command_id: str, result: Dict[str, Any]):
        """发送SuccesRăspuns"""
        self.send_response(IPCResponse(
            command_id=command_id,
            status=CommandStatus.COMPLETED,
            result=result
        ))
    
    def send_error(self, command_id: str, error: str):
        """发送EroareRăspuns"""
        self.send_response(IPCResponse(
            command_id=command_id,
            status=CommandStatus.FAILED,
            error=error
        ))
