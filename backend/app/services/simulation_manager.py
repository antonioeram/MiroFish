"""
OASISSimulare管理器
管理TwitterșiReddit双PlatformăParalelSimulare
Utilizare预设Script + LLM智能GenerareConfigurareParametru
"""

import os
import json
import shutil
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from ..config import Config
from ..utils.logger import get_logger
from .zep_entity_reader import ZepEntityReader, FilteredEntities
from .oasis_profile_generator import OasisProfileGenerator, OasisAgentProfile
from .simulation_config_generator import SimulationConfigGenerator, SimulationParameters

logger = get_logger('mirofish.simulation')


class SimulationStatus(str, Enum):
    """SimulareStare"""
    CREATED = "created"
    PREPARING = "preparing"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"      # Simulare被ManualOprire
    COMPLETED = "completed"  # Simulare自然Finalizare
    FAILED = "failed"


class PlatformType(str, Enum):
    """PlatformăTip"""
    TWITTER = "twitter"
    REDDIT = "reddit"


@dataclass
class SimulationState:
    """SimulareStare"""
    simulation_id: str
    project_id: str
    graph_id: str
    
    # Platformă启用Stare
    enable_twitter: bool = True
    enable_reddit: bool = True
    
    # Stare
    status: SimulationStatus = SimulationStatus.CREATED
    
    # 准备阶段Date
    entities_count: int = 0
    profiles_count: int = 0
    entity_types: List[str] = field(default_factory=list)
    
    # ConfigurareGenerareInformații
    config_generated: bool = False
    config_reasoning: str = ""
    
    # Rulare时Date
    current_round: int = 0
    twitter_status: str = "not_started"
    reddit_status: str = "not_started"
    
    # Timp戳
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    # EroareInformații
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """CompletStareDicționar（内部Utilizare）"""
        return {
            "simulation_id": self.simulation_id,
            "project_id": self.project_id,
            "graph_id": self.graph_id,
            "enable_twitter": self.enable_twitter,
            "enable_reddit": self.enable_reddit,
            "status": self.status.value,
            "entities_count": self.entities_count,
            "profiles_count": self.profiles_count,
            "entity_types": self.entity_types,
            "config_generated": self.config_generated,
            "config_reasoning": self.config_reasoning,
            "current_round": self.current_round,
            "twitter_status": self.twitter_status,
            "reddit_status": self.reddit_status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "error": self.error,
        }
    
    def to_simple_dict(self) -> Dict[str, Any]:
        """简化StareDicționar（APIReturnareUtilizare）"""
        return {
            "simulation_id": self.simulation_id,
            "project_id": self.project_id,
            "graph_id": self.graph_id,
            "status": self.status.value,
            "entities_count": self.entities_count,
            "profiles_count": self.profiles_count,
            "entity_types": self.entity_types,
            "config_generated": self.config_generated,
            "error": self.error,
        }


class SimulationManager:
    """
    Simulare管理器
    
    核心Funcționalitate：
    1. de laZepGraf读取Entitate并过滤
    2. GenerareOASIS Agent Profile
    3. UtilizareLLM智能GenerareSimulareConfigurareParametru
    4. 准备预设Script所需所有Fișier
    """
    
    # SimulareDate存储Director
    SIMULATION_DATA_DIR = os.path.join(
        os.path.dirname(__file__), 
        '../../uploads/simulations'
    )
    
    def __init__(self):
        # 确保Director存în
        os.makedirs(self.SIMULATION_DATA_DIR, exist_ok=True)
        
        # 内存SimulareStare缓存
        self._simulations: Dict[str, SimulationState] = {}
    
    def _get_simulation_dir(self, simulation_id: str) -> str:
        """ObținereSimulareDateDirector"""
        sim_dir = os.path.join(self.SIMULATION_DATA_DIR, simulation_id)
        os.makedirs(sim_dir, exist_ok=True)
        return sim_dir
    
    def _save_simulation_state(self, state: SimulationState):
        """SalvareSimulareStarelaFișier"""
        sim_dir = self._get_simulation_dir(state.simulation_id)
        state_file = os.path.join(sim_dir, "state.json")
        
        state.updated_at = datetime.now().isoformat()
        
        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump(state.to_dict(), f, ensure_ascii=False, indent=2)
        
        self._simulations[state.simulation_id] = state
    
    def _load_simulation_state(self, simulation_id: str) -> Optional[SimulationState]:
        """de laFișierÎncărcareSimulareStare"""
        if simulation_id in self._simulations:
            return self._simulations[simulation_id]
        
        sim_dir = self._get_simulation_dir(simulation_id)
        state_file = os.path.join(sim_dir, "state.json")
        
        if not os.path.exists(state_file):
            return None
        
        with open(state_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        state = SimulationState(
            simulation_id=simulation_id,
            project_id=data.get("project_id", ""),
            graph_id=data.get("graph_id", ""),
            enable_twitter=data.get("enable_twitter", True),
            enable_reddit=data.get("enable_reddit", True),
            status=SimulationStatus(data.get("status", "created")),
            entities_count=data.get("entities_count", 0),
            profiles_count=data.get("profiles_count", 0),
            entity_types=data.get("entity_types", []),
            config_generated=data.get("config_generated", False),
            config_reasoning=data.get("config_reasoning", ""),
            current_round=data.get("current_round", 0),
            twitter_status=data.get("twitter_status", "not_started"),
            reddit_status=data.get("reddit_status", "not_started"),
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
            error=data.get("error"),
        )
        
        self._simulations[simulation_id] = state
        return state
    
    def create_simulation(
        self,
        project_id: str,
        graph_id: str,
        enable_twitter: bool = True,
        enable_reddit: bool = True,
    ) -> SimulationState:
        """
        Creare新Simulare
        
        Args:
            project_id: ProiectID
            graph_id: ZepGrafID
            enable_twitter: DaNu启用TwitterSimulare
            enable_reddit: DaNu启用RedditSimulare
            
        Returns:
            SimulationState
        """
        import uuid
        simulation_id = f"sim_{uuid.uuid4().hex[:12]}"
        
        state = SimulationState(
            simulation_id=simulation_id,
            project_id=project_id,
            graph_id=graph_id,
            enable_twitter=enable_twitter,
            enable_reddit=enable_reddit,
            status=SimulationStatus.CREATED,
        )
        
        self._save_simulation_state(state)
        logger.info(f"CreareSimulare: {simulation_id}, project={project_id}, graph={graph_id}")
        
        return state
    
    def prepare_simulation(
        self,
        simulation_id: str,
        simulation_requirement: str,
        document_text: str,
        defined_entity_types: Optional[List[str]] = None,
        use_llm_for_profiles: bool = True,
        progress_callback: Optional[callable] = None,
        parallel_profile_count: int = 3
    ) -> SimulationState:
        """
        准备SimulareMediu（全程Automat化）
        
        步骤：
        1. de laZepGraf读取并过滤Entitate
        2. 为每个EntitateGenerareOASIS Agent Profile（可选LLM增强，SuportăParalel）
        3. UtilizareLLM智能GenerareSimulareConfigurareParametru（Timp、活跃度、发言频率等）
        4. SalvareConfigurareFișierșiProfileFișier
        5. Copiere预设ScriptlaSimulareDirector
        
        Args:
            simulation_id: SimulareID
            simulation_requirement: SimulareCerințăDescriere（用于LLMGenerareConfigurare）
            document_text: 原始DocumentațieConținut（用于LLM理解背景）
            defined_entity_types: 预定义EntitateTip（可选）
            use_llm_for_profiles: DaNuUtilizareLLMGenerare详细人设
            progress_callback: Progres回调Funcție (stage, progress, message)
            parallel_profile_count: ParalelGenerare人设数量，Implicit3
            
        Returns:
            SimulationState
        """
        state = self._load_simulation_state(simulation_id)
        if not state:
            raise ValueError(f"SimulareInexistent: {simulation_id}")
        
        try:
            state.status = SimulationStatus.PREPARING
            self._save_simulation_state(state)
            
            sim_dir = self._get_simulation_dir(simulation_id)
            
            # ========== 阶段1: 读取并过滤Entitate ==========
            if progress_callback:
                progress_callback("reading", 0, "正în连接ZepGraf...")
            
            reader = ZepEntityReader()
            
            if progress_callback:
                progress_callback("reading", 30, "正în读取NodDate...")
            
            filtered = reader.filter_defined_entities(
                graph_id=state.graph_id,
                defined_entity_types=defined_entity_types,
                enrich_with_edges=True
            )
            
            state.entities_count = filtered.filtered_count
            state.entity_types = list(filtered.entity_types)
            
            if progress_callback:
                progress_callback(
                    "reading", 100, 
                    f"Finalizare，共 {filtered.filtered_count} 个Entitate",
                    current=filtered.filtered_count,
                    total=filtered.filtered_count
                )
            
            if filtered.filtered_count == 0:
                state.status = SimulationStatus.FAILED
                state.error = "没有找la符合CondițieEntitate，请VerificareGrafDaNuCorectConstruire"
                self._save_simulation_state(state)
                return state
            
            # ========== 阶段2: GenerareAgent Profile ==========
            total_entities = len(filtered.entities)
            
            if progress_callback:
                progress_callback(
                    "generating_profiles", 0, 
                    "StartGenerare...",
                    current=0,
                    total=total_entities
                )
            
            # 传入graph_id以启用Zep检索Funcționalitate，Obținere更丰富文
            generator = OasisProfileGenerator(graph_id=state.graph_id)
            
            def profile_progress(current, total, msg):
                if progress_callback:
                    progress_callback(
                        "generating_profiles", 
                        int(current / total * 100), 
                        msg,
                        current=current,
                        total=total,
                        item_name=msg
                    )
            
            # Setări实时SalvareFișierCale（优先Utilizare Reddit JSON Format）
            realtime_output_path = None
            realtime_platform = "reddit"
            if state.enable_reddit:
                realtime_output_path = os.path.join(sim_dir, "reddit_profiles.json")
                realtime_platform = "reddit"
            elif state.enable_twitter:
                realtime_output_path = os.path.join(sim_dir, "twitter_profiles.csv")
                realtime_platform = "twitter"
            
            profiles = generator.generate_profiles_from_entities(
                entities=filtered.entities,
                use_llm=use_llm_for_profiles,
                progress_callback=profile_progress,
                graph_id=state.graph_id,  # 传入graph_id用于Zep检索
                parallel_count=parallel_profile_count,  # ParalelGenerare数量
                realtime_output_path=realtime_output_path,  # 实时SalvareCale
                output_platform=realtime_platform  # OutputFormat
            )
            
            state.profiles_count = len(profiles)
            
            # SalvareProfileFișier（注意：TwitterUtilizareCSVFormat，RedditUtilizareJSONFormat）
            # Reddit 已经înGenerare过程实时Salvare，这里再Salvare一次确保Complet性
            if progress_callback:
                progress_callback(
                    "generating_profiles", 95, 
                    "SalvareProfileFișier...",
                    current=total_entities,
                    total=total_entities
                )
            
            if state.enable_reddit:
                generator.save_profiles(
                    profiles=profiles,
                    file_path=os.path.join(sim_dir, "reddit_profiles.json"),
                    platform="reddit"
                )
            
            if state.enable_twitter:
                # TwitterUtilizareCSVFormat！这DaOASIS要求
                generator.save_profiles(
                    profiles=profiles,
                    file_path=os.path.join(sim_dir, "twitter_profiles.csv"),
                    platform="twitter"
                )
            
            if progress_callback:
                progress_callback(
                    "generating_profiles", 100, 
                    f"Finalizare，共 {len(profiles)} 个Profile",
                    current=len(profiles),
                    total=len(profiles)
                )
            
            # ========== 阶段3: LLM智能GenerareSimulareConfigurare ==========
            if progress_callback:
                progress_callback(
                    "generating_config", 0, 
                    "正înAnalizăSimulareCerință...",
                    current=0,
                    total=3
                )
            
            config_generator = SimulationConfigGenerator()
            
            if progress_callback:
                progress_callback(
                    "generating_config", 30, 
                    "正în调用LLMGenerareConfigurare...",
                    current=1,
                    total=3
                )
            
            sim_params = config_generator.generate_config(
                simulation_id=simulation_id,
                project_id=state.project_id,
                graph_id=state.graph_id,
                simulation_requirement=simulation_requirement,
                document_text=document_text,
                entities=filtered.entities,
                enable_twitter=state.enable_twitter,
                enable_reddit=state.enable_reddit
            )
            
            if progress_callback:
                progress_callback(
                    "generating_config", 70, 
                    "正înSalvareConfigurareFișier...",
                    current=2,
                    total=3
                )
            
            # SalvareConfigurareFișier
            config_path = os.path.join(sim_dir, "simulation_config.json")
            with open(config_path, 'w', encoding='utf-8') as f:
                f.write(sim_params.to_json())
            
            state.config_generated = True
            state.config_reasoning = sim_params.generation_reasoning
            
            if progress_callback:
                progress_callback(
                    "generating_config", 100, 
                    "ConfigurareGenerareFinalizare",
                    current=3,
                    total=3
                )
            
            # 注意：RulareScript保留în backend/scripts/ Director，不再CopierelaSimulareDirector
            # 启动Simulare时，simulation_runner 会de la scripts/ DirectorRulareScript
            
            # ActualizareStare
            state.status = SimulationStatus.READY
            self._save_simulation_state(state)
            
            logger.info(f"Simulare准备Finalizare: {simulation_id}, "
                       f"entities={state.entities_count}, profiles={state.profiles_count}")
            
            return state
            
        except Exception as e:
            logger.error(f"Simulare准备Eșec: {simulation_id}, error={str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            state.status = SimulationStatus.FAILED
            state.error = str(e)
            self._save_simulation_state(state)
            raise
    
    def get_simulation(self, simulation_id: str) -> Optional[SimulationState]:
        """ObținereSimulareStare"""
        return self._load_simulation_state(simulation_id)
    
    def list_simulations(self, project_id: Optional[str] = None) -> List[SimulationState]:
        """列出所有Simulare"""
        simulations = []
        
        if os.path.exists(self.SIMULATION_DATA_DIR):
            for sim_id in os.listdir(self.SIMULATION_DATA_DIR):
                # 跳过隐藏Fișier（如 .DS_Store）șinuDirectorFișier
                sim_path = os.path.join(self.SIMULATION_DATA_DIR, sim_id)
                if sim_id.startswith('.') or not os.path.isdir(sim_path):
                    continue
                
                state = self._load_simulation_state(sim_id)
                if state:
                    if project_id is None or state.project_id == project_id:
                        simulations.append(state)
        
        return simulations
    
    def get_profiles(self, simulation_id: str, platform: str = "reddit") -> List[Dict[str, Any]]:
        """ObținereSimulareAgent Profile"""
        state = self._load_simulation_state(simulation_id)
        if not state:
            raise ValueError(f"SimulareInexistent: {simulation_id}")
        
        sim_dir = self._get_simulation_dir(simulation_id)
        profile_path = os.path.join(sim_dir, f"{platform}_profiles.json")
        
        if not os.path.exists(profile_path):
            return []
        
        with open(profile_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def get_simulation_config(self, simulation_id: str) -> Optional[Dict[str, Any]]:
        """ObținereSimulareConfigurare"""
        sim_dir = self._get_simulation_dir(simulation_id)
        config_path = os.path.join(sim_dir, "simulation_config.json")
        
        if not os.path.exists(config_path):
            return None
        
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def get_run_instructions(self, simulation_id: str) -> Dict[str, str]:
        """ObținereRulare说明"""
        sim_dir = self._get_simulation_dir(simulation_id)
        config_path = os.path.join(sim_dir, "simulation_config.json")
        scripts_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../scripts'))
        
        return {
            "simulation_dir": sim_dir,
            "scripts_dir": scripts_dir,
            "config_file": config_path,
            "commands": {
                "twitter": f"python {scripts_dir}/run_twitter_simulation.py --config {config_path}",
                "reddit": f"python {scripts_dir}/run_reddit_simulation.py --config {config_path}",
                "parallel": f"python {scripts_dir}/run_parallel_simulation.py --config {config_path}",
            },
            "instructions": (
                f"1. 激活condaMediu: conda activate MiroFish\n"
                f"2. RulareSimulare (Script位于 {scripts_dir}):\n"
                f"   - 单独RulareTwitter: python {scripts_dir}/run_twitter_simulation.py --config {config_path}\n"
                f"   - 单独RulareReddit: python {scripts_dir}/run_reddit_simulation.py --config {config_path}\n"
                f"   - ParalelRulare双Platformă: python {scripts_dir}/run_parallel_simulation.py --config {config_path}"
            )
        }
