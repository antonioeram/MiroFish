"""
SarcinăStare管理
用于跟踪长TimpRulareSarcină（如GrafConstruire）
"""

import uuid
import threading
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional
from dataclasses import dataclass, field


class TaskStatus(str, Enum):
    """SarcinăStare枚举"""
    PENDING = "pending"          # 等待
    PROCESSING = "processing"    # Procesare
    COMPLETED = "completed"      # 已Finalizare
    FAILED = "failed"            # Eșec


@dataclass
class Task:
    """SarcinăDateClasă"""
    task_id: str
    task_type: str
    status: TaskStatus
    created_at: datetime
    updated_at: datetime
    progress: int = 0              # 总Progres百分比 0-100
    message: str = ""              # StareMesaj
    result: Optional[Dict] = None  # SarcinăRezultat
    error: Optional[str] = None    # EroareInformații
    metadata: Dict = field(default_factory=dict)  # 额外元Date
    progress_detail: Dict = field(default_factory=dict)  # 详细ProgresInformații
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为Dicționar"""
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "progress": self.progress,
            "message": self.message,
            "progress_detail": self.progress_detail,
            "result": self.result,
            "error": self.error,
            "metadata": self.metadata,
        }


class TaskManager:
    """
    Sarcină管理器
    线程安全SarcinăStare管理
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._tasks: Dict[str, Task] = {}
                    cls._instance._task_lock = threading.Lock()
        return cls._instance
    
    def create_task(self, task_type: str, metadata: Optional[Dict] = None) -> str:
        """
        Creare新Sarcină
        
        Args:
            task_type: SarcinăTip
            metadata: 额外元Date
            
        Returns:
            SarcinăID
        """
        task_id = str(uuid.uuid4())
        now = datetime.now()
        
        task = Task(
            task_id=task_id,
            task_type=task_type,
            status=TaskStatus.PENDING,
            created_at=now,
            updated_at=now,
            metadata=metadata or {}
        )
        
        with self._task_lock:
            self._tasks[task_id] = task
        
        return task_id
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """ObținereSarcină"""
        with self._task_lock:
            return self._tasks.get(task_id)
    
    def update_task(
        self,
        task_id: str,
        status: Optional[TaskStatus] = None,
        progress: Optional[int] = None,
        message: Optional[str] = None,
        result: Optional[Dict] = None,
        error: Optional[str] = None,
        progress_detail: Optional[Dict] = None
    ):
        """
        ActualizareSarcinăStare
        
        Args:
            task_id: SarcinăID
            status: 新Stare
            progress: Progres
            message: Mesaj
            result: Rezultat
            error: EroareInformații
            progress_detail: 详细ProgresInformații
        """
        with self._task_lock:
            task = self._tasks.get(task_id)
            if task:
                task.updated_at = datetime.now()
                if status is not None:
                    task.status = status
                if progress is not None:
                    task.progress = progress
                if message is not None:
                    task.message = message
                if result is not None:
                    task.result = result
                if error is not None:
                    task.error = error
                if progress_detail is not None:
                    task.progress_detail = progress_detail
    
    def complete_task(self, task_id: str, result: Dict):
        """标记SarcinăFinalizare"""
        self.update_task(
            task_id,
            status=TaskStatus.COMPLETED,
            progress=100,
            message="SarcinăFinalizare",
            result=result
        )
    
    def fail_task(self, task_id: str, error: str):
        """标记SarcinăEșec"""
        self.update_task(
            task_id,
            status=TaskStatus.FAILED,
            message="SarcinăEșec",
            error=error
        )
    
    def list_tasks(self, task_type: Optional[str] = None) -> list:
        """列出Sarcină"""
        with self._task_lock:
            tasks = list(self._tasks.values())
            if task_type:
                tasks = [t for t in tasks if t.task_type == task_type]
            return [t.to_dict() for t in sorted(tasks, key=lambda x: x.created_at, reverse=True)]
    
    def cleanup_old_tasks(self, max_age_hours: int = 24):
        """清理旧Sarcină"""
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        
        with self._task_lock:
            old_ids = [
                tid for tid, task in self._tasks.items()
                if task.created_at < cutoff and task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]
            ]
            for tid in old_ids:
                del self._tasks[tid]

