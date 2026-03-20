"""
Configurare simulare智能Generare器
UtilizareLLM根据SimulareCerință、DocumentațieConținut、GrafInformații自动Generare细致SimulareParametru
实现全程自动化，无需人工SetăriParametru

采用分步Generare策略，避免一次性Generare过长Conținut导致Eșec：
1. GenerareTimpConfigurare
2. Generare事件Configurare
3. 分批GenerareAgentConfigurare
4. GenerarePlatformăConfigurare
"""

import json
import math
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime

from openai import OpenAI

from ..config import Config
from ..utils.logger import get_logger
from .zep_entity_reader import EntityNode, ZepEntityReader

logger = get_logger('mirofish.simulation_config')

# 国作息TimpConfigurare（北京Timp）
CHINA_TIMEZONE_CONFIG = {
    # 深夜时段（几乎无人活动）
    "dead_hours": [0, 1, 2, 3, 4, 5],
    # 早间时段（逐渐醒来）
    "morning_hours": [6, 7, 8],
    # 工作时段
    "work_hours": [9, 10, 11, 12, 13, 14, 15, 16, 17, 18],
    # 晚间高峰（最活跃）
    "peak_hours": [19, 20, 21, 22],
    # 夜间时段（活跃度降）
    "night_hours": [23],
    # 活跃度系数
    "activity_multipliers": {
        "dead": 0.05,      # 凌晨几乎无人
        "morning": 0.4,    # 早间逐渐活跃
        "work": 0.7,       # 工作时段等
        "peak": 1.5,       # 晚间高峰
        "night": 0.5       # 深夜降
    }
}


@dataclass
class AgentActivityConfig:
    """单个Agent活动Configurare"""
    agent_id: int
    entity_uuid: str
    entity_name: str
    entity_type: str
    
    # 活跃度Configurare (0.0-1.0)
    activity_level: float = 0.5  # 整体活跃度
    
    # 发言频率（每小时预期发言次数）
    posts_per_hour: float = 1.0
    comments_per_hour: float = 2.0
    
    # 活跃Timp段（24小时制，0-23）
    active_hours: List[int] = field(default_factory=lambda: list(range(8, 23)))
    
    # Răspuns速度（对热点事件反应延迟，单位：Simulare分钟）
    response_delay_min: int = 5
    response_delay_max: int = 60
    
    # 情感倾către (-1.0la1.0，负面la正面)
    sentiment_bias: float = 0.0
    
    # 立场（对特定SubiectAtitudine）
    stance: str = "neutral"  # supportive, opposing, neutral, observer
    
    # 影响力权重（决定其发言被其他Agent看la概率）
    influence_weight: float = 1.0


@dataclass  
class TimeSimulationConfig:
    """TimpConfigurare simulare（基于国人作息习惯）"""
    # Simulare总时长（Simulare小时数）
    total_simulation_hours: int = 72  # 默认Simulare72小时（3天）
    
    # 每轮代表Timp（Simulare分钟）- 默认60分钟（1小时），加快Timp流速
    minutes_per_round: int = 60
    
    # 每小时激活Agent数量范围
    agents_per_hour_min: int = 5
    agents_per_hour_max: int = 20
    
    # 高峰时段（晚间19-22点，国人最活跃Timp）
    peak_hours: List[int] = field(default_factory=lambda: [19, 20, 21, 22])
    peak_activity_multiplier: float = 1.5
    
    # 低谷时段（凌晨0-5点，几乎无人活动）
    off_peak_hours: List[int] = field(default_factory=lambda: [0, 1, 2, 3, 4, 5])
    off_peak_activity_multiplier: float = 0.05  # 凌晨活跃度极低
    
    # 早间时段
    morning_hours: List[int] = field(default_factory=lambda: [6, 7, 8])
    morning_activity_multiplier: float = 0.4
    
    # 工作时段
    work_hours: List[int] = field(default_factory=lambda: [9, 10, 11, 12, 13, 14, 15, 16, 17, 18])
    work_activity_multiplier: float = 0.7


@dataclass
class EventConfig:
    """事件Configurare"""
    # 初始事件（SimulareStart时触发事件）
    initial_posts: List[Dict[str, Any]] = field(default_factory=list)
    
    # 定时事件（în特定Timp触发事件）
    scheduled_events: List[Dict[str, Any]] = field(default_factory=list)
    
    # 热点Subiect关Cheie词
    hot_topics: List[str] = field(default_factory=list)
    
    # 舆论引导方către
    narrative_direction: str = ""


@dataclass
class PlatformConfig:
    """Platformă特定Configurare"""
    platform: str  # twitter or reddit
    
    # 推荐算法权重
    recency_weight: float = 0.4  # Timp新鲜度
    popularity_weight: float = 0.3  # 热度
    relevance_weight: float = 0.3  # 相关性
    
    # 病毒传播阈Valoare（达la多少互动后触发扩散）
    viral_threshold: int = 10
    
    # 回声室效应强度（相似Opinie聚集程度）
    echo_chamber_strength: float = 0.5


@dataclass
class SimulationParameters:
    """完整SimulareParametruConfigurare"""
    # 基础Informații
    simulation_id: str
    project_id: str
    graph_id: str
    simulation_requirement: str
    
    # TimpConfigurare
    time_config: TimeSimulationConfig = field(default_factory=TimeSimulationConfig)
    
    # AgentConfigurareListă
    agent_configs: List[AgentActivityConfig] = field(default_factory=list)
    
    # 事件Configurare
    event_config: EventConfig = field(default_factory=EventConfig)
    
    # PlatformăConfigurare
    twitter_config: Optional[PlatformConfig] = None
    reddit_config: Optional[PlatformConfig] = None
    
    # LLMConfigurare
    llm_model: str = ""
    llm_base_url: str = ""
    
    # Generare元Date
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    generation_reasoning: str = ""  # LLM推理说明
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为Dicționar"""
        time_dict = asdict(self.time_config)
        return {
            "simulation_id": self.simulation_id,
            "project_id": self.project_id,
            "graph_id": self.graph_id,
            "simulation_requirement": self.simulation_requirement,
            "time_config": time_dict,
            "agent_configs": [asdict(a) for a in self.agent_configs],
            "event_config": asdict(self.event_config),
            "twitter_config": asdict(self.twitter_config) if self.twitter_config else None,
            "reddit_config": asdict(self.reddit_config) if self.reddit_config else None,
            "llm_model": self.llm_model,
            "llm_base_url": self.llm_base_url,
            "generated_at": self.generated_at,
            "generation_reasoning": self.generation_reasoning,
        }
    
    def to_json(self, indent: int = 2) -> str:
        """转换为JSONȘir"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


class SimulationConfigGenerator:
    """
    Configurare simulare智能Generare器
    
    UtilizareLLMAnalizăSimulareCerință、DocumentațieConținut、GrafEntitateInformații，
    自动Generare最佳SimulareParametruConfigurare
    
    采用分步Generare策略：
    1. GenerareTimpConfigurareși事件Configurare（轻量级）
    2. 分批GenerareAgentConfigurare（每批10-20个）
    3. GenerarePlatformăConfigurare
    """
    
    # 文最大字符数
    MAX_CONTEXT_LENGTH = 50000
    # 每批GenerareAgent数量
    AGENTS_PER_BATCH = 15
    
    # 各步骤文截断长度（字符数）
    TIME_CONFIG_CONTEXT_LENGTH = 10000   # TimpConfigurare
    EVENT_CONFIG_CONTEXT_LENGTH = 8000   # 事件Configurare
    ENTITY_SUMMARY_LENGTH = 300          # Entitate摘要
    AGENT_SUMMARY_LENGTH = 300           # AgentConfigurareEntitate摘要
    ENTITIES_PER_TYPE_DISPLAY = 20       # 每ClasăEntitate显示数量
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None
    ):
        self.api_key = api_key or Config.LLM_API_KEY
        self.base_url = base_url or Config.LLM_BASE_URL
        self.model_name = model_name or Config.LLM_MODEL_NAME
        
        if not self.api_key:
            raise ValueError("LLM_API_KEY 未Configurare")
        
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )
    
    def generate_config(
        self,
        simulation_id: str,
        project_id: str,
        graph_id: str,
        simulation_requirement: str,
        document_text: str,
        entities: List[EntityNode],
        enable_twitter: bool = True,
        enable_reddit: bool = True,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> SimulationParameters:
        """
        智能Generare完整Configurare simulare（分步Generare）
        
        Args:
            simulation_id: SimulareID
            project_id: ProiectID
            graph_id: GrafID
            simulation_requirement: SimulareCerințăDescriere
            document_text: 原始DocumentațieConținut
            entities: 过滤后EntitateListă
            enable_twitter: DaNu启用Twitter
            enable_reddit: DaNu启用Reddit
            progress_callback: Progres回调Funcție(current_step, total_steps, message)
            
        Returns:
            SimulationParameters: 完整SimulareParametru
        """
        logger.info(f"Start智能GenerareConfigurare simulare: simulation_id={simulation_id}, Entitate数={len(entities)}")
        
        # 计算Total pași数
        num_batches = math.ceil(len(entities) / self.AGENTS_PER_BATCH)
        total_steps = 3 + num_batches  # TimpConfigurare + 事件Configurare + N批Agent + PlatformăConfigurare
        current_step = 0
        
        def report_progress(step: int, message: str):
            nonlocal current_step
            current_step = step
            if progress_callback:
                progress_callback(step, total_steps, message)
            logger.info(f"[{step}/{total_steps}] {message}")
        
        # 1. Construire基础文Informații
        context = self._build_context(
            simulation_requirement=simulation_requirement,
            document_text=document_text,
            entities=entities
        )
        
        reasoning_parts = []
        
        # ========== 步骤1: GenerareTimpConfigurare ==========
        report_progress(1, "GenerareTimpConfigurare...")
        num_entities = len(entities)
        time_config_result = self._generate_time_config(context, num_entities)
        time_config = self._parse_time_config(time_config_result, num_entities)
        reasoning_parts.append(f"TimpConfigurare: {time_config_result.get('reasoning', 'Succes')}")
        
        # ========== 步骤2: Generare事件Configurare ==========
        report_progress(2, "Generare事件Configurareși热点Subiect...")
        event_config_result = self._generate_event_config(context, simulation_requirement, entities)
        event_config = self._parse_event_config(event_config_result)
        reasoning_parts.append(f"事件Configurare: {event_config_result.get('reasoning', 'Succes')}")
        
        # ========== 步骤3-N: 分批GenerareAgentConfigurare ==========
        all_agent_configs = []
        for batch_idx in range(num_batches):
            start_idx = batch_idx * self.AGENTS_PER_BATCH
            end_idx = min(start_idx + self.AGENTS_PER_BATCH, len(entities))
            batch_entities = entities[start_idx:end_idx]
            
            report_progress(
                3 + batch_idx,
                f"GenerareAgentConfigurare ({start_idx + 1}-{end_idx}/{len(entities)})..."
            )
            
            batch_configs = self._generate_agent_configs_batch(
                context=context,
                entities=batch_entities,
                start_idx=start_idx,
                simulation_requirement=simulation_requirement
            )
            all_agent_configs.extend(batch_configs)
        
        reasoning_parts.append(f"AgentConfigurare: SuccesGenerare {len(all_agent_configs)} 个")
        
        # ========== 为初始帖子分配Publicare者 Agent ==========
        logger.info("为初始帖子分配合适Publicare者 Agent...")
        event_config = self._assign_initial_post_agents(event_config, all_agent_configs)
        assigned_count = len([p for p in event_config.initial_posts if p.get("poster_agent_id") is not None])
        reasoning_parts.append(f"初始帖子分配: {assigned_count} 个帖子已分配Publicare者")
        
        # ========== 最后一步: GenerarePlatformăConfigurare ==========
        report_progress(total_steps, "GenerarePlatformăConfigurare...")
        twitter_config = None
        reddit_config = None
        
        if enable_twitter:
            twitter_config = PlatformConfig(
                platform="twitter",
                recency_weight=0.4,
                popularity_weight=0.3,
                relevance_weight=0.3,
                viral_threshold=10,
                echo_chamber_strength=0.5
            )
        
        if enable_reddit:
            reddit_config = PlatformConfig(
                platform="reddit",
                recency_weight=0.3,
                popularity_weight=0.4,
                relevance_weight=0.3,
                viral_threshold=15,
                echo_chamber_strength=0.6
            )
        
        # Construire最终Parametru
        params = SimulationParameters(
            simulation_id=simulation_id,
            project_id=project_id,
            graph_id=graph_id,
            simulation_requirement=simulation_requirement,
            time_config=time_config,
            agent_configs=all_agent_configs,
            event_config=event_config,
            twitter_config=twitter_config,
            reddit_config=reddit_config,
            llm_model=self.model_name,
            llm_base_url=self.base_url,
            generation_reasoning=" | ".join(reasoning_parts)
        )
        
        logger.info(f"Configurare simulareGenerareFinalizare: {len(params.agent_configs)} 个AgentConfigurare")
        
        return params
    
    def _build_context(
        self,
        simulation_requirement: str,
        document_text: str,
        entities: List[EntityNode]
    ) -> str:
        """ConstruireLLM文，截断la最大长度"""
        
        # Entitate摘要
        entity_summary = self._summarize_entities(entities)
        
        # Construire文
        context_parts = [
            f"## SimulareCerință\n{simulation_requirement}",
            f"\n## EntitateInformații ({len(entities)}个)\n{entity_summary}",
        ]
        
        current_length = sum(len(p) for p in context_parts)
        remaining_length = self.MAX_CONTEXT_LENGTH - current_length - 500  # 留500字符余量
        
        if remaining_length > 0 and document_text:
            doc_text = document_text[:remaining_length]
            if len(document_text) > remaining_length:
                doc_text += "\n...(Documentație已截断)"
            context_parts.append(f"\n## 原始DocumentațieConținut\n{doc_text}")
        
        return "\n".join(context_parts)
    
    def _summarize_entities(self, entities: List[EntityNode]) -> str:
        """GenerareEntitate摘要"""
        lines = []
        
        # 按Tip分组
        by_type: Dict[str, List[EntityNode]] = {}
        for e in entities:
            t = e.get_entity_type() or "Unknown"
            if t not in by_type:
                by_type[t] = []
            by_type[t].append(e)
        
        for entity_type, type_entities in by_type.items():
            lines.append(f"\n### {entity_type} ({len(type_entities)}个)")
            # UtilizareConfigurare显示数量și摘要长度
            display_count = self.ENTITIES_PER_TYPE_DISPLAY
            summary_len = self.ENTITY_SUMMARY_LENGTH
            for e in type_entities[:display_count]:
                summary_preview = (e.summary[:summary_len] + "...") if len(e.summary) > summary_len else e.summary
                lines.append(f"- {e.name}: {summary_preview}")
            if len(type_entities) > display_count:
                lines.append(f"  ... 还有 {len(type_entities) - display_count} 个")
        
        return "\n".join(lines)
    
    def _call_llm_with_retry(self, prompt: str, system_prompt: str) -> Dict[str, Any]:
        """带ReîncearcăLLM调用，包含JSON修复逻辑"""
        import re
        
        max_attempts = 3
        last_error = None
        
        for attempt in range(max_attempts):
            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.7 - (attempt * 0.1)  # 每次Reîncearcă降低温度
                    # 不Setărimax_tokens，让LLM自由发挥
                )
                
                content = response.choices[0].message.content
                finish_reason = response.choices[0].finish_reason
                
                # VerificareDaNu被截断
                if finish_reason == 'length':
                    logger.warning(f"LLMOutput被截断 (attempt {attempt+1})")
                    content = self._fix_truncated_json(content)
                
                # 尝试解析JSON
                try:
                    return json.loads(content)
                except json.JSONDecodeError as e:
                    logger.warning(f"JSON解析Eșec (attempt {attempt+1}): {str(e)[:80]}")
                    
                    # 尝试修复JSON
                    fixed = self._try_fix_config_json(content)
                    if fixed:
                        return fixed
                    
                    last_error = e
                    
            except Exception as e:
                logger.warning(f"LLM调用Eșec (attempt {attempt+1}): {str(e)[:80]}")
                last_error = e
                import time
                time.sleep(2 * (attempt + 1))
        
        raise last_error or Exception("LLM调用Eșec")
    
    def _fix_truncated_json(self, content: str) -> str:
        """修复被截断JSON"""
        content = content.strip()
        
        # 计算未闭合括号
        open_braces = content.count('{') - content.count('}')
        open_brackets = content.count('[') - content.count(']')
        
        # VerificareDaNu有未闭合Șir
        if content and content[-1] not in '",}]':
            content += '"'
        
        # 闭合括号
        content += ']' * open_brackets
        content += '}' * open_braces
        
        return content
    
    def _try_fix_config_json(self, content: str) -> Optional[Dict[str, Any]]:
        """尝试修复ConfigurareJSON"""
        import re
        
        # 修复被截断情况
        content = self._fix_truncated_json(content)
        
        # 提取JSON部分
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            json_str = json_match.group()
            
            # 移除Șir换行符
            def fix_string(match):
                s = match.group(0)
                s = s.replace('\n', ' ').replace('\r', ' ')
                s = re.sub(r'\s+', ' ', s)
                return s
            
            json_str = re.sub(r'"[^"\\]*(?:\\.[^"\\]*)*"', fix_string, json_str)
            
            try:
                return json.loads(json_str)
            except:
                # 尝试移除所有控制字符
                json_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', ' ', json_str)
                json_str = re.sub(r'\s+', ' ', json_str)
                try:
                    return json.loads(json_str)
                except:
                    pass
        
        return None
    
    def _generate_time_config(self, context: str, num_entities: int) -> Dict[str, Any]:
        """GenerareTimpConfigurare"""
        # UtilizareConfigurare文截断长度
        context_truncated = context[:self.TIME_CONFIG_CONTEXT_LENGTH]
        
        # 计算最大允许Valoare（80%agent数）
        max_agents_allowed = max(1, int(num_entities * 0.9))
        
        prompt = f"""基于以SimulareCerință，GenerareTimpConfigurare simulare。

{context_truncated}

## Sarcină
请GenerareTimpConfigurareJSON。

### 基本原则（仅供参考，需根据具体事件și参și群体灵活调整）：
- Utilizator群体为国人，需符合北京Timp作息习惯
- 凌晨0-5点几乎无人活动（活跃度系数0.05）
- 早6-8点逐渐活跃（活跃度系数0.4）
- 工作Timp9-18点等活跃（活跃度系数0.7）
- 晚间19-22点Da高峰期（活跃度系数1.5）
- 23点后活跃度降（活跃度系数0.5）
- 一般规律：凌晨低活跃、早间渐增、工作时段等、晚间高峰
- **重要**：以示例Valoare仅供参考，你需要根据事件性质、参și群体特点来调整具体时段
  - 例如：学生群体高峰可能Da21-23点；媒体全天活跃；官方机构只în工作Timp
  - 例如：突发热点可能导致深夜也有讨论，off_peak_hours 可适când缩短

### ÎnapoiJSONFormat（不要markdown）

示例：
{{
    "total_simulation_hours": 72,
    "minutes_per_round": 60,
    "agents_per_hour_min": 5,
    "agents_per_hour_max": 50,
    "peak_hours": [19, 20, 21, 22],
    "off_peak_hours": [0, 1, 2, 3, 4, 5],
    "morning_hours": [6, 7, 8],
    "work_hours": [9, 10, 11, 12, 13, 14, 15, 16, 17, 18],
    "reasoning": "针对该事件TimpConfigurare说明"
}}

字段说明：
- total_simulation_hours (int): Simulare总时长，24-168小时，突发事件短、持续Subiect长
- minutes_per_round (int): 每轮时长，30-120分钟，建议60分钟
- agents_per_hour_min (int): 每小时最少激活Agent数（取Valoare范围: 1-{max_agents_allowed}）
- agents_per_hour_max (int): 每小时最多激活Agent数（取Valoare范围: 1-{max_agents_allowed}）
- peak_hours (intArray): 高峰时段，根据事件参și群体调整
- off_peak_hours (intArray): 低谷时段，通常深夜凌晨
- morning_hours (intArray): 早间时段
- work_hours (intArray): 工作时段
- reasoning (string): 简要说明为什么这样Configurare"""

        system_prompt = "你Da社交媒体Simulare专家。Returnează format JSON pur，TimpConfigurare需符合国人作息习惯。"
        
        try:
            return self._call_llm_with_retry(prompt, system_prompt)
        except Exception as e:
            logger.warning(f"TimpConfigurareLLMGenerareEșec: {e}, Utilizare默认Configurare")
            return self._get_default_time_config(num_entities)
    
    def _get_default_time_config(self, num_entities: int) -> Dict[str, Any]:
        """Obținere默认TimpConfigurare（国人作息）"""
        return {
            "total_simulation_hours": 72,
            "minutes_per_round": 60,  # 每轮1小时，加快Timp流速
            "agents_per_hour_min": max(1, num_entities // 15),
            "agents_per_hour_max": max(5, num_entities // 5),
            "peak_hours": [19, 20, 21, 22],
            "off_peak_hours": [0, 1, 2, 3, 4, 5],
            "morning_hours": [6, 7, 8],
            "work_hours": [9, 10, 11, 12, 13, 14, 15, 16, 17, 18],
            "reasoning": "Utilizare默认国人作息Configurare（每轮1小时）"
        }
    
    def _parse_time_config(self, result: Dict[str, Any], num_entities: int) -> TimeSimulationConfig:
        """解析TimpConfigurareRezultat，并Verificareagents_per_hourValoarenu mai mult de总agent数"""
        # Obținere原始Valoare
        agents_per_hour_min = result.get("agents_per_hour_min", max(1, num_entities // 15))
        agents_per_hour_max = result.get("agents_per_hour_max", max(5, num_entities // 5))
        
        # Verificare并修正：确保nu mai mult de总agent数
        if agents_per_hour_min > num_entities:
            logger.warning(f"agents_per_hour_min ({agents_per_hour_min}) 超过总Agent数 ({num_entities})，已修正")
            agents_per_hour_min = max(1, num_entities // 10)
        
        if agents_per_hour_max > num_entities:
            logger.warning(f"agents_per_hour_max ({agents_per_hour_max}) 超过总Agent数 ({num_entities})，已修正")
            agents_per_hour_max = max(agents_per_hour_min + 1, num_entities // 2)
        
        # 确保 min < max
        if agents_per_hour_min >= agents_per_hour_max:
            agents_per_hour_min = max(1, agents_per_hour_max // 2)
            logger.warning(f"agents_per_hour_min >= max，已修正为 {agents_per_hour_min}")
        
        return TimeSimulationConfig(
            total_simulation_hours=result.get("total_simulation_hours", 72),
            minutes_per_round=result.get("minutes_per_round", 60),  # 默认每轮1小时
            agents_per_hour_min=agents_per_hour_min,
            agents_per_hour_max=agents_per_hour_max,
            peak_hours=result.get("peak_hours", [19, 20, 21, 22]),
            off_peak_hours=result.get("off_peak_hours", [0, 1, 2, 3, 4, 5]),
            off_peak_activity_multiplier=0.05,  # 凌晨几乎无人
            morning_hours=result.get("morning_hours", [6, 7, 8]),
            morning_activity_multiplier=0.4,
            work_hours=result.get("work_hours", list(range(9, 19))),
            work_activity_multiplier=0.7,
            peak_activity_multiplier=1.5
        )
    
    def _generate_event_config(
        self, 
        context: str, 
        simulation_requirement: str,
        entities: List[EntityNode]
    ) -> Dict[str, Any]:
        """Generare事件Configurare"""
        
        # Obținere可用EntitateTipListă，供 LLM 参考
        entity_types_available = list(set(
            e.get_entity_type() or "Unknown" for e in entities
        ))
        
        # 为每种Tip列出代表性EntitateNume
        type_examples = {}
        for e in entities:
            etype = e.get_entity_type() or "Unknown"
            if etype not in type_examples:
                type_examples[etype] = []
            if len(type_examples[etype]) < 3:
                type_examples[etype].append(e.name)
        
        type_info = "\n".join([
            f"- {t}: {', '.join(examples)}" 
            for t, examples in type_examples.items()
        ])
        
        # UtilizareConfigurare文截断长度
        context_truncated = context[:self.EVENT_CONFIG_CONTEXT_LENGTH]
        
        prompt = f"""基于以SimulareCerință，Generare事件Configurare。

SimulareCerință: {simulation_requirement}

{context_truncated}

## 可用EntitateTip及示例
{type_info}

## Sarcină
请Generare事件ConfigurareJSON：
- 提取热点Subiect关Cheie词
- Descriere舆论发展方către
- 设计初始帖子Conținut，**每个帖子必须指定 poster_type（Publicare者Tip）**

**重要**: poster_type 必须de la面"可用EntitateTip"Selectare，这样初始帖子才能分配给合适 Agent Publicare。
例如：官方声明应由 Official/University TipPublicare，新闻由 MediaOutlet Publicare，学生Opinie由 Student Publicare。

ÎnapoiJSONFormat（不要markdown）：
{{
    "hot_topics": ["关Cheie词1", "关Cheie词2", ...],
    "narrative_direction": "<舆论发展方cătreDescriere>",
    "initial_posts": [
        {{"content": "帖子Conținut", "poster_type": "EntitateTip（必须de la可用TipSelectare）"}},
        ...
    ],
    "reasoning": "<简要说明>"
}}"""

        system_prompt = "你Da舆论Analiză专家。Returnează format JSON pur。注意 poster_type 必须精确匹配可用EntitateTip。"
        
        try:
            return self._call_llm_with_retry(prompt, system_prompt)
        except Exception as e:
            logger.warning(f"事件ConfigurareLLMGenerareEșec: {e}, Utilizare默认Configurare")
            return {
                "hot_topics": [],
                "narrative_direction": "",
                "initial_posts": [],
                "reasoning": "Utilizare默认Configurare"
            }
    
    def _parse_event_config(self, result: Dict[str, Any]) -> EventConfig:
        """解析事件ConfigurareRezultat"""
        return EventConfig(
            initial_posts=result.get("initial_posts", []),
            scheduled_events=[],
            hot_topics=result.get("hot_topics", []),
            narrative_direction=result.get("narrative_direction", "")
        )
    
    def _assign_initial_post_agents(
        self,
        event_config: EventConfig,
        agent_configs: List[AgentActivityConfig]
    ) -> EventConfig:
        """
        为初始帖子分配合适Publicare者 Agent
        
        根据每个帖子 poster_type 匹配最合适 agent_id
        """
        if not event_config.initial_posts:
            return event_config
        
        # 按EntitateTip建立 agent Index
        agents_by_type: Dict[str, List[AgentActivityConfig]] = {}
        for agent in agent_configs:
            etype = agent.entity_type.lower()
            if etype not in agents_by_type:
                agents_by_type[etype] = []
            agents_by_type[etype].append(agent)
        
        # Tip映射表（Procesare LLM 可能Output不同Format）
        type_aliases = {
            "official": ["official", "university", "governmentagency", "government"],
            "university": ["university", "official"],
            "mediaoutlet": ["mediaoutlet", "media"],
            "student": ["student", "person"],
            "professor": ["professor", "expert", "teacher"],
            "alumni": ["alumni", "person"],
            "organization": ["organization", "ngo", "company", "group"],
            "person": ["person", "student", "alumni"],
        }
        
        # Înregistrare每种Tip已Utilizare agent Index，避免重复Utilizare同一个 agent
        used_indices: Dict[str, int] = {}
        
        updated_posts = []
        for post in event_config.initial_posts:
            poster_type = post.get("poster_type", "").lower()
            content = post.get("content", "")
            
            # 尝试找la匹配 agent
            matched_agent_id = None
            
            # 1. 直接匹配
            if poster_type in agents_by_type:
                agents = agents_by_type[poster_type]
                idx = used_indices.get(poster_type, 0) % len(agents)
                matched_agent_id = agents[idx].agent_id
                used_indices[poster_type] = idx + 1
            else:
                # 2. Utilizare别名匹配
                for alias_key, aliases in type_aliases.items():
                    if poster_type in aliases or alias_key == poster_type:
                        for alias in aliases:
                            if alias in agents_by_type:
                                agents = agents_by_type[alias]
                                idx = used_indices.get(alias, 0) % len(agents)
                                matched_agent_id = agents[idx].agent_id
                                used_indices[alias] = idx + 1
                                break
                    if matched_agent_id is not None:
                        break
            
            # 3. dacă仍未找la，Utilizare影响力最高 agent
            if matched_agent_id is None:
                logger.warning(f"未找laTip '{poster_type}' 匹配 Agent，Utilizare影响力最高 Agent")
                if agent_configs:
                    # 按影响力排序，Selectare影响力最高
                    sorted_agents = sorted(agent_configs, key=lambda a: a.influence_weight, reverse=True)
                    matched_agent_id = sorted_agents[0].agent_id
                else:
                    matched_agent_id = 0
            
            updated_posts.append({
                "content": content,
                "poster_type": post.get("poster_type", "Unknown"),
                "poster_agent_id": matched_agent_id
            })
            
            logger.info(f"初始帖子分配: poster_type='{poster_type}' -> agent_id={matched_agent_id}")
        
        event_config.initial_posts = updated_posts
        return event_config
    
    def _generate_agent_configs_batch(
        self,
        context: str,
        entities: List[EntityNode],
        start_idx: int,
        simulation_requirement: str
    ) -> List[AgentActivityConfig]:
        """分批GenerareAgentConfigurare"""
        
        # ConstruireEntitateInformații（UtilizareConfigurare摘要长度）
        entity_list = []
        summary_len = self.AGENT_SUMMARY_LENGTH
        for i, e in enumerate(entities):
            entity_list.append({
                "agent_id": start_idx + i,
                "entity_name": e.name,
                "entity_type": e.get_entity_type() or "Unknown",
                "summary": e.summary[:summary_len] if e.summary else ""
            })
        
        prompt = f"""基于以Informații，为每个EntitateGenerare社交媒体活动Configurare。

SimulareCerință: {simulation_requirement}

## EntitateListă
```json
{json.dumps(entity_list, ensure_ascii=False, indent=2)}
```

## Sarcină
为每个EntitateGenerare活动Configurare，注意：
- **Timp符合国人作息**：凌晨0-5点几乎不活动，晚间19-22点最活跃
- **官方机构**（University/GovernmentAgency）：活跃度低(0.1-0.3)，工作Timp(9-17)活动，Răspuns慢(60-240分钟)，影响力高(2.5-3.0)
- **媒体**（MediaOutlet）：活跃度(0.4-0.6)，全天活动(8-23)，Răspuns快(5-30分钟)，影响力高(2.0-2.5)
- **个人**（Student/Person/Alumni）：活跃度高(0.6-0.9)，主要晚间活动(18-23)，Răspuns快(1-15分钟)，影响力低(0.8-1.2)
- **公众人物/专家**：活跃度(0.4-0.6)，影响力高(1.5-2.0)

ÎnapoiJSONFormat（不要markdown）：
{{
    "agent_configs": [
        {{
            "agent_id": <必须șiInput一致>,
            "activity_level": <0.0-1.0>,
            "posts_per_hour": <发帖频率>,
            "comments_per_hour": <评论频率>,
            "active_hours": [<活跃小时Listă，考虑国人作息>],
            "response_delay_min": <最小Răspuns延迟分钟>,
            "response_delay_max": <最大Răspuns延迟分钟>,
            "sentiment_bias": <-1.0la1.0>,
            "stance": "<supportive/opposing/neutral/observer>",
            "influence_weight": <影响力权重>
        }},
        ...
    ]
}}"""

        system_prompt = "你Da社交媒体行为Analiză专家。Înapoi纯JSON，Configurare需符合国人作息习惯。"
        
        try:
            result = self._call_llm_with_retry(prompt, system_prompt)
            llm_configs = {cfg["agent_id"]: cfg for cfg in result.get("agent_configs", [])}
        except Exception as e:
            logger.warning(f"AgentConfigurare批次LLMGenerareEșec: {e}, Utilizare规则Generare")
            llm_configs = {}
        
        # ConstruireAgentActivityConfigObiect
        configs = []
        for i, entity in enumerate(entities):
            agent_id = start_idx + i
            cfg = llm_configs.get(agent_id, {})
            
            # dacăLLM没有Generare，Utilizare规则Generare
            if not cfg:
                cfg = self._generate_agent_config_by_rule(entity)
            
            config = AgentActivityConfig(
                agent_id=agent_id,
                entity_uuid=entity.uuid,
                entity_name=entity.name,
                entity_type=entity.get_entity_type() or "Unknown",
                activity_level=cfg.get("activity_level", 0.5),
                posts_per_hour=cfg.get("posts_per_hour", 0.5),
                comments_per_hour=cfg.get("comments_per_hour", 1.0),
                active_hours=cfg.get("active_hours", list(range(9, 23))),
                response_delay_min=cfg.get("response_delay_min", 5),
                response_delay_max=cfg.get("response_delay_max", 60),
                sentiment_bias=cfg.get("sentiment_bias", 0.0),
                stance=cfg.get("stance", "neutral"),
                influence_weight=cfg.get("influence_weight", 1.0)
            )
            configs.append(config)
        
        return configs
    
    def _generate_agent_config_by_rule(self, entity: EntityNode) -> Dict[str, Any]:
        """基于规则Generare单个AgentConfigurare（国人作息）"""
        entity_type = (entity.get_entity_type() or "Unknown").lower()
        
        if entity_type in ["university", "governmentagency", "ngo"]:
            # 官方机构：工作Timp活动，低频率，高影响力
            return {
                "activity_level": 0.2,
                "posts_per_hour": 0.1,
                "comments_per_hour": 0.05,
                "active_hours": list(range(9, 18)),  # 9:00-17:59
                "response_delay_min": 60,
                "response_delay_max": 240,
                "sentiment_bias": 0.0,
                "stance": "neutral",
                "influence_weight": 3.0
            }
        elif entity_type in ["mediaoutlet"]:
            # 媒体：全天活动，等频率，高影响力
            return {
                "activity_level": 0.5,
                "posts_per_hour": 0.8,
                "comments_per_hour": 0.3,
                "active_hours": list(range(7, 24)),  # 7:00-23:59
                "response_delay_min": 5,
                "response_delay_max": 30,
                "sentiment_bias": 0.0,
                "stance": "observer",
                "influence_weight": 2.5
            }
        elif entity_type in ["professor", "expert", "official"]:
            # 专家/教授：工作+晚间活动，等频率
            return {
                "activity_level": 0.4,
                "posts_per_hour": 0.3,
                "comments_per_hour": 0.5,
                "active_hours": list(range(8, 22)),  # 8:00-21:59
                "response_delay_min": 15,
                "response_delay_max": 90,
                "sentiment_bias": 0.0,
                "stance": "neutral",
                "influence_weight": 2.0
            }
        elif entity_type in ["student"]:
            # 学生：晚间为主，高频率
            return {
                "activity_level": 0.8,
                "posts_per_hour": 0.6,
                "comments_per_hour": 1.5,
                "active_hours": [8, 9, 10, 11, 12, 13, 18, 19, 20, 21, 22, 23],  # 午+晚间
                "response_delay_min": 1,
                "response_delay_max": 15,
                "sentiment_bias": 0.0,
                "stance": "neutral",
                "influence_weight": 0.8
            }
        elif entity_type in ["alumni"]:
            # 校友：晚间为主
            return {
                "activity_level": 0.6,
                "posts_per_hour": 0.4,
                "comments_per_hour": 0.8,
                "active_hours": [12, 13, 19, 20, 21, 22, 23],  # 午休+晚间
                "response_delay_min": 5,
                "response_delay_max": 30,
                "sentiment_bias": 0.0,
                "stance": "neutral",
                "influence_weight": 1.0
            }
        else:
            # 普通人：晚间高峰
            return {
                "activity_level": 0.7,
                "posts_per_hour": 0.5,
                "comments_per_hour": 1.2,
                "active_hours": [9, 10, 11, 12, 13, 18, 19, 20, 21, 22, 23],  # 白天+晚间
                "response_delay_min": 2,
                "response_delay_max": 20,
                "sentiment_bias": 0.0,
                "stance": "neutral",
                "influence_weight": 1.0
            }
    

