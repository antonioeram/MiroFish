"""
OASIS Agent ProfileGenerare器
将ZepGrafEntitate转换为OASISSimularePlatformă所需Agent ProfileFormat

优化改进：
1. 调用Zep检索Funcționalitate二次丰富NodInformații
2. 优化Indicație词Generarenu常详细人设
3. 区分个人Entitateși抽象群体Entitate
"""

import json
import random
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

from openai import OpenAI
from zep_cloud.client import Zep

from ..config import Config
from ..utils.logger import get_logger
from .zep_entity_reader import EntityNode, ZepEntityReader

logger = get_logger('mirofish.oasis_profile')


@dataclass
class OasisAgentProfile:
    """OASIS Agent ProfileDate结构"""
    # 通用字段
    user_id: int
    user_name: str
    name: str
    bio: str
    persona: str
    
    # 可选字段 - Reddit风格
    karma: int = 1000
    
    # 可选字段 - Twitter风格
    friend_count: int = 100
    follower_count: int = 150
    statuses_count: int = 500
    
    # 额外人设Informații
    age: Optional[int] = None
    gender: Optional[str] = None
    mbti: Optional[str] = None
    country: Optional[str] = None
    profession: Optional[str] = None
    interested_topics: List[str] = field(default_factory=list)
    
    # 来源EntitateInformații
    source_entity_uuid: Optional[str] = None
    source_entity_type: Optional[str] = None
    
    created_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    
    def to_reddit_format(self) -> Dict[str, Any]:
        """转换为RedditPlatformăFormat"""
        profile = {
            "user_id": self.user_id,
            "username": self.user_name,  # OASIS 库要求字段名为 username（无划线）
            "name": self.name,
            "bio": self.bio,
            "persona": self.persona,
            "karma": self.karma,
            "created_at": self.created_at,
        }
        
        # 添加额外人设Informații（dacă有）
        if self.age:
            profile["age"] = self.age
        if self.gender:
            profile["gender"] = self.gender
        if self.mbti:
            profile["mbti"] = self.mbti
        if self.country:
            profile["country"] = self.country
        if self.profession:
            profile["profession"] = self.profession
        if self.interested_topics:
            profile["interested_topics"] = self.interested_topics
        
        return profile
    
    def to_twitter_format(self) -> Dict[str, Any]:
        """转换为TwitterPlatformăFormat"""
        profile = {
            "user_id": self.user_id,
            "username": self.user_name,  # OASIS 库要求字段名为 username（无划线）
            "name": self.name,
            "bio": self.bio,
            "persona": self.persona,
            "friend_count": self.friend_count,
            "follower_count": self.follower_count,
            "statuses_count": self.statuses_count,
            "created_at": self.created_at,
        }
        
        # 添加额外人设Informații
        if self.age:
            profile["age"] = self.age
        if self.gender:
            profile["gender"] = self.gender
        if self.mbti:
            profile["mbti"] = self.mbti
        if self.country:
            profile["country"] = self.country
        if self.profession:
            profile["profession"] = self.profession
        if self.interested_topics:
            profile["interested_topics"] = self.interested_topics
        
        return profile
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为CompletDicționarFormat"""
        return {
            "user_id": self.user_id,
            "user_name": self.user_name,
            "name": self.name,
            "bio": self.bio,
            "persona": self.persona,
            "karma": self.karma,
            "friend_count": self.friend_count,
            "follower_count": self.follower_count,
            "statuses_count": self.statuses_count,
            "age": self.age,
            "gender": self.gender,
            "mbti": self.mbti,
            "country": self.country,
            "profession": self.profession,
            "interested_topics": self.interested_topics,
            "source_entity_uuid": self.source_entity_uuid,
            "source_entity_type": self.source_entity_type,
            "created_at": self.created_at,
        }


class OasisProfileGenerator:
    """
    OASIS ProfileGenerare器
    
    将ZepGrafEntitate转换为OASISSimulare所需Agent Profile
    
    优化特性：
    1. 调用ZepGraf检索FuncționalitateObținere更丰富文
    2. Generarenu常详细人设（包括基本Informații、Profesie经历、性格特征、社交媒体Comportament等）
    3. 区分个人Entitateși抽象群体Entitate
    """
    
    # MBTITipListă
    MBTI_TYPES = [
        "INTJ", "INTP", "ENTJ", "ENTP",
        "INFJ", "INFP", "ENFJ", "ENFP",
        "ISTJ", "ISFJ", "ESTJ", "ESFJ",
        "ISTP", "ISFP", "ESTP", "ESFP"
    ]
    
    # 常见国家Listă
    COUNTRIES = [
        "China", "US", "UK", "Japan", "Germany", "France", 
        "Canada", "Australia", "Brazil", "India", "South Korea"
    ]
    
    # 个人TipEntitate（需要Generare具体人设）
    INDIVIDUAL_ENTITY_TYPES = [
        "student", "alumni", "professor", "person", "publicfigure", 
        "expert", "faculty", "official", "journalist", "activist"
    ]
    
    # 群体/机构TipEntitate（需要Generare群体代表人设）
    GROUP_ENTITY_TYPES = [
        "university", "governmentagency", "organization", "ngo", 
        "mediaoutlet", "company", "institution", "group", "community"
    ]
    
    def __init__(
        self, 
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None,
        zep_api_key: Optional[str] = None,
        graph_id: Optional[str] = None
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
        
        # Zep客户端用于检索丰富文
        self.zep_api_key = zep_api_key or Config.ZEP_API_KEY
        self.zep_client = None
        self.graph_id = graph_id
        
        if self.zep_api_key:
            try:
                self.zep_client = Zep(api_key=self.zep_api_key)
            except Exception as e:
                logger.warning(f"Zep客户端InițializareEșec: {e}")
    
    def generate_profile_from_entity(
        self, 
        entity: EntityNode, 
        user_id: int,
        use_llm: bool = True
    ) -> OasisAgentProfile:
        """
        de laZepEntitateGenerareOASIS Agent Profile
        
        Args:
            entity: ZepEntitateNod
            user_id: UtilizatorID（用于OASIS）
            use_llm: DaNuUtilizareLLMGenerare详细人设
            
        Returns:
            OasisAgentProfile
        """
        entity_type = entity.get_entity_type() or "Entity"
        
        # 基础Informații
        name = entity.name
        user_name = self._generate_username(name)
        
        # Construire文Informații
        context = self._build_entity_context(entity)
        
        if use_llm:
            # UtilizareLLMGenerare详细人设
            profile_data = self._generate_profile_with_llm(
                entity_name=name,
                entity_type=entity_type,
                entity_summary=entity.summary,
                entity_attributes=entity.attributes,
                context=context
            )
        else:
            # Utilizare规则Generare基础人设
            profile_data = self._generate_profile_rule_based(
                entity_name=name,
                entity_type=entity_type,
                entity_summary=entity.summary,
                entity_attributes=entity.attributes
            )
        
        return OasisAgentProfile(
            user_id=user_id,
            user_name=user_name,
            name=name,
            bio=profile_data.get("bio", f"{entity_type}: {name}"),
            persona=profile_data.get("persona", entity.summary or f"A {entity_type} named {name}."),
            karma=profile_data.get("karma", random.randint(500, 5000)),
            friend_count=profile_data.get("friend_count", random.randint(50, 500)),
            follower_count=profile_data.get("follower_count", random.randint(100, 1000)),
            statuses_count=profile_data.get("statuses_count", random.randint(100, 2000)),
            age=profile_data.get("age"),
            gender=profile_data.get("gender"),
            mbti=profile_data.get("mbti"),
            country=profile_data.get("country"),
            profession=profile_data.get("profession"),
            interested_topics=profile_data.get("interested_topics", []),
            source_entity_uuid=entity.uuid,
            source_entity_type=entity_type,
        )
    
    def _generate_username(self, name: str) -> str:
        """GenerareUtilizator名"""
        # 移除特殊字符，转换为小写
        username = name.lower().replace(" ", "_")
        username = ''.join(c for c in username if c.isalnum() or c == '_')
        
        # 添加随机后缀避免重复
        suffix = random.randint(100, 999)
        return f"{username}_{suffix}"
    
    def _search_zep_for_entity(self, entity: EntityNode) -> Dict[str, Any]:
        """
        UtilizareZepGraf混合搜索FuncționalitateObținereEntitate相关丰富Informații
        
        Zep没有内置混合搜索Interfață，需要分别搜索edgesșinodes然后合并Rezultat。
        UtilizareParalelCerere同时搜索，提高效率。
        
        Args:
            entity: EntitateNodObiect
            
        Returns:
            包含facts, node_summaries, contextDicționar
        """
        import concurrent.futures
        
        if not self.zep_client:
            return {"facts": [], "node_summaries": [], "context": ""}
        
        entity_name = entity.name
        
        results = {
            "facts": [],
            "node_summaries": [],
            "context": ""
        }
        
        # 必须有graph_id才能进行搜索
        if not self.graph_id:
            logger.debug(f"跳过Zep检索：未Setărigraph_id")
            return results
        
        comprehensive_query = f"Despre{entity_name}所有Informații、活动、Eveniment、Relațieși背景"
        
        def search_edges():
            """搜索边（事实/Relație）- 带Reîncercare机制"""
            max_retries = 3
            last_exception = None
            delay = 2.0
            
            for attempt in range(max_retries):
                try:
                    return self.zep_client.graph.search(
                        query=comprehensive_query,
                        graph_id=self.graph_id,
                        limit=30,
                        scope="edges",
                        reranker="rrf"
                    )
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.debug(f"Zep边搜索第 {attempt + 1} 次Eșec: {str(e)[:80]}, Reîncercare...")
                        time.sleep(delay)
                        delay *= 2
                    else:
                        logger.debug(f"Zep边搜索în {max_retries} 次尝试后仍Eșec: {e}")
            return None
        
        def search_nodes():
            """搜索Nod（Entitate摘要）- 带Reîncercare机制"""
            max_retries = 3
            last_exception = None
            delay = 2.0
            
            for attempt in range(max_retries):
                try:
                    return self.zep_client.graph.search(
                        query=comprehensive_query,
                        graph_id=self.graph_id,
                        limit=20,
                        scope="nodes",
                        reranker="rrf"
                    )
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.debug(f"ZepNod搜索第 {attempt + 1} 次Eșec: {str(e)[:80]}, Reîncercare...")
                        time.sleep(delay)
                        delay *= 2
                    else:
                        logger.debug(f"ZepNod搜索în {max_retries} 次尝试后仍Eșec: {e}")
            return None
        
        try:
            # Paralel执行edgesșinodes搜索
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                edge_future = executor.submit(search_edges)
                node_future = executor.submit(search_nodes)
                
                # ObținereRezultat
                edge_result = edge_future.result(timeout=30)
                node_result = node_future.result(timeout=30)
            
            # Procesare边搜索Rezultat
            all_facts = set()
            if edge_result and hasattr(edge_result, 'edges') and edge_result.edges:
                for edge in edge_result.edges:
                    if hasattr(edge, 'fact') and edge.fact:
                        all_facts.add(edge.fact)
            results["facts"] = list(all_facts)
            
            # ProcesareNod搜索Rezultat
            all_summaries = set()
            if node_result and hasattr(node_result, 'nodes') and node_result.nodes:
                for node in node_result.nodes:
                    if hasattr(node, 'summary') and node.summary:
                        all_summaries.add(node.summary)
                    if hasattr(node, 'name') and node.name and node.name != entity_name:
                        all_summaries.add(f"相关Entitate: {node.name}")
            results["node_summaries"] = list(all_summaries)
            
            # Construire综合文
            context_parts = []
            if results["facts"]:
                context_parts.append("事实Informații:\n" + "\n".join(f"- {f}" for f in results["facts"][:20]))
            if results["node_summaries"]:
                context_parts.append("相关Entitate:\n" + "\n".join(f"- {s}" for s in results["node_summaries"][:10]))
            results["context"] = "\n\n".join(context_parts)
            
            logger.info(f"Zep混合检索Finalizare: {entity_name}, Obținere {len(results['facts'])} 条事实, {len(results['node_summaries'])} 个相关Nod")
            
        except concurrent.futures.TimeoutError:
            logger.warning(f"Zep检索超时 ({entity_name})")
        except Exception as e:
            logger.warning(f"Zep检索Eșec ({entity_name}): {e}")
        
        return results
    
    def _build_entity_context(self, entity: EntityNode) -> str:
        """
        ConstruireEntitateComplet文Informații
        
        包括：
        1. Entitate本身边Informații（事实）
        2. 关联Nod详细Informații
        3. Zep混合检索la丰富Informații
        """
        context_parts = []
        
        # 1. 添加EntitateProprietateInformații
        if entity.attributes:
            attrs = []
            for key, value in entity.attributes.items():
                if value and str(value).strip():
                    attrs.append(f"- {key}: {value}")
            if attrs:
                context_parts.append("### EntitateProprietate\n" + "\n".join(attrs))
        
        # 2. 添加相关边Informații（事实/Relație）
        existing_facts = set()
        if entity.related_edges:
            relationships = []
            for edge in entity.related_edges:  # 不限制数量
                fact = edge.get("fact", "")
                edge_name = edge.get("edge_name", "")
                direction = edge.get("direction", "")
                
                if fact:
                    relationships.append(f"- {fact}")
                    existing_facts.add(fact)
                elif edge_name:
                    if direction == "outgoing":
                        relationships.append(f"- {entity.name} --[{edge_name}]--> (相关Entitate)")
                    else:
                        relationships.append(f"- (相关Entitate) --[{edge_name}]--> {entity.name}")
            
            if relationships:
                context_parts.append("### 相关事实șiRelație\n" + "\n".join(relationships))
        
        # 3. 添加关联Nod详细Informații
        if entity.related_nodes:
            related_info = []
            for node in entity.related_nodes:  # 不限制数量
                node_name = node.get("name", "")
                node_labels = node.get("labels", [])
                node_summary = node.get("summary", "")
                
                # 过滤掉Implicit标签
                custom_labels = [l for l in node_labels if l not in ["Entity", "Node"]]
                label_str = f" ({', '.join(custom_labels)})" if custom_labels else ""
                
                if node_summary:
                    related_info.append(f"- **{node_name}**{label_str}: {node_summary}")
                else:
                    related_info.append(f"- **{node_name}**{label_str}")
            
            if related_info:
                context_parts.append("### 关联EntitateInformații\n" + "\n".join(related_info))
        
        # 4. UtilizareZep混合检索Obținere更丰富Informații
        zep_results = self._search_zep_for_entity(entity)
        
        if zep_results.get("facts"):
            # 去重：排除已存în事实
            new_facts = [f for f in zep_results["facts"] if f not in existing_facts]
            if new_facts:
                context_parts.append("### Zep检索la事实Informații\n" + "\n".join(f"- {f}" for f in new_facts[:15]))
        
        if zep_results.get("node_summaries"):
            context_parts.append("### Zep检索la相关Nod\n" + "\n".join(f"- {s}" for s in zep_results["node_summaries"][:10]))
        
        return "\n\n".join(context_parts)
    
    def _is_individual_entity(self, entity_type: str) -> bool:
        """判断DaNuDa个人TipEntitate"""
        return entity_type.lower() in self.INDIVIDUAL_ENTITY_TYPES
    
    def _is_group_entity(self, entity_type: str) -> bool:
        """判断DaNuDa群体/机构TipEntitate"""
        return entity_type.lower() in self.GROUP_ENTITY_TYPES
    
    def _generate_profile_with_llm(
        self,
        entity_name: str,
        entity_type: str,
        entity_summary: str,
        entity_attributes: Dict[str, Any],
        context: str
    ) -> Dict[str, Any]:
        """
        UtilizareLLMGenerarenu常详细人设
        
        根据EntitateTip区分：
        - 个人Entitate：Generare具体人物设定
        - 群体/机构Entitate：Generare代表性账号设定
        """
        
        is_individual = self._is_individual_entity(entity_type)
        
        if is_individual:
            prompt = self._build_individual_persona_prompt(
                entity_name, entity_type, entity_summary, entity_attributes, context
            )
        else:
            prompt = self._build_group_persona_prompt(
                entity_name, entity_type, entity_summary, entity_attributes, context
            )

        # 尝试多次Generare，直laSuccessau达la最大Reîncercare次数
        max_attempts = 3
        last_error = None
        
        for attempt in range(max_attempts):
            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": self._get_system_prompt(is_individual)},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.7 - (attempt * 0.1)  # 每次Reîncercare降低温度
                    # 不Setărimax_tokens，让LLM自由发挥
                )
                
                content = response.choices[0].message.content
                
                # VerificareDaNu被截断（finish_reason不Da'stop'）
                finish_reason = response.choices[0].finish_reason
                if finish_reason == 'length':
                    logger.warning(f"LLMOutput被截断 (attempt {attempt+1}), 尝试修复...")
                    content = self._fix_truncated_json(content)
                
                # 尝试解析JSON
                try:
                    result = json.loads(content)
                    
                    # Verificare必需字段
                    if "bio" not in result or not result["bio"]:
                        result["bio"] = entity_summary[:200] if entity_summary else f"{entity_type}: {entity_name}"
                    if "persona" not in result or not result["persona"]:
                        result["persona"] = entity_summary or f"{entity_name}Da一个{entity_type}。"
                    
                    return result
                    
                except json.JSONDecodeError as je:
                    logger.warning(f"JSON解析Eșec (attempt {attempt+1}): {str(je)[:80]}")
                    
                    # 尝试修复JSON
                    result = self._try_fix_json(content, entity_name, entity_type, entity_summary)
                    if result.get("_fixed"):
                        del result["_fixed"]
                        return result
                    
                    last_error = je
                    
            except Exception as e:
                logger.warning(f"LLM调用Eșec (attempt {attempt+1}): {str(e)[:80]}")
                last_error = e
                import time
                time.sleep(1 * (attempt + 1))  # 指数退避
        
        logger.warning(f"LLMGenerare人设Eșec（{max_attempts}次尝试）: {last_error}, Utilizare规则Generare")
        return self._generate_profile_rule_based(
            entity_name, entity_type, entity_summary, entity_attributes
        )
    
    def _fix_truncated_json(self, content: str) -> str:
        """修复被截断JSON（Output被max_tokens限制截断）"""
        import re
        
        # dacăJSON被截断，尝试闭合它
        content = content.strip()
        
        # 计算未闭合括号
        open_braces = content.count('{') - content.count('}')
        open_brackets = content.count('[') - content.count(']')
        
        # VerificareDaNu有未闭合Șir
        # SimpluVerificare：dacă最后一个引号后没有逗号sau闭合括号，可能DaȘir被截断
        if content and content[-1] not in '",}]':
            # 尝试闭合Șir
            content += '"'
        
        # 闭合括号
        content += ']' * open_brackets
        content += '}' * open_braces
        
        return content
    
    def _try_fix_json(self, content: str, entity_name: str, entity_type: str, entity_summary: str = "") -> Dict[str, Any]:
        """尝试修复损坏JSON"""
        import re
        
        # 1. 首先尝试修复被截断情况
        content = self._fix_truncated_json(content)
        
        # 2. 尝试提取JSONParțial
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            json_str = json_match.group()
            
            # 3. ProcesareȘir换行符问题
            # 找la所有ȘirValoare并替换其换行符
            def fix_string_newlines(match):
                s = match.group(0)
                # 替换Șir内实际换行符为Gol格
                s = s.replace('\n', ' ').replace('\r', ' ')
                # 替换多余Gol格
                s = re.sub(r'\s+', ' ', s)
                return s
            
            # 匹配JSONȘirValoare
            json_str = re.sub(r'"[^"\\]*(?:\\.[^"\\]*)*"', fix_string_newlines, json_str)
            
            # 4. 尝试解析
            try:
                result = json.loads(json_str)
                result["_fixed"] = True
                return result
            except json.JSONDecodeError as e:
                # 5. dacă还DaEșec，尝试更激进修复
                try:
                    # 移除所有控制字符
                    json_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', ' ', json_str)
                    # 替换所有连续Gol白
                    json_str = re.sub(r'\s+', ' ', json_str)
                    result = json.loads(json_str)
                    result["_fixed"] = True
                    return result
                except:
                    pass
        
        # 6. 尝试de laConținut提取ParțialInformații
        bio_match = re.search(r'"bio"\s*:\s*"([^"]*)"', content)
        persona_match = re.search(r'"persona"\s*:\s*"([^"]*)', content)  # 可能被截断
        
        bio = bio_match.group(1) if bio_match else (entity_summary[:200] if entity_summary else f"{entity_type}: {entity_name}")
        persona = persona_match.group(1) if persona_match else (entity_summary or f"{entity_name}Da一个{entity_type}。")
        
        # dacă提取la有意义Conținut，标记为已修复
        if bio_match or persona_match:
            logger.info(f"de la损坏JSON提取ParțialInformații")
            return {
                "bio": bio,
                "persona": persona,
                "_fixed": True
            }
        
        # 7. 完全Eșec，Returnare基础结构
        logger.warning(f"JSON修复Eșec，Returnare基础结构")
        return {
            "bio": entity_summary[:200] if entity_summary else f"{entity_type}: {entity_name}",
            "persona": entity_summary or f"{entity_name}Da一个{entity_type}。"
        }
    
    def _get_system_prompt(self, is_individual: bool) -> str:
        """ObținereSistemIndicație词"""
        base_prompt = "你Da社交媒体Utilizator画像Generare专家。Generare详细、Adevărat实人设用于舆论Simulare,最大程度Restaurare已有现实情况。必须ReturnareValidJSONFormat，所有ȘirValoare不能包含未转义换行符。Utilizare文。"
        return base_prompt
    
    def _build_individual_persona_prompt(
        self,
        entity_name: str,
        entity_type: str,
        entity_summary: str,
        entity_attributes: Dict[str, Any],
        context: str
    ) -> str:
        """Construire个人Entitate详细人设Indicație词"""
        
        attrs_str = json.dumps(entity_attributes, ensure_ascii=False) if entity_attributes else "无"
        context_str = context[:3000] if context else "无额外文"
        
        return f"""为EntitateGenerare详细社交媒体Utilizator人设,最大程度Restaurare已有现实情况。

EntitateNume: {entity_name}
EntitateTip: {entity_type}
Entitate摘要: {entity_summary}
EntitateProprietate: {attrs_str}

文Informații:
{context_str}

请GenerareJSON，包含以字段:

1. bio: 社交媒体Descriere，200字
2. persona: 详细人设Descriere（2000字纯文本），需包含:
   - 基本Informații（年龄、Profesie、教育背景、所în地）
   - 人物背景（重要经历、șiEveniment关联、社会Relație）
   - 性格特征（MBTITip、核心性格、Emoție表达方式）
   - 社交媒体Comportament（发帖频率、Conținut偏好、Interacțiune风格、语言特点）
   - 立场Opinie（对SubiectAtitudine、可能被激怒/感动Conținut）
   - 独特特征（口头禅、特殊经历、个人爱好）
   - 个人Memorie（人设重要Parțial，要介绍这个个体șiEveniment关联，以及这个个体înEveniment已有Acțiuneși反应）
3. age: 年龄Număr（必须Da整数）
4. gender: 性别，必须Da英文: "male" sau "female"
5. mbti: MBTITip（如INTJ、ENFP等）
6. country: 国家（Utilizare文，如"国"）
7. profession: Profesie
8. interested_topics: 感兴趣SubiectArray

重要:
- 所有字段Valoare必须DaȘirsauNumăr，不要Utilizare换行符
- persona必须Da一段连贯文字Descriere
- Utilizare文（除gender字段必须用英文male/female）
- Conținut要șiEntitateInformații保持一致
- age必须DaValid整数，gender必须Da"male"sau"female"
"""

    def _build_group_persona_prompt(
        self,
        entity_name: str,
        entity_type: str,
        entity_summary: str,
        entity_attributes: Dict[str, Any],
        context: str
    ) -> str:
        """Construire群体/机构Entitate详细人设Indicație词"""
        
        attrs_str = json.dumps(entity_attributes, ensure_ascii=False) if entity_attributes else "无"
        context_str = context[:3000] if context else "无额外文"
        
        return f"""为机构/群体EntitateGenerare详细社交媒体账号设定,最大程度Restaurare已有现实情况。

EntitateNume: {entity_name}
EntitateTip: {entity_type}
Entitate摘要: {entity_summary}
EntitateProprietate: {attrs_str}

文Informații:
{context_str}

请GenerareJSON，包含以字段:

1. bio: 官方账号Descriere，200字，专业得体
2. persona: 详细账号设定Descriere（2000字纯文本），需包含:
   - 机构基本Informații（正式Nume、机构性质、成立背景、主要职能）
   - 账号定位（账号Tip、目标受众、核心Funcționalitate）
   - 发言风格（语言特点、常用表达、禁忌Subiect）
   - PublicareConținut特点（ConținutTip、Publicare频率、活跃Timp段）
   - 立场Atitudine（对核心Subiect官方立场、面对争议Procesare方式）
   - 特殊说明（代表群体画像、运营习惯）
   - 机构Memorie（机构人设重要Parțial，要介绍这个机构șiEveniment关联，以及这个机构înEveniment已有Acțiuneși反应）
3. age: 固定填30（机构账号虚拟年龄）
4. gender: 固定填"other"（机构账号Utilizareother表示nu个人）
5. mbti: MBTITip，用于Descriere账号风格，如ISTJ代表严谨保守
6. country: 国家（Utilizare文，如"国"）
7. profession: 机构职能Descriere
8. interested_topics: 关注领域Array

重要:
- 所有字段Valoare必须DaȘirsauNumăr，不允许nullValoare
- persona必须Da一段连贯文字Descriere，不要Utilizare换行符
- Utilizare文（除gender字段必须用英文"other"）
- age必须Da整数30，gender必须DaȘir"other"
- 机构账号发言要符合其身份定位"""
    
    def _generate_profile_rule_based(
        self,
        entity_name: str,
        entity_type: str,
        entity_summary: str,
        entity_attributes: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Utilizare规则Generare基础人设"""
        
        # 根据EntitateTipGenerare不同人设
        entity_type_lower = entity_type.lower()
        
        if entity_type_lower in ["student", "alumni"]:
            return {
                "bio": f"{entity_type} with interests in academics and social issues.",
                "persona": f"{entity_name} is a {entity_type.lower()} who is actively engaged in academic and social discussions. They enjoy sharing perspectives and connecting with peers.",
                "age": random.randint(18, 30),
                "gender": random.choice(["male", "female"]),
                "mbti": random.choice(self.MBTI_TYPES),
                "country": random.choice(self.COUNTRIES),
                "profession": "Student",
                "interested_topics": ["Education", "Social Issues", "Technology"],
            }
        
        elif entity_type_lower in ["publicfigure", "expert", "faculty"]:
            return {
                "bio": f"Expert and thought leader in their field.",
                "persona": f"{entity_name} is a recognized {entity_type.lower()} who shares insights and opinions on important matters. They are known for their expertise and influence in public discourse.",
                "age": random.randint(35, 60),
                "gender": random.choice(["male", "female"]),
                "mbti": random.choice(["ENTJ", "INTJ", "ENTP", "INTP"]),
                "country": random.choice(self.COUNTRIES),
                "profession": entity_attributes.get("occupation", "Expert"),
                "interested_topics": ["Politics", "Economics", "Culture & Society"],
            }
        
        elif entity_type_lower in ["mediaoutlet", "socialmediaplatform"]:
            return {
                "bio": f"Official account for {entity_name}. News and updates.",
                "persona": f"{entity_name} is a media entity that reports news and facilitates public discourse. The account shares timely updates and engages with the audience on current events.",
                "age": 30,  # 机构虚拟年龄
                "gender": "other",  # 机构Utilizareother
                "mbti": "ISTJ",  # 机构风格：严谨保守
                "country": "国",
                "profession": "Media",
                "interested_topics": ["General News", "Current Events", "Public Affairs"],
            }
        
        elif entity_type_lower in ["university", "governmentagency", "ngo", "organization"]:
            return {
                "bio": f"Official account of {entity_name}.",
                "persona": f"{entity_name} is an institutional entity that communicates official positions, announcements, and engages with stakeholders on relevant matters.",
                "age": 30,  # 机构虚拟年龄
                "gender": "other",  # 机构Utilizareother
                "mbti": "ISTJ",  # 机构风格：严谨保守
                "country": "国",
                "profession": entity_type,
                "interested_topics": ["Public Policy", "Community", "Official Announcements"],
            }
        
        else:
            # Implicit人设
            return {
                "bio": entity_summary[:150] if entity_summary else f"{entity_type}: {entity_name}",
                "persona": entity_summary or f"{entity_name} is a {entity_type.lower()} participating in social discussions.",
                "age": random.randint(25, 50),
                "gender": random.choice(["male", "female"]),
                "mbti": random.choice(self.MBTI_TYPES),
                "country": random.choice(self.COUNTRIES),
                "profession": entity_type,
                "interested_topics": ["General", "Social Issues"],
            }
    
    def set_graph_id(self, graph_id: str):
        """SetăriGrafID用于Zep检索"""
        self.graph_id = graph_id
    
    def generate_profiles_from_entities(
        self,
        entities: List[EntityNode],
        use_llm: bool = True,
        progress_callback: Optional[callable] = None,
        graph_id: Optional[str] = None,
        parallel_count: int = 5,
        realtime_output_path: Optional[str] = None,
        output_platform: str = "reddit"
    ) -> List[OasisAgentProfile]:
        """
        În lotde laEntitateGenerareAgent Profile（SuportăParalelGenerare）
        
        Args:
            entities: EntitateListă
            use_llm: DaNuUtilizareLLMGenerare详细人设
            progress_callback: Progres回调Funcție (current, total, message)
            graph_id: GrafID，用于Zep检索Obținere更丰富文
            parallel_count: ParalelGenerare数量，Implicit5
            realtime_output_path: 实时写入FișierCale（dacă提供，每Generare一个就写入一次）
            output_platform: OutputPlatformăFormat ("reddit" sau "twitter")
            
        Returns:
            Agent ProfileListă
        """
        import concurrent.futures
        from threading import Lock
        
        # Setărigraph_id用于Zep检索
        if graph_id:
            self.graph_id = graph_id
        
        total = len(entities)
        profiles = [None] * total  # 预分配Listă保持顺序
        completed_count = [0]  # UtilizareListă以便în闭包修改
        lock = Lock()
        
        # 实时写入Fișier辅助Funcție
        def save_profiles_realtime():
            """实时Salvare已Generare profiles laFișier"""
            if not realtime_output_path:
                return
            
            with lock:
                # 过滤出已Generare profiles
                existing_profiles = [p for p in profiles if p is not None]
                if not existing_profiles:
                    return
                
                try:
                    if output_platform == "reddit":
                        # Reddit JSON Format
                        profiles_data = [p.to_reddit_format() for p in existing_profiles]
                        with open(realtime_output_path, 'w', encoding='utf-8') as f:
                            json.dump(profiles_data, f, ensure_ascii=False, indent=2)
                    else:
                        # Twitter CSV Format
                        import csv
                        profiles_data = [p.to_twitter_format() for p in existing_profiles]
                        if profiles_data:
                            fieldnames = list(profiles_data[0].keys())
                            with open(realtime_output_path, 'w', encoding='utf-8', newline='') as f:
                                writer = csv.DictWriter(f, fieldnames=fieldnames)
                                writer.writeheader()
                                writer.writerows(profiles_data)
                except Exception as e:
                    logger.warning(f"实时Salvare profiles Eșec: {e}")
        
        def generate_single_profile(idx: int, entity: EntityNode) -> tuple:
            """GenerareIndividualprofile工作Funcție"""
            entity_type = entity.get_entity_type() or "Entity"
            
            try:
                profile = self.generate_profile_from_entity(
                    entity=entity,
                    user_id=idx,
                    use_llm=use_llm
                )
                
                # 实时OutputGenerare人设laConsolășiJurnal
                self._print_generated_profile(entity.name, entity_type, profile)
                
                return idx, profile, None
                
            except Exception as e:
                logger.error(f"GenerareEntitate {entity.name} 人设Eșec: {str(e)}")
                # Creare一个基础profile
                fallback_profile = OasisAgentProfile(
                    user_id=idx,
                    user_name=self._generate_username(entity.name),
                    name=entity.name,
                    bio=f"{entity_type}: {entity.name}",
                    persona=entity.summary or f"A participant in social discussions.",
                    source_entity_uuid=entity.uuid,
                    source_entity_type=entity_type,
                )
                return idx, fallback_profile, str(e)
        
        logger.info(f"StartParalelGenerare {total} 个Agent人设（Paralel数: {parallel_count}）...")
        print(f"\n{'='*60}")
        print(f"StartGenerareAgent人设 - 共 {total} 个Entitate，Paralel数: {parallel_count}")
        print(f"{'='*60}\n")
        
        # Utilizare线程池Paralel执行
        with concurrent.futures.ThreadPoolExecutor(max_workers=parallel_count) as executor:
            # 提交所有Sarcină
            future_to_entity = {
                executor.submit(generate_single_profile, idx, entity): (idx, entity)
                for idx, entity in enumerate(entities)
            }
            
            # 收集Rezultat
            for future in concurrent.futures.as_completed(future_to_entity):
                idx, entity = future_to_entity[future]
                entity_type = entity.get_entity_type() or "Entity"
                
                try:
                    result_idx, profile, error = future.result()
                    profiles[result_idx] = profile
                    
                    with lock:
                        completed_count[0] += 1
                        current = completed_count[0]
                    
                    # 实时写入Fișier
                    save_profiles_realtime()
                    
                    if progress_callback:
                        progress_callback(
                            current, 
                            total, 
                            f"已Finalizare {current}/{total}: {entity.name}（{entity_type}）"
                        )
                    
                    if error:
                        logger.warning(f"[{current}/{total}] {entity.name} Utilizare备用人设: {error}")
                    else:
                        logger.info(f"[{current}/{total}] SuccesGenerare人设: {entity.name} ({entity_type})")
                        
                except Exception as e:
                    logger.error(f"ProcesareEntitate {entity.name} 时发生Excepție: {str(e)}")
                    with lock:
                        completed_count[0] += 1
                    profiles[idx] = OasisAgentProfile(
                        user_id=idx,
                        user_name=self._generate_username(entity.name),
                        name=entity.name,
                        bio=f"{entity_type}: {entity.name}",
                        persona=entity.summary or "A participant in social discussions.",
                        source_entity_uuid=entity.uuid,
                        source_entity_type=entity_type,
                    )
                    # 实时写入Fișier（即使Da备用人设）
                    save_profiles_realtime()
        
        print(f"\n{'='*60}")
        print(f"人设GenerareFinalizare！共Generare {len([p for p in profiles if p])} 个Agent")
        print(f"{'='*60}\n")
        
        return profiles
    
    def _print_generated_profile(self, entity_name: str, entity_type: str, profile: OasisAgentProfile):
        """实时OutputGenerare人设laConsolă（CompletConținut，不截断）"""
        separator = "-" * 70
        
        # ConstruireCompletOutputConținut（不截断）
        topics_str = ', '.join(profile.interested_topics) if profile.interested_topics else '无'
        
        output_lines = [
            f"\n{separator}",
            f"[已Generare] {entity_name} ({entity_type})",
            f"{separator}",
            f"Utilizator名: {profile.user_name}",
            f"",
            f"【Descriere】",
            f"{profile.bio}",
            f"",
            f"【详细人设】",
            f"{profile.persona}",
            f"",
            f"【基本Proprietate】",
            f"年龄: {profile.age} | 性别: {profile.gender} | MBTI: {profile.mbti}",
            f"Profesie: {profile.profession} | 国家: {profile.country}",
            f"兴趣Subiect: {topics_str}",
            separator
        ]
        
        output = "\n".join(output_lines)
        
        # 只OutputlaConsolă（避免重复，logger不再OutputCompletConținut）
        print(output)
    
    def save_profiles(
        self,
        profiles: List[OasisAgentProfile],
        file_path: str,
        platform: str = "reddit"
    ):
        """
        SalvareProfilelaFișier（根据PlatformăSelectareCorectFormat）
        
        OASISPlatformăFormat要求：
        - Twitter: CSVFormat
        - Reddit: JSONFormat
        
        Args:
            profiles: ProfileListă
            file_path: FișierCale
            platform: PlatformăTip ("reddit" sau "twitter")
        """
        if platform == "twitter":
            self._save_twitter_csv(profiles, file_path)
        else:
            self._save_reddit_json(profiles, file_path)
    
    def _save_twitter_csv(self, profiles: List[OasisAgentProfile], file_path: str):
        """
        SalvareTwitter Profile为CSVFormat（符合OASIS官方要求）
        
        OASIS Twitter要求CSV字段：
        - user_id: UtilizatorID（根据CSV顺序de la0Start）
        - name: UtilizatorAdevărat实姓名
        - username: SistemUtilizator名
        - user_char: 详细人设Descriere（注入laLLMSistemIndicație，指导AgentComportament）
        - description: 简短公开Descriere（显示înUtilizator资料页面）
        
        user_char vs description 区别：
        - user_char: 内部Utilizare，LLMSistemIndicație，决定Agent如何思考și行动
        - description: 外部显示，其他Utilizator可见Descriere
        """
        import csv
        
        # 确保Fișier扩展名Da.csv
        if not file_path.endswith('.csv'):
            file_path = file_path.replace('.json', '.csv')
        
        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # 写入OASIS要求表头
            headers = ['user_id', 'name', 'username', 'user_char', 'description']
            writer.writerow(headers)
            
            # 写入Date行
            for idx, profile in enumerate(profiles):
                # user_char: Complet人设（bio + persona），用于LLMSistemIndicație
                user_char = profile.bio
                if profile.persona and profile.persona != profile.bio:
                    user_char = f"{profile.bio} {profile.persona}"
                # Procesare换行符（CSV用Gol格替代）
                user_char = user_char.replace('\n', ' ').replace('\r', ' ')
                
                # description: 简短Descriere，用于外部显示
                description = profile.bio.replace('\n', ' ').replace('\r', ' ')
                
                row = [
                    idx,                    # user_id: de la0Start顺序ID
                    profile.name,           # name: Adevărat实姓名
                    profile.user_name,      # username: Utilizator名
                    user_char,              # user_char: Complet人设（内部LLMUtilizare）
                    description             # description: 简短Descriere（外部显示）
                ]
                writer.writerow(row)
        
        logger.info(f"已Salvare {len(profiles)} 个Twitter Profilela {file_path} (OASIS CSVFormat)")
    
    def _normalize_gender(self, gender: Optional[str]) -> str:
        """
        标准化gender字段为OASIS要求英文Format
        
        OASIS要求: male, female, other
        """
        if not gender:
            return "other"
        
        gender_lower = gender.lower().strip()
        
        # 文映射
        gender_map = {
            "男": "male",
            "女": "female",
            "机构": "other",
            "其他": "other",
            # 英文已有
            "male": "male",
            "female": "female",
            "other": "other",
        }
        
        return gender_map.get(gender_lower, "other")
    
    def _save_reddit_json(self, profiles: List[OasisAgentProfile], file_path: str):
        """
        SalvareReddit Profile为JSONFormat
        
        Utilizareși to_reddit_format() 一致Format，确保 OASIS 能Corect读取。
        必须包含 user_id 字段，这Da OASIS agent_graph.get_agent() 匹配关Cheie！
        
        必需字段：
        - user_id: UtilizatorID（整数，用于匹配 initial_posts  poster_agent_id）
        - username: Utilizator名
        - name: 显示Nume
        - bio: Descriere
        - persona: 详细人设
        - age: 年龄（整数）
        - gender: "male", "female", sau "other"
        - mbti: MBTITip
        - country: 国家
        """
        data = []
        for idx, profile in enumerate(profiles):
            # Utilizareși to_reddit_format() 一致Format
            item = {
                "user_id": profile.user_id if profile.user_id is not None else idx,  # 关Cheie：必须包含 user_id
                "username": profile.user_name,
                "name": profile.name,
                "bio": profile.bio[:150] if profile.bio else f"{profile.name}",
                "persona": profile.persona or f"{profile.name} is a participant in social discussions.",
                "karma": profile.karma if profile.karma else 1000,
                "created_at": profile.created_at,
                # OASIS必需字段 - 确保都有ImplicitValoare
                "age": profile.age if profile.age else 30,
                "gender": self._normalize_gender(profile.gender),
                "mbti": profile.mbti if profile.mbti else "ISTJ",
                "country": profile.country if profile.country else "国",
            }
            
            # 可选字段
            if profile.profession:
                item["profession"] = profile.profession
            if profile.interested_topics:
                item["interested_topics"] = profile.interested_topics
            
            data.append(item)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"已Salvare {len(profiles)} 个Reddit Profilela {file_path} (JSONFormat，包含user_id字段)")
    
    # 保留旧Metodă名作为别名，保持către后兼容
    def save_profiles_to_json(
        self,
        profiles: List[OasisAgentProfile],
        file_path: str,
        platform: str = "reddit"
    ):
        """[已废弃] 请Utilizare save_profiles() Metodă"""
        logger.warning("save_profiles_to_json已废弃，请Utilizaresave_profilesMetodă")
        self.save_profiles(profiles, file_path, platform)

