"""
Zep检索InstrumentServiciu
封装Graf搜索、Nod读取、边Interogare等Instrument，供Report AgentUtilizare

核心检索Instrument（优化后）：
1. InsightForge（深度洞察检索）- 最强大混合检索，AutomatGenerare子问题并多维度检索
2. PanoramaSearch（广度搜索）- Obținere全貌，包括过期Conținut
3. QuickSearch（Simplu搜索）- Rapid检索
"""

import time
import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

from zep_cloud.client import Zep

from ..config import Config
from ..utils.logger import get_logger
from ..utils.llm_client import LLMClient
from ..utils.zep_paging import fetch_all_nodes, fetch_all_edges

logger = get_logger('mirofish.zep_tools')


@dataclass
class SearchResult:
    """搜索Rezultat"""
    facts: List[str]
    edges: List[Dict[str, Any]]
    nodes: List[Dict[str, Any]]
    query: str
    total_count: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "facts": self.facts,
            "edges": self.edges,
            "nodes": self.nodes,
            "query": self.query,
            "total_count": self.total_count
        }
    
    def to_text(self) -> str:
        """转换为文本Format，供LLM理解"""
        text_parts = [f"搜索Interogare: {self.query}", f"找la {self.total_count} 条相关Informații"]
        
        if self.facts:
            text_parts.append("\n### 相关事实:")
            for i, fact in enumerate(self.facts, 1):
                text_parts.append(f"{i}. {fact}")
        
        return "\n".join(text_parts)


@dataclass
class NodeInfo:
    """NodInformații"""
    uuid: str
    name: str
    labels: List[str]
    summary: str
    attributes: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "uuid": self.uuid,
            "name": self.name,
            "labels": self.labels,
            "summary": self.summary,
            "attributes": self.attributes
        }
    
    def to_text(self) -> str:
        """转换为文本Format"""
        entity_type = next((l for l in self.labels if l not in ["Entity", "Node"]), "NecunoscutTip")
        return f"Entitate: {self.name} (Tip: {entity_type})\n摘要: {self.summary}"


@dataclass
class EdgeInfo:
    """边Informații"""
    uuid: str
    name: str
    fact: str
    source_node_uuid: str
    target_node_uuid: str
    source_node_name: Optional[str] = None
    target_node_name: Optional[str] = None
    # TimpInformații
    created_at: Optional[str] = None
    valid_at: Optional[str] = None
    invalid_at: Optional[str] = None
    expired_at: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "uuid": self.uuid,
            "name": self.name,
            "fact": self.fact,
            "source_node_uuid": self.source_node_uuid,
            "target_node_uuid": self.target_node_uuid,
            "source_node_name": self.source_node_name,
            "target_node_name": self.target_node_name,
            "created_at": self.created_at,
            "valid_at": self.valid_at,
            "invalid_at": self.invalid_at,
            "expired_at": self.expired_at
        }
    
    def to_text(self, include_temporal: bool = False) -> str:
        """转换为文本Format"""
        source = self.source_node_name or self.source_node_uuid[:8]
        target = self.target_node_name or self.target_node_uuid[:8]
        base_text = f"Relație: {source} --[{self.name}]--> {target}\n事实: {self.fact}"
        
        if include_temporal:
            valid_at = self.valid_at or "Necunoscut"
            invalid_at = self.invalid_at or "至今"
            base_text += f"\n时效: {valid_at} - {invalid_at}"
            if self.expired_at:
                base_text += f" (已过期: {self.expired_at})"
        
        return base_text
    
    @property
    def is_expired(self) -> bool:
        """DaNu已过期"""
        return self.expired_at is not None
    
    @property
    def is_invalid(self) -> bool:
        """DaNu已失效"""
        return self.invalid_at is not None


@dataclass
class InsightForgeResult:
    """
    深度洞察检索Rezultat (InsightForge)
    包含多个子问题检索Rezultat，以及综合Analiză
    """
    query: str
    simulation_requirement: str
    sub_queries: List[str]
    
    # 各维度检索Rezultat
    semantic_facts: List[str] = field(default_factory=list)  # 语义搜索Rezultat
    entity_insights: List[Dict[str, Any]] = field(default_factory=list)  # Entitate洞察
    relationship_chains: List[str] = field(default_factory=list)  # Relație链
    
    # 统计Informații
    total_facts: int = 0
    total_entities: int = 0
    total_relationships: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "simulation_requirement": self.simulation_requirement,
            "sub_queries": self.sub_queries,
            "semantic_facts": self.semantic_facts,
            "entity_insights": self.entity_insights,
            "relationship_chains": self.relationship_chains,
            "total_facts": self.total_facts,
            "total_entities": self.total_entities,
            "total_relationships": self.total_relationships
        }
    
    def to_text(self) -> str:
        """转换为详细文本Format，供LLM理解"""
        text_parts = [
            f"## ViitorPredicție深度Analiză",
            f"Analiză问题: {self.query}",
            f"Predicție场景: {self.simulation_requirement}",
            f"\n### PredicțieDate统计",
            f"- 相关Predicție事实: {self.total_facts}条",
            f"- 涉及Entitate: {self.total_entities}个",
            f"- Relație链: {self.total_relationships}条"
        ]
        
        # 子问题
        if self.sub_queries:
            text_parts.append(f"\n### Analiză子问题")
            for i, sq in enumerate(self.sub_queries, 1):
                text_parts.append(f"{i}. {sq}")
        
        # 语义搜索Rezultat
        if self.semantic_facts:
            text_parts.append(f"\n### 【关Cheie事实】(请înRaport引用这些原文)")
            for i, fact in enumerate(self.semantic_facts, 1):
                text_parts.append(f"{i}. \"{fact}\"")
        
        # Entitate洞察
        if self.entity_insights:
            text_parts.append(f"\n### 【核心Entitate】")
            for entity in self.entity_insights:
                text_parts.append(f"- **{entity.get('name', 'Necunoscut')}** ({entity.get('type', 'Entitate')})")
                if entity.get('summary'):
                    text_parts.append(f"  摘要: \"{entity.get('summary')}\"")
                if entity.get('related_facts'):
                    text_parts.append(f"  相关事实: {len(entity.get('related_facts', []))}条")
        
        # Relație链
        if self.relationship_chains:
            text_parts.append(f"\n### 【Relație链】")
            for chain in self.relationship_chains:
                text_parts.append(f"- {chain}")
        
        return "\n".join(text_parts)


@dataclass
class PanoramaResult:
    """
    广度搜索Rezultat (Panorama)
    包含所有相关Informații，包括过期Conținut
    """
    query: str
    
    # ToateNod
    all_nodes: List[NodeInfo] = field(default_factory=list)
    # Toate边（包括过期）
    all_edges: List[EdgeInfo] = field(default_factory=list)
    # CurentValid事实
    active_facts: List[str] = field(default_factory=list)
    # 已过期/失效事实（IstoricÎnregistrare）
    historical_facts: List[str] = field(default_factory=list)
    
    # 统计
    total_nodes: int = 0
    total_edges: int = 0
    active_count: int = 0
    historical_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "all_nodes": [n.to_dict() for n in self.all_nodes],
            "all_edges": [e.to_dict() for e in self.all_edges],
            "active_facts": self.active_facts,
            "historical_facts": self.historical_facts,
            "total_nodes": self.total_nodes,
            "total_edges": self.total_edges,
            "active_count": self.active_count,
            "historical_count": self.historical_count
        }
    
    def to_text(self) -> str:
        """转换为文本Format（CompletVersiune，不截断）"""
        text_parts = [
            f"## 广度搜索Rezultat（Viitor全景视图）",
            f"Interogare: {self.query}",
            f"\n### 统计Informații",
            f"- 总Nod数: {self.total_nodes}",
            f"- 总边数: {self.total_edges}",
            f"- CurentValid事实: {self.active_count}条",
            f"- Istoric/过期事实: {self.historical_count}条"
        ]
        
        # CurentValid事实（CompletOutput，不截断）
        if self.active_facts:
            text_parts.append(f"\n### 【CurentValid事实】(SimulareRezultat原文)")
            for i, fact in enumerate(self.active_facts, 1):
                text_parts.append(f"{i}. \"{fact}\"")
        
        # Istoric/过期事实（CompletOutput，不截断）
        if self.historical_facts:
            text_parts.append(f"\n### 【Istoric/过期事实】(演变过程Înregistrare)")
            for i, fact in enumerate(self.historical_facts, 1):
                text_parts.append(f"{i}. \"{fact}\"")
        
        # 关CheieEntitate（CompletOutput，不截断）
        if self.all_nodes:
            text_parts.append(f"\n### 【涉及Entitate】")
            for node in self.all_nodes:
                entity_type = next((l for l in node.labels if l not in ["Entity", "Node"]), "Entitate")
                text_parts.append(f"- **{node.name}** ({entity_type})")
        
        return "\n".join(text_parts)


@dataclass
class AgentInterview:
    """IndividualAgentInterviuRezultat"""
    agent_name: str
    agent_role: str  # RolTip（如：学生、教师、媒体等）
    agent_bio: str  # Descriere
    question: str  # Interviu问题
    response: str  # Interviu回答
    key_quotes: List[str] = field(default_factory=list)  # 关Cheie引言
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "agent_role": self.agent_role,
            "agent_bio": self.agent_bio,
            "question": self.question,
            "response": self.response,
            "key_quotes": self.key_quotes
        }
    
    def to_text(self) -> str:
        text = f"**{self.agent_name}** ({self.agent_role})\n"
        # 显示Completagent_bio，不截断
        text += f"_Descriere: {self.agent_bio}_\n\n"
        text += f"**Q:** {self.question}\n\n"
        text += f"**A:** {self.response}\n"
        if self.key_quotes:
            text += "\n**关Cheie引言:**\n"
            for quote in self.key_quotes:
                # 清理各种引号
                clean_quote = quote.replace('\u201c', '').replace('\u201d', '').replace('"', '')
                clean_quote = clean_quote.replace('\u300c', '').replace('\u300d', '')
                clean_quote = clean_quote.strip()
                # 去掉开头标点
                while clean_quote and clean_quote[0] in '，,；;：:、。！？\n\r\t ':
                    clean_quote = clean_quote[1:]
                # 过滤包含问题编号垃圾Conținut（问题1-9）
                skip = False
                for d in '123456789':
                    if f'\u95ee\u9898{d}' in clean_quote:
                        skip = True
                        break
                if skip:
                    continue
                # 截断过长Conținut（按句号截断，而nu硬截断）
                if len(clean_quote) > 150:
                    dot_pos = clean_quote.find('\u3002', 80)
                    if dot_pos > 0:
                        clean_quote = clean_quote[:dot_pos + 1]
                    else:
                        clean_quote = clean_quote[:147] + "..."
                if clean_quote and len(clean_quote) >= 10:
                    text += f'> "{clean_quote}"\n'
        return text


@dataclass
class InterviewResult:
    """
    InterviuRezultat (Interview)
    包含多个SimulareAgentInterviu回答
    """
    interview_topic: str  # Interviu主题
    interview_questions: List[str]  # Interviu问题Listă
    
    # InterviuSelectareAgent
    selected_agents: List[Dict[str, Any]] = field(default_factory=list)
    # 各AgentInterviu回答
    interviews: List[AgentInterview] = field(default_factory=list)
    
    # SelectareAgent理由
    selection_reasoning: str = ""
    # 整合后Interviu摘要
    summary: str = ""
    
    # 统计
    total_agents: int = 0
    interviewed_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "interview_topic": self.interview_topic,
            "interview_questions": self.interview_questions,
            "selected_agents": self.selected_agents,
            "interviews": [i.to_dict() for i in self.interviews],
            "selection_reasoning": self.selection_reasoning,
            "summary": self.summary,
            "total_agents": self.total_agents,
            "interviewed_count": self.interviewed_count
        }
    
    def to_text(self) -> str:
        """转换为详细文本Format，供LLM理解șiRaport引用"""
        text_parts = [
            "## 深度InterviuRaport",
            f"**Interviu主题:** {self.interview_topic}",
            f"**Interviu人数:** {self.interviewed_count} / {self.total_agents} 位SimulareAgent",
            "\n### InterviuObiectSelectare理由",
            self.selection_reasoning or "（AutomatSelectare）",
            "\n---",
            "\n### Interviu实录",
        ]

        if self.interviews:
            for i, interview in enumerate(self.interviews, 1):
                text_parts.append(f"\n#### Interviu #{i}: {interview.agent_name}")
                text_parts.append(interview.to_text())
                text_parts.append("\n---")
        else:
            text_parts.append("（无InterviuÎnregistrare）\n\n---")

        text_parts.append("\n### Interviu摘要și核心Opinie")
        text_parts.append(self.summary or "（无摘要）")

        return "\n".join(text_parts)


class ZepToolsService:
    """
    Zep检索InstrumentServiciu
    
    【核心检索Instrument - 优化后】
    1. insight_forge - 深度洞察检索（最强大，AutomatGenerare子问题，多维度检索）
    2. panorama_search - 广度搜索（Obținere全貌，包括过期Conținut）
    3. quick_search - Simplu搜索（Rapid检索）
    4. interview_agents - 深度Interviu（InterviuSimulareAgent，Obținere多视角Opinie）
    
    【基础Instrument】
    - search_graph - Graf语义搜索
    - get_all_nodes - ObținereGraf所有Nod
    - get_all_edges - ObținereGraf所有边（含TimpInformații）
    - get_node_detail - ObținereNod详细Informații
    - get_node_edges - ObținereNod相关边
    - get_entities_by_type - 按TipObținereEntitate
    - get_entity_summary - ObținereEntitateRelație摘要
    """
    
    # ReîncercareConfigurare
    MAX_RETRIES = 3
    RETRY_DELAY = 2.0
    
    def __init__(self, api_key: Optional[str] = None, llm_client: Optional[LLMClient] = None):
        self.api_key = api_key or Config.ZEP_API_KEY
        if not self.api_key:
            raise ValueError("ZEP_API_KEY 未Configurare")
        
        self.client = Zep(api_key=self.api_key)
        # LLM客户端用于InsightForgeGenerare子问题
        self._llm_client = llm_client
        logger.info("ZepToolsService InițializareFinalizare")
    
    @property
    def llm(self) -> LLMClient:
        """延迟InițializareLLM客户端"""
        if self._llm_client is None:
            self._llm_client = LLMClient()
        return self._llm_client
    
    def _call_with_retry(self, func, operation_name: str, max_retries: int = None):
        """带Reîncercare机制API调用"""
        max_retries = max_retries or self.MAX_RETRIES
        last_exception = None
        delay = self.RETRY_DELAY
        
        for attempt in range(max_retries):
            try:
                return func()
            except Exception as e:
                last_exception = e
                if attempt < max_retries - 1:
                    logger.warning(
                        f"Zep {operation_name} 第 {attempt + 1} 次尝试Eșec: {str(e)[:100]}, "
                        f"{delay:.1f}秒后Reîncercare..."
                    )
                    time.sleep(delay)
                    delay *= 2
                else:
                    logger.error(f"Zep {operation_name} în {max_retries} 次尝试后仍Eșec: {str(e)}")
        
        raise last_exception
    
    def search_graph(
        self, 
        graph_id: str, 
        query: str, 
        limit: int = 10,
        scope: str = "edges"
    ) -> SearchResult:
        """
        Graf语义搜索
        
        Utilizare混合搜索（语义+BM25）înGraf搜索相关Informații。
        dacăZep Cloudsearch API不可用，则降级为本地关Cheie词匹配。
        
        Args:
            graph_id: GrafID (Standalone Graph)
            query: 搜索Interogare
            limit: ReturnareRezultat数量
            scope: 搜索范围，"edges" sau "nodes"
            
        Returns:
            SearchResult: 搜索Rezultat
        """
        logger.info(f"Graf搜索: graph_id={graph_id}, query={query[:50]}...")
        
        # 尝试UtilizareZep Cloud Search API
        try:
            search_results = self._call_with_retry(
                func=lambda: self.client.graph.search(
                    graph_id=graph_id,
                    query=query,
                    limit=limit,
                    scope=scope,
                    reranker="cross_encoder"
                ),
                operation_name=f"Graf搜索(graph={graph_id})"
            )
            
            facts = []
            edges = []
            nodes = []
            
            # 解析边搜索Rezultat
            if hasattr(search_results, 'edges') and search_results.edges:
                for edge in search_results.edges:
                    if hasattr(edge, 'fact') and edge.fact:
                        facts.append(edge.fact)
                    edges.append({
                        "uuid": getattr(edge, 'uuid_', None) or getattr(edge, 'uuid', ''),
                        "name": getattr(edge, 'name', ''),
                        "fact": getattr(edge, 'fact', ''),
                        "source_node_uuid": getattr(edge, 'source_node_uuid', ''),
                        "target_node_uuid": getattr(edge, 'target_node_uuid', ''),
                    })
            
            # 解析Nod搜索Rezultat
            if hasattr(search_results, 'nodes') and search_results.nodes:
                for node in search_results.nodes:
                    nodes.append({
                        "uuid": getattr(node, 'uuid_', None) or getattr(node, 'uuid', ''),
                        "name": getattr(node, 'name', ''),
                        "labels": getattr(node, 'labels', []),
                        "summary": getattr(node, 'summary', ''),
                    })
                    # Nod摘要也算作事实
                    if hasattr(node, 'summary') and node.summary:
                        facts.append(f"[{node.name}]: {node.summary}")
            
            logger.info(f"搜索Finalizare: 找la {len(facts)} 条相关事实")
            
            return SearchResult(
                facts=facts,
                edges=edges,
                nodes=nodes,
                query=query,
                total_count=len(facts)
            )
            
        except Exception as e:
            logger.warning(f"Zep Search APIEșec，降级为本地搜索: {str(e)}")
            # 降级：Utilizare本地关Cheie词匹配搜索
            return self._local_search(graph_id, query, limit, scope)
    
    def _local_search(
        self, 
        graph_id: str, 
        query: str, 
        limit: int = 10,
        scope: str = "edges"
    ) -> SearchResult:
        """
        本地关Cheie词匹配搜索（作为Zep Search API降级方案）
        
        Obținere所有边/Nod，然后în本地进行关Cheie词匹配
        
        Args:
            graph_id: GrafID
            query: 搜索Interogare
            limit: ReturnareRezultat数量
            scope: 搜索范围
            
        Returns:
            SearchResult: 搜索Rezultat
        """
        logger.info(f"Utilizare本地搜索: query={query[:30]}...")
        
        facts = []
        edges_result = []
        nodes_result = []
        
        # 提取Interogare关Cheie词（Simplu分词）
        query_lower = query.lower()
        keywords = [w.strip() for w in query_lower.replace(',', ' ').replace('，', ' ').split() if len(w.strip()) > 1]
        
        def match_score(text: str) -> int:
            """计算文本șiInterogare匹配分数"""
            if not text:
                return 0
            text_lower = text.lower()
            # 完全匹配Interogare
            if query_lower in text_lower:
                return 100
            # 关Cheie词匹配
            score = 0
            for keyword in keywords:
                if keyword in text_lower:
                    score += 10
            return score
        
        try:
            if scope in ["edges", "both"]:
                # Obținere所有边并匹配
                all_edges = self.get_all_edges(graph_id)
                scored_edges = []
                for edge in all_edges:
                    score = match_score(edge.fact) + match_score(edge.name)
                    if score > 0:
                        scored_edges.append((score, edge))
                
                # 按分数排序
                scored_edges.sort(key=lambda x: x[0], reverse=True)
                
                for score, edge in scored_edges[:limit]:
                    if edge.fact:
                        facts.append(edge.fact)
                    edges_result.append({
                        "uuid": edge.uuid,
                        "name": edge.name,
                        "fact": edge.fact,
                        "source_node_uuid": edge.source_node_uuid,
                        "target_node_uuid": edge.target_node_uuid,
                    })
            
            if scope in ["nodes", "both"]:
                # Obținere所有Nod并匹配
                all_nodes = self.get_all_nodes(graph_id)
                scored_nodes = []
                for node in all_nodes:
                    score = match_score(node.name) + match_score(node.summary)
                    if score > 0:
                        scored_nodes.append((score, node))
                
                scored_nodes.sort(key=lambda x: x[0], reverse=True)
                
                for score, node in scored_nodes[:limit]:
                    nodes_result.append({
                        "uuid": node.uuid,
                        "name": node.name,
                        "labels": node.labels,
                        "summary": node.summary,
                    })
                    if node.summary:
                        facts.append(f"[{node.name}]: {node.summary}")
            
            logger.info(f"本地搜索Finalizare: 找la {len(facts)} 条相关事实")
            
        except Exception as e:
            logger.error(f"本地搜索Eșec: {str(e)}")
        
        return SearchResult(
            facts=facts,
            edges=edges_result,
            nodes=nodes_result,
            query=query,
            total_count=len(facts)
        )
    
    def get_all_nodes(self, graph_id: str) -> List[NodeInfo]:
        """
        ObținereGraf所有Nod（分页Obținere）

        Args:
            graph_id: GrafID

        Returns:
            NodListă
        """
        logger.info(f"ObținereGraf {graph_id} 所有Nod...")

        nodes = fetch_all_nodes(self.client, graph_id)

        result = []
        for node in nodes:
            node_uuid = getattr(node, 'uuid_', None) or getattr(node, 'uuid', None) or ""
            result.append(NodeInfo(
                uuid=str(node_uuid) if node_uuid else "",
                name=node.name or "",
                labels=node.labels or [],
                summary=node.summary or "",
                attributes=node.attributes or {}
            ))

        logger.info(f"Obținerela {len(result)} 个Nod")
        return result

    def get_all_edges(self, graph_id: str, include_temporal: bool = True) -> List[EdgeInfo]:
        """
        ObținereGraf所有边（分页Obținere，包含TimpInformații）

        Args:
            graph_id: GrafID
            include_temporal: DaNu包含TimpInformații（ImplicitTrue）

        Returns:
            边Listă（包含created_at, valid_at, invalid_at, expired_at）
        """
        logger.info(f"ObținereGraf {graph_id} 所有边...")

        edges = fetch_all_edges(self.client, graph_id)

        result = []
        for edge in edges:
            edge_uuid = getattr(edge, 'uuid_', None) or getattr(edge, 'uuid', None) or ""
            edge_info = EdgeInfo(
                uuid=str(edge_uuid) if edge_uuid else "",
                name=edge.name or "",
                fact=edge.fact or "",
                source_node_uuid=edge.source_node_uuid or "",
                target_node_uuid=edge.target_node_uuid or ""
            )

            # 添加TimpInformații
            if include_temporal:
                edge_info.created_at = getattr(edge, 'created_at', None)
                edge_info.valid_at = getattr(edge, 'valid_at', None)
                edge_info.invalid_at = getattr(edge, 'invalid_at', None)
                edge_info.expired_at = getattr(edge, 'expired_at', None)

            result.append(edge_info)

        logger.info(f"Obținerela {len(result)} 条边")
        return result
    
    def get_node_detail(self, node_uuid: str) -> Optional[NodeInfo]:
        """
        ObținereIndividualNod详细Informații
        
        Args:
            node_uuid: NodUUID
            
        Returns:
            NodInformațiisauNone
        """
        logger.info(f"ObținereNod详情: {node_uuid[:8]}...")
        
        try:
            node = self._call_with_retry(
                func=lambda: self.client.graph.node.get(uuid_=node_uuid),
                operation_name=f"ObținereNod详情(uuid={node_uuid[:8]}...)"
            )
            
            if not node:
                return None
            
            return NodeInfo(
                uuid=getattr(node, 'uuid_', None) or getattr(node, 'uuid', ''),
                name=node.name or "",
                labels=node.labels or [],
                summary=node.summary or "",
                attributes=node.attributes or {}
            )
        except Exception as e:
            logger.error(f"ObținereNod详情Eșec: {str(e)}")
            return None
    
    def get_node_edges(self, graph_id: str, node_uuid: str) -> List[EdgeInfo]:
        """
        ObținereNod相关所有边
        
        通过ObținereGraf所有边，然后过滤出și指定Nod相关边
        
        Args:
            graph_id: GrafID
            node_uuid: NodUUID
            
        Returns:
            边Listă
        """
        logger.info(f"ObținereNod {node_uuid[:8]}... 相关边")
        
        try:
            # ObținereGraf所有边，然后过滤
            all_edges = self.get_all_edges(graph_id)
            
            result = []
            for edge in all_edges:
                # Verificare边DaNuși指定Nod相关（作为源sau目标）
                if edge.source_node_uuid == node_uuid or edge.target_node_uuid == node_uuid:
                    result.append(edge)
            
            logger.info(f"找la {len(result)} 条șiNod相关边")
            return result
            
        except Exception as e:
            logger.warning(f"ObținereNod边Eșec: {str(e)}")
            return []
    
    def get_entities_by_type(
        self, 
        graph_id: str, 
        entity_type: str
    ) -> List[NodeInfo]:
        """
        按TipObținereEntitate
        
        Args:
            graph_id: GrafID
            entity_type: EntitateTip（如 Student, PublicFigure 等）
            
        Returns:
            符合TipEntitateListă
        """
        logger.info(f"ObținereTip为 {entity_type} Entitate...")
        
        all_nodes = self.get_all_nodes(graph_id)
        
        filtered = []
        for node in all_nodes:
            # VerificarelabelsDaNu包含指定Tip
            if entity_type in node.labels:
                filtered.append(node)
        
        logger.info(f"找la {len(filtered)} 个 {entity_type} TipEntitate")
        return filtered
    
    def get_entity_summary(
        self, 
        graph_id: str, 
        entity_name: str
    ) -> Dict[str, Any]:
        """
        Obținere指定EntitateRelație摘要
        
        搜索și该Entitate相关所有Informații，并Generare摘要
        
        Args:
            graph_id: GrafID
            entity_name: EntitateNume
            
        Returns:
            Entitate摘要Informații
        """
        logger.info(f"ObținereEntitate {entity_name} Relație摘要...")
        
        # 先搜索该Entitate相关Informații
        search_result = self.search_graph(
            graph_id=graph_id,
            query=entity_name,
            limit=20
        )
        
        # 尝试în所有Nod找la该Entitate
        all_nodes = self.get_all_nodes(graph_id)
        entity_node = None
        for node in all_nodes:
            if node.name.lower() == entity_name.lower():
                entity_node = node
                break
        
        related_edges = []
        if entity_node:
            # 传入graph_idParametru
            related_edges = self.get_node_edges(graph_id, entity_node.uuid)
        
        return {
            "entity_name": entity_name,
            "entity_info": entity_node.to_dict() if entity_node else None,
            "related_facts": search_result.facts,
            "related_edges": [e.to_dict() for e in related_edges],
            "total_relations": len(related_edges)
        }
    
    def get_graph_statistics(self, graph_id: str) -> Dict[str, Any]:
        """
        ObținereGraf统计Informații
        
        Args:
            graph_id: GrafID
            
        Returns:
            统计Informații
        """
        logger.info(f"ObținereGraf {graph_id} 统计Informații...")
        
        nodes = self.get_all_nodes(graph_id)
        edges = self.get_all_edges(graph_id)
        
        # 统计EntitateTip分布
        entity_types = {}
        for node in nodes:
            for label in node.labels:
                if label not in ["Entity", "Node"]:
                    entity_types[label] = entity_types.get(label, 0) + 1
        
        # 统计RelațieTip分布
        relation_types = {}
        for edge in edges:
            relation_types[edge.name] = relation_types.get(edge.name, 0) + 1
        
        return {
            "graph_id": graph_id,
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "entity_types": entity_types,
            "relation_types": relation_types
        }
    
    def get_simulation_context(
        self, 
        graph_id: str,
        simulation_requirement: str,
        limit: int = 30
    ) -> Dict[str, Any]:
        """
        ObținereSimulare相关文Informații
        
        综合搜索șiSimulareCerință相关所有Informații
        
        Args:
            graph_id: GrafID
            simulation_requirement: SimulareCerințăDescriere
            limit: 每ClasăInformații数量限制
            
        Returns:
            Simulare文Informații
        """
        logger.info(f"ObținereSimulare文: {simulation_requirement[:50]}...")
        
        # 搜索șiSimulareCerință相关Informații
        search_result = self.search_graph(
            graph_id=graph_id,
            query=simulation_requirement,
            limit=limit
        )
        
        # ObținereGraf统计
        stats = self.get_graph_statistics(graph_id)
        
        # Obținere所有EntitateNod
        all_nodes = self.get_all_nodes(graph_id)
        
        # Filtrare有实际TipEntitate（nu纯EntityNod）
        entities = []
        for node in all_nodes:
            custom_labels = [l for l in node.labels if l not in ["Entity", "Node"]]
            if custom_labels:
                entities.append({
                    "name": node.name,
                    "type": custom_labels[0],
                    "summary": node.summary
                })
        
        return {
            "simulation_requirement": simulation_requirement,
            "related_facts": search_result.facts,
            "graph_statistics": stats,
            "entities": entities[:limit],  # 限制数量
            "total_entities": len(entities)
        }
    
    # ========== 核心检索Instrument（优化后） ==========
    
    def insight_forge(
        self,
        graph_id: str,
        query: str,
        simulation_requirement: str,
        report_context: str = "",
        max_sub_queries: int = 5
    ) -> InsightForgeResult:
        """
        【InsightForge - 深度洞察检索】
        
        最强大混合检索Funcție，Automat分解问题并多维度检索：
        1. UtilizareLLM将问题分解为多个子问题
        2. 对每个子问题进行语义搜索
        3. 提取相关Entitate并Obținere其详细Informații
        4. 追踪Relație链
        5. 整合所有Rezultat，Generare深度洞察
        
        Args:
            graph_id: GrafID
            query: Utilizator问题
            simulation_requirement: SimulareCerințăDescriere
            report_context: Raport文（可选，用于更精准子问题Generare）
            max_sub_queries: 最大子问题数量
            
        Returns:
            InsightForgeResult: 深度洞察检索Rezultat
        """
        logger.info(f"InsightForge 深度洞察检索: {query[:50]}...")
        
        result = InsightForgeResult(
            query=query,
            simulation_requirement=simulation_requirement,
            sub_queries=[]
        )
        
        # Step 1: UtilizareLLMGenerare子问题
        sub_queries = self._generate_sub_queries(
            query=query,
            simulation_requirement=simulation_requirement,
            report_context=report_context,
            max_queries=max_sub_queries
        )
        result.sub_queries = sub_queries
        logger.info(f"Generare {len(sub_queries)} 个子问题")
        
        # Step 2: 对每个子问题进行语义搜索
        all_facts = []
        all_edges = []
        seen_facts = set()
        
        for sub_query in sub_queries:
            search_result = self.search_graph(
                graph_id=graph_id,
                query=sub_query,
                limit=15,
                scope="edges"
            )
            
            for fact in search_result.facts:
                if fact not in seen_facts:
                    all_facts.append(fact)
                    seen_facts.add(fact)
            
            all_edges.extend(search_result.edges)
        
        # 对原始问题也进行搜索
        main_search = self.search_graph(
            graph_id=graph_id,
            query=query,
            limit=20,
            scope="edges"
        )
        for fact in main_search.facts:
            if fact not in seen_facts:
                all_facts.append(fact)
                seen_facts.add(fact)
        
        result.semantic_facts = all_facts
        result.total_facts = len(all_facts)
        
        # Step 3: de la边提取相关EntitateUUID，只Obținere这些EntitateInformații（不ObținereToateNod）
        entity_uuids = set()
        for edge_data in all_edges:
            if isinstance(edge_data, dict):
                source_uuid = edge_data.get('source_node_uuid', '')
                target_uuid = edge_data.get('target_node_uuid', '')
                if source_uuid:
                    entity_uuids.add(source_uuid)
                if target_uuid:
                    entity_uuids.add(target_uuid)
        
        # Obținere所有相关Entitate详情（不限制数量，CompletOutput）
        entity_insights = []
        node_map = {}  # 用于后续Relație链Construire
        
        for uuid in list(entity_uuids):  # Procesare所有Entitate，不截断
            if not uuid:
                continue
            try:
                # 单独Obținere每个相关NodInformații
                node = self.get_node_detail(uuid)
                if node:
                    node_map[uuid] = node
                    entity_type = next((l for l in node.labels if l not in ["Entity", "Node"]), "Entitate")
                    
                    # Obținere该Entitate相关所有事实（不截断）
                    related_facts = [
                        f for f in all_facts 
                        if node.name.lower() in f.lower()
                    ]
                    
                    entity_insights.append({
                        "uuid": node.uuid,
                        "name": node.name,
                        "type": entity_type,
                        "summary": node.summary,
                        "related_facts": related_facts  # CompletOutput，不截断
                    })
            except Exception as e:
                logger.debug(f"ObținereNod {uuid} Eșec: {e}")
                continue
        
        result.entity_insights = entity_insights
        result.total_entities = len(entity_insights)
        
        # Step 4: Construire所有Relație链（不限制数量）
        relationship_chains = []
        for edge_data in all_edges:  # Procesare所有边，不截断
            if isinstance(edge_data, dict):
                source_uuid = edge_data.get('source_node_uuid', '')
                target_uuid = edge_data.get('target_node_uuid', '')
                relation_name = edge_data.get('name', '')
                
                source_name = node_map.get(source_uuid, NodeInfo('', '', [], '', {})).name or source_uuid[:8]
                target_name = node_map.get(target_uuid, NodeInfo('', '', [], '', {})).name or target_uuid[:8]
                
                chain = f"{source_name} --[{relation_name}]--> {target_name}"
                if chain not in relationship_chains:
                    relationship_chains.append(chain)
        
        result.relationship_chains = relationship_chains
        result.total_relationships = len(relationship_chains)
        
        logger.info(f"InsightForgeFinalizare: {result.total_facts}条事实, {result.total_entities}个Entitate, {result.total_relationships}条Relație")
        return result
    
    def _generate_sub_queries(
        self,
        query: str,
        simulation_requirement: str,
        report_context: str = "",
        max_queries: int = 5
    ) -> List[str]:
        """
        UtilizareLLMGenerare子问题
        
        将Complex问题分解为多个可以独立检索子问题
        """
        system_prompt = """你Da一个专业问题Analiză专家。你SarcinăDa将一个Complex问题分解为多个可以înSimulare世界独立观察子问题。

要求：
1. 每个子问题应该足够具体，可以înSimulare世界找la相关AgentComportamentsauEveniment
2. 子问题应该覆盖原问题不同维度（如：谁、什么、为什么、怎么样、何时、何地）
3. 子问题应该șiSimulare场景相关
4. ReturnareJSONFormat：{"sub_queries": ["子问题1", "子问题2", ...]}"""

        user_prompt = f"""SimulareCerință背景：
{simulation_requirement}

{f"Raport文：{report_context[:500]}" if report_context else ""}

请将以问题分解为{max_queries}个子问题：
{query}

ReturnareJSONFormat子问题Listă。"""

        try:
            response = self.llm.chat_json(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3
            )
            
            sub_queries = response.get("sub_queries", [])
            # 确保DaȘirListă
            return [str(sq) for sq in sub_queries[:max_queries]]
            
        except Exception as e:
            logger.warning(f"Generare子问题Eșec: {str(e)}，UtilizareImplicit子问题")
            # 降级：Returnare基于原问题变体
            return [
                query,
                f"{query} 主要参și者",
                f"{query} 原因șiImpact",
                f"{query} 发展过程"
            ][:max_queries]
    
    def panorama_search(
        self,
        graph_id: str,
        query: str,
        include_expired: bool = True,
        limit: int = 50
    ) -> PanoramaResult:
        """
        【PanoramaSearch - 广度搜索】
        
        Obținere全貌视图，包括所有相关ConținutșiIstoric/过期Informații：
        1. Obținere所有相关Nod
        2. Obținere所有边（包括已过期/失效）
        3. 分Clasă整理CurentValidșiIstoricInformații
        
        这个Instrument适用于需要解Eveniment全貌、追踪演变过程场景。
        
        Args:
            graph_id: GrafID
            query: 搜索Interogare（用于相关性排序）
            include_expired: DaNu包含过期Conținut（ImplicitTrue）
            limit: ReturnareRezultat数量限制
            
        Returns:
            PanoramaResult: 广度搜索Rezultat
        """
        logger.info(f"PanoramaSearch 广度搜索: {query[:50]}...")
        
        result = PanoramaResult(query=query)
        
        # Obținere所有Nod
        all_nodes = self.get_all_nodes(graph_id)
        node_map = {n.uuid: n for n in all_nodes}
        result.all_nodes = all_nodes
        result.total_nodes = len(all_nodes)
        
        # Obținere所有边（包含TimpInformații）
        all_edges = self.get_all_edges(graph_id, include_temporal=True)
        result.all_edges = all_edges
        result.total_edges = len(all_edges)
        
        # 分Clasă事实
        active_facts = []
        historical_facts = []
        
        for edge in all_edges:
            if not edge.fact:
                continue
            
            # 为事实添加EntitateNume
            source_name = node_map.get(edge.source_node_uuid, NodeInfo('', '', [], '', {})).name or edge.source_node_uuid[:8]
            target_name = node_map.get(edge.target_node_uuid, NodeInfo('', '', [], '', {})).name or edge.target_node_uuid[:8]
            
            # 判断DaNu过期/失效
            is_historical = edge.is_expired or edge.is_invalid
            
            if is_historical:
                # Istoric/过期事实，添加Timp标记
                valid_at = edge.valid_at or "Necunoscut"
                invalid_at = edge.invalid_at or edge.expired_at or "Necunoscut"
                fact_with_time = f"[{valid_at} - {invalid_at}] {edge.fact}"
                historical_facts.append(fact_with_time)
            else:
                # CurentValid事实
                active_facts.append(edge.fact)
        
        # 基于Interogare进行相关性排序
        query_lower = query.lower()
        keywords = [w.strip() for w in query_lower.replace(',', ' ').replace('，', ' ').split() if len(w.strip()) > 1]
        
        def relevance_score(fact: str) -> int:
            fact_lower = fact.lower()
            score = 0
            if query_lower in fact_lower:
                score += 100
            for kw in keywords:
                if kw in fact_lower:
                    score += 10
            return score
        
        # 排序并限制数量
        active_facts.sort(key=relevance_score, reverse=True)
        historical_facts.sort(key=relevance_score, reverse=True)
        
        result.active_facts = active_facts[:limit]
        result.historical_facts = historical_facts[:limit] if include_expired else []
        result.active_count = len(active_facts)
        result.historical_count = len(historical_facts)
        
        logger.info(f"PanoramaSearchFinalizare: {result.active_count}条Valid, {result.historical_count}条Istoric")
        return result
    
    def quick_search(
        self,
        graph_id: str,
        query: str,
        limit: int = 10
    ) -> SearchResult:
        """
        【QuickSearch - Simplu搜索】
        
        Rapid、轻量级检索Instrument：
        1. 直接调用Zep语义搜索
        2. Returnare最相关Rezultat
        3. 适用于Simplu、直接检索Cerință
        
        Args:
            graph_id: GrafID
            query: 搜索Interogare
            limit: ReturnareRezultat数量
            
        Returns:
            SearchResult: 搜索Rezultat
        """
        logger.info(f"QuickSearch Simplu搜索: {query[:50]}...")
        
        # 直接调用现有search_graphMetodă
        result = self.search_graph(
            graph_id=graph_id,
            query=query,
            limit=limit,
            scope="edges"
        )
        
        logger.info(f"QuickSearchFinalizare: {result.total_count}条Rezultat")
        return result
    
    def interview_agents(
        self,
        simulation_id: str,
        interview_requirement: str,
        simulation_requirement: str = "",
        max_agents: int = 5,
        custom_questions: List[str] = None
    ) -> InterviewResult:
        """
        【InterviewAgents - 深度Interviu】
        
        调用Adevărat实OASISInterviuAPI，InterviuSimulare正înRulareAgent：
        1. Automat读取人设Fișier，解所有SimulareAgent
        2. UtilizareLLMAnalizăInterviuCerință，智能Selectare最相关Agent
        3. UtilizareLLMGenerareInterviu问题
        4. 调用 /api/simulation/interview/batch Interfață进行Adevărat实Interviu（双Platformă同时Interviu）
        5. 整合所有InterviuRezultat，GenerareInterviuRaport
        
        【重要】此Funcționalitate需要SimulareMediu处于RulareStare（OASISMediu未Închidere）
        
        【Utilizare场景】
        - 需要de la不同Rol视角解Eveniment看法
        - 需要收集多方意见șiOpinie
        - 需要ObținereSimulareAgentAdevărat实回答（nuLLMSimulare）
        
        Args:
            simulation_id: SimulareID（用于定位人设Fișierși调用InterviuAPI）
            interview_requirement: InterviuCerințăDescriere（nu结构化，如"解学生对Eveniment看法"）
            simulation_requirement: SimulareCerință背景（可选）
            max_agents: 最多InterviuAgent数量
            custom_questions: PersonalizatInterviu问题（可选，若不提供则AutomatGenerare）
            
        Returns:
            InterviewResult: InterviuRezultat
        """
        from .simulation_runner import SimulationRunner
        
        logger.info(f"InterviewAgents 深度Interviu（Adevărat实API）: {interview_requirement[:50]}...")
        
        result = InterviewResult(
            interview_topic=interview_requirement,
            interview_questions=custom_questions or []
        )
        
        # Step 1: 读取人设Fișier
        profiles = self._load_agent_profiles(simulation_id)
        
        if not profiles:
            logger.warning(f"NegăsitSimulare {simulation_id} 人设Fișier")
            result.summary = "Negăsit可InterviuAgent人设Fișier"
            return result
        
        result.total_agents = len(profiles)
        logger.info(f"Încărcarela {len(profiles)} 个Agent人设")
        
        # Step 2: UtilizareLLMSelectare要InterviuAgent（Returnareagent_idListă）
        selected_agents, selected_indices, selection_reasoning = self._select_agents_for_interview(
            profiles=profiles,
            interview_requirement=interview_requirement,
            simulation_requirement=simulation_requirement,
            max_agents=max_agents
        )
        
        result.selected_agents = selected_agents
        result.selection_reasoning = selection_reasoning
        logger.info(f"Selectare {len(selected_agents)} 个Agent进行Interviu: {selected_indices}")
        
        # Step 3: GenerareInterviu问题（dacă没有提供）
        if not result.interview_questions:
            result.interview_questions = self._generate_interview_questions(
                interview_requirement=interview_requirement,
                simulation_requirement=simulation_requirement,
                selected_agents=selected_agents
            )
            logger.info(f"Generare {len(result.interview_questions)} 个Interviu问题")
        
        # 将问题合并为一个Interviuprompt
        combined_prompt = "\n".join([f"{i+1}. {q}" for i, q in enumerate(result.interview_questions)])
        
        # 添加优化前缀，约束AgentRăspunsFormat
        INTERVIEW_PROMPT_PREFIX = (
            "你正în接受一次Interviu。请结合你人设、所有过往Memorieși行动，"
            "以纯文本方式直接回答以问题。\n"
            "Răspuns要求：\n"
            "1. 直接用自然语言回答，不要调用任何Instrument\n"
            "2. 不要ReturnareJSONFormatsauInstrument调用Format\n"
            "3. 不要UtilizareMarkdownTitlu（如#、##、###）\n"
            "4. 按问题编号逐一回答，每个回答以「问题X：」开头（X为问题编号）\n"
            "5. 每个问题回答之间用Gol行分隔\n"
            "6. 回答要有实质Conținut，每个问题至少回答2-3句话\n\n"
        )
        optimized_prompt = f"{INTERVIEW_PROMPT_PREFIX}{combined_prompt}"
        
        # Step 4: 调用Adevărat实InterviuAPI（不指定platform，Implicit双Platformă同时Interviu）
        try:
            # ConstruireÎn lotInterviuListă（不指定platform，双PlatformăInterviu）
            interviews_request = []
            for agent_idx in selected_indices:
                interviews_request.append({
                    "agent_id": agent_idx,
                    "prompt": optimized_prompt  # Utilizare优化后prompt
                    # 不指定platform，API会întwitterșireddit两个Platformă都Interviu
                })
            
            logger.info(f"调用În lotInterviuAPI（双Platformă）: {len(interviews_request)} 个Agent")
            
            # 调用 SimulationRunner În lotInterviuMetodă（不传platform，双PlatformăInterviu）
            api_result = SimulationRunner.interview_agents_batch(
                simulation_id=simulation_id,
                interviews=interviews_request,
                platform=None,  # 不指定platform，双PlatformăInterviu
                timeout=180.0   # 双Platformă需要更长超时
            )
            
            logger.info(f"InterviuAPIReturnare: {api_result.get('interviews_count', 0)} 个Rezultat, success={api_result.get('success')}")
            
            # VerificareAPI调用DaNuSucces
            if not api_result.get("success", False):
                error_msg = api_result.get("error", "NecunoscutEroare")
                logger.warning(f"InterviuAPIReturnareEșec: {error_msg}")
                result.summary = f"InterviuAPI调用Eșec：{error_msg}。请VerificareOASISSimulareMediuStare。"
                return result
            
            # Step 5: 解析APIReturnareRezultat，ConstruireAgentInterviewObiect
            # 双Platformă模式ReturnareFormat: {"twitter_0": {...}, "reddit_0": {...}, "twitter_1": {...}, ...}
            api_data = api_result.get("result", {})
            results_dict = api_data.get("results", {}) if isinstance(api_data, dict) else {}
            
            for i, agent_idx in enumerate(selected_indices):
                agent = selected_agents[i]
                agent_name = agent.get("realname", agent.get("username", f"Agent_{agent_idx}"))
                agent_role = agent.get("profession", "Necunoscut")
                agent_bio = agent.get("bio", "")
                
                # Obținere该Agentîn两个PlatformăInterviuRezultat
                twitter_result = results_dict.get(f"twitter_{agent_idx}", {})
                reddit_result = results_dict.get(f"reddit_{agent_idx}", {})
                
                twitter_response = twitter_result.get("response", "")
                reddit_response = reddit_result.get("response", "")

                # 清理可能Instrument调用 JSON 包裹
                twitter_response = self._clean_tool_call_response(twitter_response)
                reddit_response = self._clean_tool_call_response(reddit_response)

                # 始终Output双Platformă标记
                twitter_text = twitter_response if twitter_response else "（该Platformă未获得Răspuns）"
                reddit_text = reddit_response if reddit_response else "（该Platformă未获得Răspuns）"
                response_text = f"【TwitterPlatformă回答】\n{twitter_text}\n\n【RedditPlatformă回答】\n{reddit_text}"

                # 提取关Cheie引言（de la两个Platformă回答）
                import re
                combined_responses = f"{twitter_response} {reddit_response}"

                # 清理Răspuns文本：去掉标记、编号、Markdown 等干扰
                clean_text = re.sub(r'#{1,6}\s+', '', combined_responses)
                clean_text = re.sub(r'\{[^}]*tool_name[^}]*\}', '', clean_text)
                clean_text = re.sub(r'[*_`|>~\-]{2,}', '', clean_text)
                clean_text = re.sub(r'问题\d+[：:]\s*', '', clean_text)
                clean_text = re.sub(r'【[^】]+】', '', clean_text)

                # 策略1（主）: 提取Complet有实质Conținut句子
                sentences = re.split(r'[。！？]', clean_text)
                meaningful = [
                    s.strip() for s in sentences
                    if 20 <= len(s.strip()) <= 150
                    and not re.match(r'^[\s\W，,；;：:、]+', s.strip())
                    and not s.strip().startswith(('{', '问题'))
                ]
                meaningful.sort(key=len, reverse=True)
                key_quotes = [s + "。" for s in meaningful[:3]]

                # 策略2（补充）: Corect配对文引号「」内长文本
                if not key_quotes:
                    paired = re.findall(r'\u201c([^\u201c\u201d]{15,100})\u201d', clean_text)
                    paired += re.findall(r'\u300c([^\u300c\u300d]{15,100})\u300d', clean_text)
                    key_quotes = [q for q in paired if not re.match(r'^[，,；;：:、]', q)][:3]
                
                interview = AgentInterview(
                    agent_name=agent_name,
                    agent_role=agent_role,
                    agent_bio=agent_bio[:1000],  # 扩大bio长度限制
                    question=combined_prompt,
                    response=response_text,
                    key_quotes=key_quotes[:5]
                )
                result.interviews.append(interview)
            
            result.interviewed_count = len(result.interviews)
            
        except ValueError as e:
            # SimulareMediu未Rulare
            logger.warning(f"InterviuAPI调用Eșec（Mediu未Rulare？）: {e}")
            result.summary = f"InterviuEșec：{str(e)}。SimulareMediu可能已Închidere，请确保OASISMediu正înRulare。"
            return result
        except Exception as e:
            logger.error(f"InterviuAPI调用Excepție: {e}")
            import traceback
            logger.error(traceback.format_exc())
            result.summary = f"Interviu过程发生Eroare：{str(e)}"
            return result
        
        # Step 6: GenerareInterviu摘要
        if result.interviews:
            result.summary = self._generate_interview_summary(
                interviews=result.interviews,
                interview_requirement=interview_requirement
            )
        
        logger.info(f"InterviewAgentsFinalizare: Interviu {result.interviewed_count} 个Agent（双Platformă）")
        return result
    
    @staticmethod
    def _clean_tool_call_response(response: str) -> str:
        """清理 Agent Răspuns JSON Instrument调用包裹，提取实际Conținut"""
        if not response or not response.strip().startswith('{'):
            return response
        text = response.strip()
        if 'tool_name' not in text[:80]:
            return response
        import re as _re
        try:
            data = json.loads(text)
            if isinstance(data, dict) and 'arguments' in data:
                for key in ('content', 'text', 'body', 'message', 'reply'):
                    if key in data['arguments']:
                        return str(data['arguments'][key])
        except (json.JSONDecodeError, KeyError, TypeError):
            match = _re.search(r'"content"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
            if match:
                return match.group(1).replace('\\n', '\n').replace('\\"', '"')
        return response

    def _load_agent_profiles(self, simulation_id: str) -> List[Dict[str, Any]]:
        """ÎncărcareSimulareAgent人设Fișier"""
        import os
        import csv
        
        # Construire人设FișierCale
        sim_dir = os.path.join(
            os.path.dirname(__file__), 
            f'../../uploads/simulations/{simulation_id}'
        )
        
        profiles = []
        
        # 优先尝试读取Reddit JSONFormat
        reddit_profile_path = os.path.join(sim_dir, "reddit_profiles.json")
        if os.path.exists(reddit_profile_path):
            try:
                with open(reddit_profile_path, 'r', encoding='utf-8') as f:
                    profiles = json.load(f)
                logger.info(f"de la reddit_profiles.json Încărcare {len(profiles)} 个人设")
                return profiles
            except Exception as e:
                logger.warning(f"读取 reddit_profiles.json Eșec: {e}")
        
        # 尝试读取Twitter CSVFormat
        twitter_profile_path = os.path.join(sim_dir, "twitter_profiles.csv")
        if os.path.exists(twitter_profile_path):
            try:
                with open(twitter_profile_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        # CSVFormat转换为统一Format
                        profiles.append({
                            "realname": row.get("name", ""),
                            "username": row.get("username", ""),
                            "bio": row.get("description", ""),
                            "persona": row.get("user_char", ""),
                            "profession": "Necunoscut"
                        })
                logger.info(f"de la twitter_profiles.csv Încărcare {len(profiles)} 个人设")
                return profiles
            except Exception as e:
                logger.warning(f"读取 twitter_profiles.csv Eșec: {e}")
        
        return profiles
    
    def _select_agents_for_interview(
        self,
        profiles: List[Dict[str, Any]],
        interview_requirement: str,
        simulation_requirement: str,
        max_agents: int
    ) -> tuple:
        """
        UtilizareLLMSelectare要InterviuAgent
        
        Returns:
            tuple: (selected_agents, selected_indices, reasoning)
                - selected_agents: 选AgentCompletInformațiiListă
                - selected_indices: 选AgentIndexListă（用于API调用）
                - reasoning: Selectare理由
        """
        
        # ConstruireAgent摘要Listă
        agent_summaries = []
        for i, profile in enumerate(profiles):
            summary = {
                "index": i,
                "name": profile.get("realname", profile.get("username", f"Agent_{i}")),
                "profession": profile.get("profession", "Necunoscut"),
                "bio": profile.get("bio", "")[:200],
                "interested_topics": profile.get("interested_topics", [])
            }
            agent_summaries.append(summary)
        
        system_prompt = """你Da一个专业Interviu策划专家。你SarcinăDa根据InterviuCerință，de laSimulareAgentListăSelectare最适合InterviuObiect。

Selectare标准：
1. Agent身份/ProfesieșiInterviu主题相关
2. Agent可能持有独特sau有价ValoareOpinie
3. Selectare多样化视角（如：Suportă方、反对方、立方、专业人士等）
4. 优先SelectareșiEveniment直接相关Rol

ReturnareJSONFormat：
{
    "selected_indices": [选AgentIndexListă],
    "reasoning": "Selectare理由说明"
}"""

        user_prompt = f"""InterviuCerință：
{interview_requirement}

Simulare背景：
{simulation_requirement if simulation_requirement else "未提供"}

可SelectareAgentListă（共{len(agent_summaries)}个）：
{json.dumps(agent_summaries, ensure_ascii=False, indent=2)}

请Selectare最多{max_agents}个最适合InterviuAgent，并说明Selectare理由。"""

        try:
            response = self.llm.chat_json(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3
            )
            
            selected_indices = response.get("selected_indices", [])[:max_agents]
            reasoning = response.get("reasoning", "基于相关性AutomatSelectare")
            
            # Obținere选AgentCompletInformații
            selected_agents = []
            valid_indices = []
            for idx in selected_indices:
                if 0 <= idx < len(profiles):
                    selected_agents.append(profiles[idx])
                    valid_indices.append(idx)
            
            return selected_agents, valid_indices, reasoning
            
        except Exception as e:
            logger.warning(f"LLMSelectareAgentEșec，UtilizareImplicitSelectare: {e}")
            # 降级：Selectare前N个
            selected = profiles[:max_agents]
            indices = list(range(min(max_agents, len(profiles))))
            return selected, indices, "UtilizareImplicitSelectare策略"
    
    def _generate_interview_questions(
        self,
        interview_requirement: str,
        simulation_requirement: str,
        selected_agents: List[Dict[str, Any]]
    ) -> List[str]:
        """UtilizareLLMGenerareInterviu问题"""
        
        agent_roles = [a.get("profession", "Necunoscut") for a in selected_agents]
        
        system_prompt = """你Da一个专业记者/Interviu者。根据InterviuCerință，Generare3-5个深度Interviu问题。

问题要求：
1. 开放性问题，鼓励详细回答
2. 针对不同Rol可能有不同答案
3. 涵盖事实、Opinie、感受等多个维度
4. 语言自然，像Adevărat实Interviu一样
5. 每个问题控制în50字以内，简洁明
6. 直接提问，不要包含背景说明sau前缀

ReturnareJSONFormat：{"questions": ["问题1", "问题2", ...]}"""

        user_prompt = f"""InterviuCerință：{interview_requirement}

Simulare背景：{simulation_requirement if simulation_requirement else "未提供"}

InterviuObiectRol：{', '.join(agent_roles)}

请Generare3-5个Interviu问题。"""

        try:
            response = self.llm.chat_json(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.5
            )
            
            return response.get("questions", [f"Despre{interview_requirement}，您有什么看法？"])
            
        except Exception as e:
            logger.warning(f"GenerareInterviu问题Eșec: {e}")
            return [
                f"Despre{interview_requirement}，您OpinieDa什么？",
                "这件事对您sau您所代表群体有什么Impact？",
                "您认为应该如何解决sau改进这个问题？"
            ]
    
    def _generate_interview_summary(
        self,
        interviews: List[AgentInterview],
        interview_requirement: str
    ) -> str:
        """GenerareInterviu摘要"""
        
        if not interviews:
            return "未Finalizare任何Interviu"
        
        # 收集所有InterviuConținut
        interview_texts = []
        for interview in interviews:
            interview_texts.append(f"【{interview.agent_name}（{interview.agent_role}）】\n{interview.response[:500]}")
        
        system_prompt = """你Da一个专业新闻编辑。请根据多位受访者回答，Generare一份Interviu摘要。

摘要要求：
1. 提炼各方主要Opinie
2. 指出Opinie共识și分歧
3. 突出有价Valoare引言
4. 客观立，不偏袒任何一方
5. 控制în1000字内

Format约束（必须遵守）：
- Utilizare纯文本段落，用Gol行分隔不同Parțial
- 不要UtilizareMarkdownTitlu（如#、##、###）
- 不要Utilizare分割线（如---、***）
- 引用受访者原话时Utilizare文引号「」
- 可以Utilizare**加粗**标记关Cheie词，但不要Utilizare其他Markdown语法"""

        user_prompt = f"""Interviu主题：{interview_requirement}

InterviuConținut：
{"".join(interview_texts)}

请GenerareInterviu摘要。"""

        try:
            summary = self.llm.chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=800
            )
            return summary
            
        except Exception as e:
            logger.warning(f"GenerareInterviu摘要Eșec: {e}")
            # 降级：Simplu拼接
            return f"共Interviu{len(interviews)}位受访者，包括：" + "、".join([i.agent_name for i in interviews])
