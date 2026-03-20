"""
Proiect文管理
用于înServiciu端持久化ProiectStare，避免前端înInterfață间传递大量Date
"""

import os
import json
import uuid
import shutil
from datetime import datetime
from typing import Dict, Any, List, Optional
from enum import Enum
from dataclasses import dataclass, field, asdict
from ..config import Config


class ProjectStatus(str, Enum):
    """ProiectStare"""
    CREATED = "created"              # 刚Creare，Fișier已传
    ONTOLOGY_GENERATED = "ontology_generated"  # Ontologie已Generare
    GRAPH_BUILDING = "graph_building"    # GrafConstruire
    GRAPH_COMPLETED = "graph_completed"  # GrafConstruireFinalizare
    FAILED = "failed"                # Eșec


@dataclass
class Project:
    """ProiectDateModel"""
    project_id: str
    name: str
    status: ProjectStatus
    created_at: str
    updated_at: str
    
    # FișierInformații
    files: List[Dict[str, str]] = field(default_factory=list)  # [{filename, path, size}]
    total_text_length: int = 0
    
    # OntologieInformații（Interfață1Generare后填充）
    ontology: Optional[Dict[str, Any]] = None
    analysis_summary: Optional[str] = None
    
    # GrafInformații（Interfață2Finalizare后填充）
    graph_id: Optional[str] = None
    graph_build_task_id: Optional[str] = None
    
    # Configurare
    simulation_requirement: Optional[str] = None
    chunk_size: int = 500
    chunk_overlap: int = 50
    
    # EroareInformații
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为Dicționar"""
        return {
            "project_id": self.project_id,
            "name": self.name,
            "status": self.status.value if isinstance(self.status, ProjectStatus) else self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "files": self.files,
            "total_text_length": self.total_text_length,
            "ontology": self.ontology,
            "analysis_summary": self.analysis_summary,
            "graph_id": self.graph_id,
            "graph_build_task_id": self.graph_build_task_id,
            "simulation_requirement": self.simulation_requirement,
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
            "error": self.error
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Project':
        """de laDicționarCreare"""
        status = data.get('status', 'created')
        if isinstance(status, str):
            status = ProjectStatus(status)
        
        return cls(
            project_id=data['project_id'],
            name=data.get('name', 'Unnamed Project'),
            status=status,
            created_at=data.get('created_at', ''),
            updated_at=data.get('updated_at', ''),
            files=data.get('files', []),
            total_text_length=data.get('total_text_length', 0),
            ontology=data.get('ontology'),
            analysis_summary=data.get('analysis_summary'),
            graph_id=data.get('graph_id'),
            graph_build_task_id=data.get('graph_build_task_id'),
            simulation_requirement=data.get('simulation_requirement'),
            chunk_size=data.get('chunk_size', 500),
            chunk_overlap=data.get('chunk_overlap', 50),
            error=data.get('error')
        )


class ProjectManager:
    """Proiect管理器 - 负责Proiect持久化存储și检索"""
    
    # Proiect存储根Director
    PROJECTS_DIR = os.path.join(Config.UPLOAD_FOLDER, 'projects')
    
    @classmethod
    def _ensure_projects_dir(cls):
        """确保ProiectDirector存în"""
        os.makedirs(cls.PROJECTS_DIR, exist_ok=True)
    
    @classmethod
    def _get_project_dir(cls, project_id: str) -> str:
        """ObținereProiectDirectorCale"""
        return os.path.join(cls.PROJECTS_DIR, project_id)
    
    @classmethod
    def _get_project_meta_path(cls, project_id: str) -> str:
        """ObținereProiect元DateFișierCale"""
        return os.path.join(cls._get_project_dir(project_id), 'project.json')
    
    @classmethod
    def _get_project_files_dir(cls, project_id: str) -> str:
        """ObținereProiectFișier存储Director"""
        return os.path.join(cls._get_project_dir(project_id), 'files')
    
    @classmethod
    def _get_project_text_path(cls, project_id: str) -> str:
        """ObținereProiect提取Text存储Cale"""
        return os.path.join(cls._get_project_dir(project_id), 'extracted_text.txt')
    
    @classmethod
    def create_project(cls, name: str = "Unnamed Project") -> Project:
        """
        Creare新Proiect
        
        Args:
            name: ProiectNume
            
        Returns:
            新CreareProjectObiect
        """
        cls._ensure_projects_dir()
        
        project_id = f"proj_{uuid.uuid4().hex[:12]}"
        now = datetime.now().isoformat()
        
        project = Project(
            project_id=project_id,
            name=name,
            status=ProjectStatus.CREATED,
            created_at=now,
            updated_at=now
        )
        
        # CreareProiectDirector结构
        project_dir = cls._get_project_dir(project_id)
        files_dir = cls._get_project_files_dir(project_id)
        os.makedirs(project_dir, exist_ok=True)
        os.makedirs(files_dir, exist_ok=True)
        
        # SalvareProiect元Date
        cls.save_project(project)
        
        return project
    
    @classmethod
    def save_project(cls, project: Project) -> None:
        """SalvareProiect元Date"""
        project.updated_at = datetime.now().isoformat()
        meta_path = cls._get_project_meta_path(project.project_id)
        
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(project.to_dict(), f, ensure_ascii=False, indent=2)
    
    @classmethod
    def get_project(cls, project_id: str) -> Optional[Project]:
        """
        ObținereProiect
        
        Args:
            project_id: ProiectID
            
        Returns:
            ProjectObiect，dacă不存înReturnareNone
        """
        meta_path = cls._get_project_meta_path(project_id)
        
        if not os.path.exists(meta_path):
            return None
        
        with open(meta_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return Project.from_dict(data)
    
    @classmethod
    def list_projects(cls, limit: int = 50) -> List[Project]:
        """
        列出所有Proiect
        
        Args:
            limit: Returnare数量限制
            
        Returns:
            ProiectListă，按CreareTimp倒序
        """
        cls._ensure_projects_dir()
        
        projects = []
        for project_id in os.listdir(cls.PROJECTS_DIR):
            project = cls.get_project(project_id)
            if project:
                projects.append(project)
        
        # 按CreareTimp倒序排序
        projects.sort(key=lambda p: p.created_at, reverse=True)
        
        return projects[:limit]
    
    @classmethod
    def delete_project(cls, project_id: str) -> bool:
        """
        ȘtergereProiect及其所有Fișier
        
        Args:
            project_id: ProiectID
            
        Returns:
            DaNuȘtergereSucces
        """
        project_dir = cls._get_project_dir(project_id)
        
        if not os.path.exists(project_dir):
            return False
        
        shutil.rmtree(project_dir)
        return True
    
    @classmethod
    def save_file_to_project(cls, project_id: str, file_storage, original_filename: str) -> Dict[str, str]:
        """
        Salvare传FișierlaProiectDirector
        
        Args:
            project_id: ProiectID
            file_storage: FlaskFileStorageObiect
            original_filename: 原始Fișier名
            
        Returns:
            FișierInformațiiDicționar {filename, path, size}
        """
        files_dir = cls._get_project_files_dir(project_id)
        os.makedirs(files_dir, exist_ok=True)
        
        # Generare安全Fișier名
        ext = os.path.splitext(original_filename)[1].lower()
        safe_filename = f"{uuid.uuid4().hex[:8]}{ext}"
        file_path = os.path.join(files_dir, safe_filename)
        
        # SalvareFișier
        file_storage.save(file_path)
        
        # ObținereFișier大小
        file_size = os.path.getsize(file_path)
        
        return {
            "original_filename": original_filename,
            "saved_filename": safe_filename,
            "path": file_path,
            "size": file_size
        }
    
    @classmethod
    def save_extracted_text(cls, project_id: str, text: str) -> None:
        """Salvare提取Text"""
        text_path = cls._get_project_text_path(project_id)
        with open(text_path, 'w', encoding='utf-8') as f:
            f.write(text)
    
    @classmethod
    def get_extracted_text(cls, project_id: str) -> Optional[str]:
        """Obținere提取Text"""
        text_path = cls._get_project_text_path(project_id)
        
        if not os.path.exists(text_path):
            return None
        
        with open(text_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    @classmethod
    def get_project_files(cls, project_id: str) -> List[str]:
        """ObținereProiect所有FișierCale"""
        files_dir = cls._get_project_files_dir(project_id)
        
        if not os.path.exists(files_dir):
            return []
        
        return [
            os.path.join(files_dir, f) 
            for f in os.listdir(files_dir) 
            if os.path.isfile(os.path.join(files_dir, f))
        ]

