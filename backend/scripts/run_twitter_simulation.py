"""
OASIS TwitterSimulare预设Script
此Script读取ConfigurareFișierParametru来执行Simulare，实现全程自动化

Funcționalitate特性:
- FinalizareSimulare后不立即ÎnchidereMediu，进入等待命令模式
- Suportă通过IPC接收Interview命令
- Suportă单个Agent采访și批量采访
- Suportă远程ÎnchidereMediu命令

Utilizare方式:
    python run_twitter_simulation.py --config /path/to/simulation_config.json
    python run_twitter_simulation.py --config /path/to/simulation_config.json --no-wait  # Finalizare后立即Închidere
"""

import argparse
import asyncio
import json
import logging
import os
import random
import signal
import sys
import sqlite3
from datetime import datetime
from typing import Dict, Any, List, Optional

# 全局Variabilă：用于信号Procesare
_shutdown_event = None
_cleanup_done = False

# 添加ProiectCale
_scripts_dir = os.path.dirname(os.path.abspath(__file__))
_backend_dir = os.path.abspath(os.path.join(_scripts_dir, '..'))
_project_root = os.path.abspath(os.path.join(_backend_dir, '..'))
sys.path.insert(0, _scripts_dir)
sys.path.insert(0, _backend_dir)

# ÎncărcareProiect根Director .env Fișier（包含 LLM_API_KEY 等Configurare）
from dotenv import load_dotenv
_env_file = os.path.join(_project_root, '.env')
if os.path.exists(_env_file):
    load_dotenv(_env_file)
else:
    _backend_env = os.path.join(_backend_dir, '.env')
    if os.path.exists(_backend_env):
        load_dotenv(_backend_env)


import re


class UnicodeFormatter(logging.Formatter):
    """自定义Format化器，将 Unicode 转义序列转换为可读字符"""
    
    UNICODE_ESCAPE_PATTERN = re.compile(r'\\u([0-9a-fA-F]{4})')
    
    def format(self, record):
        result = super().format(record)
        
        def replace_unicode(match):
            try:
                return chr(int(match.group(1), 16))
            except (ValueError, OverflowError):
                return match.group(0)
        
        return self.UNICODE_ESCAPE_PATTERN.sub(replace_unicode, result)


class MaxTokensWarningFilter(logging.Filter):
    """过滤掉 camel-ai Despre max_tokens Avertisment（我们故意不Setări max_tokens，让Model自行决定）"""
    
    def filter(self, record):
        # 过滤掉包含 max_tokens AvertismentJurnal
        if "max_tokens" in record.getMessage() and "Invalid or missing" in record.getMessage():
            return False
        return True


# înModulÎncărcare时立即添加过滤器，确保în camel 代码执行前生效
logging.getLogger().addFilter(MaxTokensWarningFilter())


def setup_oasis_logging(log_dir: str):
    """Configurare OASIS Jurnal，Utilizare固定NumeJurnalFișier"""
    os.makedirs(log_dir, exist_ok=True)
    
    # 清理旧JurnalFișier
    for f in os.listdir(log_dir):
        old_log = os.path.join(log_dir, f)
        if os.path.isfile(old_log) and f.endswith('.log'):
            try:
                os.remove(old_log)
            except OSError:
                pass
    
    formatter = UnicodeFormatter("%(levelname)s - %(asctime)s - %(name)s - %(message)s")
    
    loggers_config = {
        "social.agent": os.path.join(log_dir, "social.agent.log"),
        "social.twitter": os.path.join(log_dir, "social.twitter.log"),
        "social.rec": os.path.join(log_dir, "social.rec.log"),
        "oasis.env": os.path.join(log_dir, "oasis.env.log"),
        "table": os.path.join(log_dir, "table.log"),
    }
    
    for logger_name, log_file in loggers_config.items():
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.DEBUG)
        logger.handlers.clear()
        file_handler = logging.FileHandler(log_file, encoding='utf-8', mode='w')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        logger.propagate = False


try:
    from camel.models import ModelFactory
    from camel.types import ModelPlatformType
    import oasis
    from oasis import (
        ActionType,
        LLMAction,
        ManualAction,
        generate_twitter_agent_graph
    )
except ImportError as e:
    print(f"Eroare: 缺少依赖 {e}")
    print("请先安装: pip install oasis-ai camel-ai")
    sys.exit(1)


# IPC相关常量
IPC_COMMANDS_DIR = "ipc_commands"
IPC_RESPONSES_DIR = "ipc_responses"
ENV_STATUS_FILE = "env_status.json"

class CommandType:
    """命令Tip常量"""
    INTERVIEW = "interview"
    BATCH_INTERVIEW = "batch_interview"
    CLOSE_ENV = "close_env"


class IPCHandler:
    """IPC命令Procesare器"""
    
    def __init__(self, simulation_dir: str, env, agent_graph):
        self.simulation_dir = simulation_dir
        self.env = env
        self.agent_graph = agent_graph
        self.commands_dir = os.path.join(simulation_dir, IPC_COMMANDS_DIR)
        self.responses_dir = os.path.join(simulation_dir, IPC_RESPONSES_DIR)
        self.status_file = os.path.join(simulation_dir, ENV_STATUS_FILE)
        self._running = True
        
        # 确保Director存în
        os.makedirs(self.commands_dir, exist_ok=True)
        os.makedirs(self.responses_dir, exist_ok=True)
    
    def update_status(self, status: str):
        """ActualizareMediuStare"""
        with open(self.status_file, 'w', encoding='utf-8') as f:
            json.dump({
                "status": status,
                "timestamp": datetime.now().isoformat()
            }, f, ensure_ascii=False, indent=2)
    
    def poll_command(self) -> Optional[Dict[str, Any]]:
        """轮询Obținere待Procesare命令"""
        if not os.path.exists(self.commands_dir):
            return None
        
        # Obținere命令Fișier（按Timp排序）
        command_files = []
        for filename in os.listdir(self.commands_dir):
            if filename.endswith('.json'):
                filepath = os.path.join(self.commands_dir, filename)
                command_files.append((filepath, os.path.getmtime(filepath)))
        
        command_files.sort(key=lambda x: x[1])
        
        for filepath, _ in command_files:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                continue
        
        return None
    
    def send_response(self, command_id: str, status: str, result: Dict = None, error: str = None):
        """TrimiteRăspuns"""
        response = {
            "command_id": command_id,
            "status": status,
            "result": result,
            "error": error,
            "timestamp": datetime.now().isoformat()
        }
        
        response_file = os.path.join(self.responses_dir, f"{command_id}.json")
        with open(response_file, 'w', encoding='utf-8') as f:
            json.dump(response, f, ensure_ascii=False, indent=2)
        
        # Ștergere命令Fișier
        command_file = os.path.join(self.commands_dir, f"{command_id}.json")
        try:
            os.remove(command_file)
        except OSError:
            pass
    
    async def handle_interview(self, command_id: str, agent_id: int, prompt: str) -> bool:
        """
        Procesare单个Agent采访命令
        
        Returns:
            True 表示Succes，False 表示Eșec
        """
        try:
            # ObținereAgent
            agent = self.agent_graph.get_agent(agent_id)
            
            # CreareInterviewAcțiune
            interview_action = ManualAction(
                action_type=ActionType.INTERVIEW,
                action_args={"prompt": prompt}
            )
            
            # 执行Interview
            actions = {agent: interview_action}
            await self.env.step(actions)
            
            # de laDate库ObținereRezultat
            result = self._get_interview_result(agent_id)
            
            self.send_response(command_id, "completed", result=result)
            print(f"  InterviewFinalizare: agent_id={agent_id}")
            return True
            
        except Exception as e:
            error_msg = str(e)
            print(f"  InterviewEșec: agent_id={agent_id}, error={error_msg}")
            self.send_response(command_id, "failed", error=error_msg)
            return False
    
    async def handle_batch_interview(self, command_id: str, interviews: List[Dict]) -> bool:
        """
        Procesare批量采访命令
        
        Args:
            interviews: [{"agent_id": int, "prompt": str}, ...]
        """
        try:
            # ConstruireAcțiuneDicționar
            actions = {}
            agent_prompts = {}  # Înregistrare每个agentprompt
            
            for interview in interviews:
                agent_id = interview.get("agent_id")
                prompt = interview.get("prompt", "")
                
                try:
                    agent = self.agent_graph.get_agent(agent_id)
                    actions[agent] = ManualAction(
                        action_type=ActionType.INTERVIEW,
                        action_args={"prompt": prompt}
                    )
                    agent_prompts[agent_id] = prompt
                except Exception as e:
                    print(f"  Avertisment: 无法ObținereAgent {agent_id}: {e}")
            
            if not actions:
                self.send_response(command_id, "failed", error="没有有效Agent")
                return False
            
            # 执行批量Interview
            await self.env.step(actions)
            
            # Obținere所有Rezultat
            results = {}
            for agent_id in agent_prompts.keys():
                result = self._get_interview_result(agent_id)
                results[agent_id] = result
            
            self.send_response(command_id, "completed", result={
                "interviews_count": len(results),
                "results": results
            })
            print(f"  批量InterviewFinalizare: {len(results)} 个Agent")
            return True
            
        except Exception as e:
            error_msg = str(e)
            print(f"  批量InterviewEșec: {error_msg}")
            self.send_response(command_id, "failed", error=error_msg)
            return False
    
    def _get_interview_result(self, agent_id: int) -> Dict[str, Any]:
        """de laDate库Obținere最新InterviewRezultat"""
        db_path = os.path.join(self.simulation_dir, "twitter_simulation.db")
        
        result = {
            "agent_id": agent_id,
            "response": None,
            "timestamp": None
        }
        
        if not os.path.exists(db_path):
            return result
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Interogare最新InterviewÎnregistrare
            cursor.execute("""
                SELECT user_id, info, created_at
                FROM trace
                WHERE action = ? AND user_id = ?
                ORDER BY created_at DESC
                LIMIT 1
            """, (ActionType.INTERVIEW.value, agent_id))
            
            row = cursor.fetchone()
            if row:
                user_id, info_json, created_at = row
                try:
                    info = json.loads(info_json) if info_json else {}
                    result["response"] = info.get("response", info)
                    result["timestamp"] = created_at
                except json.JSONDecodeError:
                    result["response"] = info_json
            
            conn.close()
            
        except Exception as e:
            print(f"  读取InterviewRezultatEșec: {e}")
        
        return result
    
    async def process_commands(self) -> bool:
        """
        Procesare所有待Procesare命令
        
        Returns:
            True 表示ContinuareRulare，False 表示应该Ieșire
        """
        command = self.poll_command()
        if not command:
            return True
        
        command_id = command.get("command_id")
        command_type = command.get("command_type")
        args = command.get("args", {})
        
        print(f"\n收laIPC命令: {command_type}, id={command_id}")
        
        if command_type == CommandType.INTERVIEW:
            await self.handle_interview(
                command_id,
                args.get("agent_id", 0),
                args.get("prompt", "")
            )
            return True
            
        elif command_type == CommandType.BATCH_INTERVIEW:
            await self.handle_batch_interview(
                command_id,
                args.get("interviews", [])
            )
            return True
            
        elif command_type == CommandType.CLOSE_ENV:
            print("收laÎnchidereMediu命令")
            self.send_response(command_id, "completed", result={"message": "Mediu即将Închidere"})
            return False
        
        else:
            self.send_response(command_id, "failed", error=f"未知命令Tip: {command_type}")
            return True


class TwitterSimulationRunner:
    """TwitterSimulareRulare器"""
    
    # Twitter可用Acțiune（不包含INTERVIEW，INTERVIEW只能通过ManualAction手动触发）
    AVAILABLE_ACTIONS = [
        ActionType.CREATE_POST,
        ActionType.LIKE_POST,
        ActionType.REPOST,
        ActionType.FOLLOW,
        ActionType.DO_NOTHING,
        ActionType.QUOTE_POST,
    ]
    
    def __init__(self, config_path: str, wait_for_commands: bool = True):
        """
        InițializareSimulareRulare器
        
        Args:
            config_path: ConfigurareFișierCale (simulation_config.json)
            wait_for_commands: SimulareFinalizare后DaNu等待命令（默认True）
        """
        self.config_path = config_path
        self.config = self._load_config()
        self.simulation_dir = os.path.dirname(config_path)
        self.wait_for_commands = wait_for_commands
        self.env = None
        self.agent_graph = None
        self.ipc_handler = None
        
    def _load_config(self) -> Dict[str, Any]:
        """ÎncărcareConfigurareFișier"""
        with open(self.config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _get_profile_path(self) -> str:
        """ObținereProfileFișierCale（OASIS TwitterUtilizareCSVFormat）"""
        return os.path.join(self.simulation_dir, "twitter_profiles.csv")
    
    def _get_db_path(self) -> str:
        """ObținereDate库Cale"""
        return os.path.join(self.simulation_dir, "twitter_simulation.db")
    
    def _create_model(self):
        """
        CreareLLMModel
        
        统一UtilizareProiect根Director .env FișierConfigurare（优先级最高）：
        - LLM_API_KEY: API密钥
        - LLM_BASE_URL: API基础URL
        - LLM_MODEL_NAME: ModelNume
        """
        # 优先de la .env 读取Configurare
        llm_api_key = os.environ.get("LLM_API_KEY", "")
        llm_base_url = os.environ.get("LLM_BASE_URL", "")
        llm_model = os.environ.get("LLM_MODEL_NAME", "")
        
        # dacă .env 没有，则Utilizare config 作为备用
        if not llm_model:
            llm_model = self.config.get("llm_model", "gpt-4o-mini")
        
        # Setări camel-ai 所需MediuVariabilă
        if llm_api_key:
            os.environ["OPENAI_API_KEY"] = llm_api_key
        
        if not os.environ.get("OPENAI_API_KEY"):
            raise ValueError("缺少 API Key Configurare，请înProiect根Director .env FișierSetări LLM_API_KEY")
        
        if llm_base_url:
            os.environ["OPENAI_API_BASE_URL"] = llm_base_url
        
        print(f"LLMConfigurare: model={llm_model}, base_url={llm_base_url[:40] if llm_base_url else '默认'}...")
        
        return ModelFactory.create(
            model_platform=ModelPlatformType.OPENAI,
            model_type=llm_model,
        )
    
    def _get_active_agents_for_round(
        self, 
        env, 
        current_hour: int,
        round_num: int
    ) -> List:
        """
        根据TimpșiConfigurare决定本轮激活哪些Agent
        
        Args:
            env: OASISMediu
            current_hour: când前Simulare小时（0-23）
            round_num: când前轮数
            
        Returns:
            激活AgentListă
        """
        time_config = self.config.get("time_config", {})
        agent_configs = self.config.get("agent_configs", [])
        
        # 基础激活数量
        base_min = time_config.get("agents_per_hour_min", 5)
        base_max = time_config.get("agents_per_hour_max", 20)
        
        # 根据时段调整
        peak_hours = time_config.get("peak_hours", [9, 10, 11, 14, 15, 20, 21, 22])
        off_peak_hours = time_config.get("off_peak_hours", [0, 1, 2, 3, 4, 5])
        
        if current_hour in peak_hours:
            multiplier = time_config.get("peak_activity_multiplier", 1.5)
        elif current_hour in off_peak_hours:
            multiplier = time_config.get("off_peak_activity_multiplier", 0.3)
        else:
            multiplier = 1.0
        
        target_count = int(random.uniform(base_min, base_max) * multiplier)
        
        # 根据每个AgentConfigurare计算激活概率
        candidates = []
        for cfg in agent_configs:
            agent_id = cfg.get("agent_id", 0)
            active_hours = cfg.get("active_hours", list(range(8, 23)))
            activity_level = cfg.get("activity_level", 0.5)
            
            # VerificareDaNuîn活跃Timp
            if current_hour not in active_hours:
                continue
            
            # 根据活跃度计算概率
            if random.random() < activity_level:
                candidates.append(agent_id)
        
        # 随机Selectare
        selected_ids = random.sample(
            candidates, 
            min(target_count, len(candidates))
        ) if candidates else []
        
        # 转换为AgentObiect
        active_agents = []
        for agent_id in selected_ids:
            try:
                agent = env.agent_graph.get_agent(agent_id)
                active_agents.append((agent_id, agent))
            except Exception:
                pass
        
        return active_agents
    
    async def run(self, max_rounds: int = None):
        """RulareTwitterSimulare
        
        Args:
            max_rounds: 最大Simulare轮数（可选，用于截断过长Simulare）
        """
        print("=" * 60)
        print("OASIS TwitterSimulare")
        print(f"ConfigurareFișier: {self.config_path}")
        print(f"SimulareID: {self.config.get('simulation_id', 'unknown')}")
        print(f"等待命令模式: {'启用' if self.wait_for_commands else '禁用'}")
        print("=" * 60)
        
        # ÎncărcareTimpConfigurare
        time_config = self.config.get("time_config", {})
        total_hours = time_config.get("total_simulation_hours", 72)
        minutes_per_round = time_config.get("minutes_per_round", 30)
        
        # 计算总轮数
        total_rounds = (total_hours * 60) // minutes_per_round
        
        # dacă指定最大轮数，则截断
        if max_rounds is not None and max_rounds > 0:
            original_rounds = total_rounds
            total_rounds = min(total_rounds, max_rounds)
            if total_rounds < original_rounds:
                print(f"\n轮数已截断: {original_rounds} -> {total_rounds} (max_rounds={max_rounds})")
        
        print(f"\nSimulareParametru:")
        print(f"  - 总Simulare时长: {total_hours}小时")
        print(f"  - 每轮Timp: {minutes_per_round}分钟")
        print(f"  - 总轮数: {total_rounds}")
        if max_rounds:
            print(f"  - 最大轮数限制: {max_rounds}")
        print(f"  - Agent数量: {len(self.config.get('agent_configs', []))}")
        
        # CreareModel
        print("\nInițializareLLMModel...")
        model = self._create_model()
        
        # ÎncărcareAgent图
        print("ÎncărcareAgent Profile...")
        profile_path = self._get_profile_path()
        if not os.path.exists(profile_path):
            print(f"Eroare: ProfileFișier不存în: {profile_path}")
            return
        
        self.agent_graph = await generate_twitter_agent_graph(
            profile_path=profile_path,
            model=model,
            available_actions=self.AVAILABLE_ACTIONS,
        )
        
        # Date库Cale
        db_path = self._get_db_path()
        if os.path.exists(db_path):
            os.remove(db_path)
            print(f"已Ștergere旧Date库: {db_path}")
        
        # CreareMediu
        print("CreareOASISMediu...")
        self.env = oasis.make(
            agent_graph=self.agent_graph,
            platform=oasis.DefaultPlatformType.TWITTER,
            database_path=db_path,
            semaphore=30,  # 限制最大并发 LLM Cerere数，防止 API 过载
        )
        
        await self.env.reset()
        print("MediuInițializareFinalizare\n")
        
        # InițializareIPCProcesare器
        self.ipc_handler = IPCHandler(self.simulation_dir, self.env, self.agent_graph)
        self.ipc_handler.update_status("running")
        
        # 执行初始事件
        event_config = self.config.get("event_config", {})
        initial_posts = event_config.get("initial_posts", [])
        
        if initial_posts:
            print(f"执行初始事件 ({len(initial_posts)}条初始帖子)...")
            initial_actions = {}
            for post in initial_posts:
                agent_id = post.get("poster_agent_id", 0)
                content = post.get("content", "")
                try:
                    agent = self.env.agent_graph.get_agent(agent_id)
                    initial_actions[agent] = ManualAction(
                        action_type=ActionType.CREATE_POST,
                        action_args={"content": content}
                    )
                except Exception as e:
                    print(f"  Avertisment: 无法为Agent {agent_id}Creare初始帖子: {e}")
            
            if initial_actions:
                await self.env.step(initial_actions)
                print(f"  已Publicare {len(initial_actions)} 条初始帖子")
        
        # 主Simulare循环
        print("\nStartSimulare循环...")
        start_time = datetime.now()
        
        for round_num in range(total_rounds):
            # 计算când前SimulareTimp
            simulated_minutes = round_num * minutes_per_round
            simulated_hour = (simulated_minutes // 60) % 24
            simulated_day = simulated_minutes // (60 * 24) + 1
            
            # Obținere本轮激活Agent
            active_agents = self._get_active_agents_for_round(
                self.env, simulated_hour, round_num
            )
            
            if not active_agents:
                continue
            
            # ConstruireAcțiune
            actions = {
                agent: LLMAction()
                for _, agent in active_agents
            }
            
            # 执行Acțiune
            await self.env.step(actions)
            
            # 打印Progres
            if (round_num + 1) % 10 == 0 or round_num == 0:
                elapsed = (datetime.now() - start_time).total_seconds()
                progress = (round_num + 1) / total_rounds * 100
                print(f"  [Day {simulated_day}, {simulated_hour:02d}:00] "
                      f"Round {round_num + 1}/{total_rounds} ({progress:.1f}%) "
                      f"- {len(active_agents)} agents active "
                      f"- elapsed: {elapsed:.1f}s")
        
        total_elapsed = (datetime.now() - start_time).total_seconds()
        print(f"\nSimulare循环Finalizare!")
        print(f"  - 总耗时: {total_elapsed:.1f}秒")
        print(f"  - Date库: {db_path}")
        
        # DaNu进入等待命令模式
        if self.wait_for_commands:
            print("\n" + "=" * 60)
            print("进入等待命令模式 - Mediu保持Rulare")
            print("Suportă命令: interview, batch_interview, close_env")
            print("=" * 60)
            
            self.ipc_handler.update_status("alive")
            
            # 等待命令循环（Utilizare全局 _shutdown_event）
            try:
                while not _shutdown_event.is_set():
                    should_continue = await self.ipc_handler.process_commands()
                    if not should_continue:
                        break
                    try:
                        await asyncio.wait_for(_shutdown_event.wait(), timeout=0.5)
                        break  # 收laIeșire信号
                    except asyncio.TimeoutError:
                        pass
            except KeyboardInterrupt:
                print("\n收la断信号")
            except asyncio.CancelledError:
                print("\nSarcină被Anulare")
            except Exception as e:
                print(f"\n命令Procesare出错: {e}")
            
            print("\nÎnchidereMediu...")
        
        # ÎnchidereMediu
        self.ipc_handler.update_status("stopped")
        await self.env.close()
        
        print("Mediu已Închidere")
        print("=" * 60)


async def main():
    parser = argparse.ArgumentParser(description='OASIS TwitterSimulare')
    parser.add_argument(
        '--config', 
        type=str, 
        required=True,
        help='ConfigurareFișierCale (simulation_config.json)'
    )
    parser.add_argument(
        '--max-rounds',
        type=int,
        default=None,
        help='最大Simulare轮数（可选，用于截断过长Simulare）'
    )
    parser.add_argument(
        '--no-wait',
        action='store_true',
        default=False,
        help='SimulareFinalizare后立即ÎnchidereMediu，不进入等待命令模式'
    )
    
    args = parser.parse_args()
    
    # în main FuncțieStart时Creare shutdown 事件
    global _shutdown_event
    _shutdown_event = asyncio.Event()
    
    if not os.path.exists(args.config):
        print(f"Eroare: ConfigurareFișier不存în: {args.config}")
        sys.exit(1)
    
    # InițializareJurnalConfigurare（Utilizare固定Fișier名，清理旧Jurnal）
    simulation_dir = os.path.dirname(args.config) or "."
    setup_oasis_logging(os.path.join(simulation_dir, "log"))
    
    runner = TwitterSimulationRunner(
        config_path=args.config,
        wait_for_commands=not args.no_wait
    )
    await runner.run(max_rounds=args.max_rounds)


def setup_signal_handlers():
    """
    Setări信号Procesare器，确保收la SIGTERM/SIGINT 时能够正确Ieșire
    让程序有机会正常清理资源（ÎnchidereDate库、Mediu等）
    """
    def signal_handler(signum, frame):
        global _cleanup_done
        sig_name = "SIGTERM" if signum == signal.SIGTERM else "SIGINT"
        print(f"\n收la {sig_name} 信号，正înIeșire...")
        if not _cleanup_done:
            _cleanup_done = True
            if _shutdown_event:
                _shutdown_event.set()
        else:
            # 重复收la信号才强制Ieșire
            print("强制Ieșire...")
            sys.exit(1)
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)


if __name__ == "__main__":
    setup_signal_handlers()
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n程序被断")
    except SystemExit:
        pass
    finally:
        print("Simulare进程已Ieșire")
