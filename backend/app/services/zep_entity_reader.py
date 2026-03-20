"""
ZepEntitate读取și过滤Serviciu
de laZepGraf读取Nod，筛选出符合预定义EntitateTipNod
"""

import time
from typing import Dict, Any, List, Optional, Set, Callable, TypeVar
from dataclasses import dataclass, field

from zep_cloud.client import Zep

from ..config import Config
from ..utils.logger import get_logger
from ..utils.zep_paging import fetch_all_nodes, fetch_all_edges

logger = get_logger('mirofish.zep_entity_reader')

# 用于泛型ReturnareTip
T = TypeVar('T')


@dataclass
class EntityNode:
    """EntitateNodDate结构"""
    uuid: str
    name: str
    labels: List[str]
    summary: str
    attributes: Dict[str, Any]
    # 相关边Informații
    related_edges: List[Dict[str, Any]] = field(default_factory=list)
    # 相关其他NodInformații
    related_nodes: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "uuid": self.uuid,
            "name": self.name,
            "labels": self.labels,
            "summary": self.summary,
            "attributes": self.attributes,
            "related_edges": self.related_edges,
            "related_nodes": self.related_nodes,
        }
    
    def get_entity_type(self) -> Optional[str]:
        """ObținereEntitateTip（排除ImplicitEntity标签）"""
        for label in self.labels:
            if label not in ["Entity", "Node"]:
                return label
        return None


@dataclass
class FilteredEntities:
    """过滤后EntitateSet"""
    entities: List[EntityNode]
    entity_types: Set[str]
    total_count: int
    filtered_count: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "entities": [e.to_dict() for e in self.entities],
            "entity_types": list(self.entity_types),
            "total_count": self.total_count,
            "filtered_count": self.filtered_count,
        }


class ZepEntityReader:
    """
    ZepEntitate读取și过滤Serviciu
    
    主要Funcționalitate：
    1. de laZepGraf读取所有Nod
    2. 筛选出符合预定义EntitateTipNod（Labels不只DaEntityNod）
    3. Obținere每个Entitate相关边și关联NodInformații
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or Config.ZEP_API_KEY
        if not self.api_key:
            raise ValueError("ZEP_API_KEY 未Configurare")
        
        self.client = Zep(api_key=self.api_key)
    
    def _call_with_retry(
        self, 
        func: Callable[[], T], 
        operation_name: str,
        max_retries: int = 3,
        initial_delay: float = 2.0
    ) -> T:
        """
        带Reîncercare机制Zep API调用
        
        Args:
            func: 要执行Funcție（无Parametrulambdasaucallable）
            operation_name: 操作Nume，用于Jurnal
            max_retries: 最大Reîncercare次数（Implicit3次，即最多尝试3次）
            initial_delay: 初始延迟秒数
            
        Returns:
            API调用Rezultat
        """
        last_exception = None
        delay = initial_delay
        
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
                    delay *= 2  # 指数退避
                else:
                    logger.error(f"Zep {operation_name} în {max_retries} 次尝试后仍Eșec: {str(e)}")
        
        raise last_exception
    
    def get_all_nodes(self, graph_id: str) -> List[Dict[str, Any]]:
        """
        ObținereGraf所有Nod（分页Obținere）

        Args:
            graph_id: GrafID

        Returns:
            NodListă
        """
        logger.info(f"ObținereGraf {graph_id} 所有Nod...")

        nodes = fetch_all_nodes(self.client, graph_id)

        nodes_data = []
        for node in nodes:
            nodes_data.append({
                "uuid": getattr(node, 'uuid_', None) or getattr(node, 'uuid', ''),
                "name": node.name or "",
                "labels": node.labels or [],
                "summary": node.summary or "",
                "attributes": node.attributes or {},
            })

        logger.info(f"共Obținere {len(nodes_data)} 个Nod")
        return nodes_data

    def get_all_edges(self, graph_id: str) -> List[Dict[str, Any]]:
        """
        ObținereGraf所有边（分页Obținere）

        Args:
            graph_id: GrafID

        Returns:
            边Listă
        """
        logger.info(f"ObținereGraf {graph_id} 所有边...")

        edges = fetch_all_edges(self.client, graph_id)

        edges_data = []
        for edge in edges:
            edges_data.append({
                "uuid": getattr(edge, 'uuid_', None) or getattr(edge, 'uuid', ''),
                "name": edge.name or "",
                "fact": edge.fact or "",
                "source_node_uuid": edge.source_node_uuid,
                "target_node_uuid": edge.target_node_uuid,
                "attributes": edge.attributes or {},
            })

        logger.info(f"共Obținere {len(edges_data)} 条边")
        return edges_data
    
    def get_node_edges(self, node_uuid: str) -> List[Dict[str, Any]]:
        """
        Obținere指定Nod所有相关边（带Reîncercare机制）
        
        Args:
            node_uuid: NodUUID
            
        Returns:
            边Listă
        """
        try:
            # 使用Reîncercare机制调用Zep API
            edges = self._call_with_retry(
                func=lambda: self.client.graph.node.get_entity_edges(node_uuid=node_uuid),
                operation_name=f"ObținereNod边(node={node_uuid[:8]}...)"
            )
            
            edges_data = []
            for edge in edges:
                edges_data.append({
                    "uuid": getattr(edge, 'uuid_', None) or getattr(edge, 'uuid', ''),
                    "name": edge.name or "",
                    "fact": edge.fact or "",
                    "source_node_uuid": edge.source_node_uuid,
                    "target_node_uuid": edge.target_node_uuid,
                    "attributes": edge.attributes or {},
                })
            
            return edges_data
        except Exception as e:
            logger.warning(f"ObținereNod {node_uuid} 边Eșec: {str(e)}")
            return []
    
    def filter_defined_entities(
        self, 
        graph_id: str,
        defined_entity_types: Optional[List[str]] = None,
        enrich_with_edges: bool = True
    ) -> FilteredEntities:
        """
        筛选出符合预定义EntitateTipNod
        
        筛选逻辑：
        - dacăNodLabels只有一个"Entity"，说明这个Entitate不符合我们预定义Tip，跳过
        - dacăNodLabels包含除"Entity"și"Node"之外标签，说明符合预定义Tip，保留
        
        Args:
            graph_id: GrafID
            defined_entity_types: 预定义EntitateTipListă（可选，dacă提供则只保留这些Tip）
            enrich_with_edges: DaNuObținere每个Entitate相关边Informații
            
        Returns:
            FilteredEntities: 过滤后EntitateSet
        """
        logger.info(f"Start筛选Graf {graph_id} Entitate...")
        
        # Obținere所有Nod
        all_nodes = self.get_all_nodes(graph_id)
        total_count = len(all_nodes)
        
        # Obținere所有边（用于后续关联查找）
        all_edges = self.get_all_edges(graph_id) if enrich_with_edges else []
        
        # ConstruireNodUUIDlaNodDate映射
        node_map = {n["uuid"]: n for n in all_nodes}
        
        # 筛选符合CondițieEntitate
        filtered_entities = []
        entity_types_found = set()
        
        for node in all_nodes:
            labels = node.get("labels", [])
            
            # 筛选逻辑：Labels必须包含除"Entity"și"Node"之外标签
            custom_labels = [l for l in labels if l not in ["Entity", "Node"]]
            
            if not custom_labels:
                # 只有Implicit标签，跳过
                continue
            
            # dacă指定预定义Tip，VerificareDaNu匹配
            if defined_entity_types:
                matching_labels = [l for l in custom_labels if l in defined_entity_types]
                if not matching_labels:
                    continue
                entity_type = matching_labels[0]
            else:
                entity_type = custom_labels[0]
            
            entity_types_found.add(entity_type)
            
            # CreareEntitateNodObiect
            entity = EntityNode(
                uuid=node["uuid"],
                name=node["name"],
                labels=labels,
                summary=node["summary"],
                attributes=node["attributes"],
            )
            
            # Obținere相关边șiNod
            if enrich_with_edges:
                related_edges = []
                related_node_uuids = set()
                
                for edge in all_edges:
                    if edge["source_node_uuid"] == node["uuid"]:
                        related_edges.append({
                            "direction": "outgoing",
                            "edge_name": edge["name"],
                            "fact": edge["fact"],
                            "target_node_uuid": edge["target_node_uuid"],
                        })
                        related_node_uuids.add(edge["target_node_uuid"])
                    elif edge["target_node_uuid"] == node["uuid"]:
                        related_edges.append({
                            "direction": "incoming",
                            "edge_name": edge["name"],
                            "fact": edge["fact"],
                            "source_node_uuid": edge["source_node_uuid"],
                        })
                        related_node_uuids.add(edge["source_node_uuid"])
                
                entity.related_edges = related_edges
                
                # Obținere关联Nod基本Informații
                related_nodes = []
                for related_uuid in related_node_uuids:
                    if related_uuid in node_map:
                        related_node = node_map[related_uuid]
                        related_nodes.append({
                            "uuid": related_node["uuid"],
                            "name": related_node["name"],
                            "labels": related_node["labels"],
                            "summary": related_node.get("summary", ""),
                        })
                
                entity.related_nodes = related_nodes
            
            filtered_entities.append(entity)
        
        logger.info(f"筛选Finalizare: 总Nod {total_count}, 符合Condiție {len(filtered_entities)}, "
                   f"EntitateTip: {entity_types_found}")
        
        return FilteredEntities(
            entities=filtered_entities,
            entity_types=entity_types_found,
            total_count=total_count,
            filtered_count=len(filtered_entities),
        )
    
    def get_entity_with_context(
        self, 
        graph_id: str, 
        entity_uuid: str
    ) -> Optional[EntityNode]:
        """
        ObținereIndividualEntitate及其Complet文（边și关联Nod，带Reîncercare机制）
        
        Args:
            graph_id: GrafID
            entity_uuid: EntitateUUID
            
        Returns:
            EntityNodesauNone
        """
        try:
            # 使用Reîncercare机制ObținereNod
            node = self._call_with_retry(
                func=lambda: self.client.graph.node.get(uuid_=entity_uuid),
                operation_name=f"ObținereNod详情(uuid={entity_uuid[:8]}...)"
            )
            
            if not node:
                return None
            
            # ObținereNod边
            edges = self.get_node_edges(entity_uuid)
            
            # Obținere所有Nod用于关联查找
            all_nodes = self.get_all_nodes(graph_id)
            node_map = {n["uuid"]: n for n in all_nodes}
            
            # Procesare相关边șiNod
            related_edges = []
            related_node_uuids = set()
            
            for edge in edges:
                if edge["source_node_uuid"] == entity_uuid:
                    related_edges.append({
                        "direction": "outgoing",
                        "edge_name": edge["name"],
                        "fact": edge["fact"],
                        "target_node_uuid": edge["target_node_uuid"],
                    })
                    related_node_uuids.add(edge["target_node_uuid"])
                else:
                    related_edges.append({
                        "direction": "incoming",
                        "edge_name": edge["name"],
                        "fact": edge["fact"],
                        "source_node_uuid": edge["source_node_uuid"],
                    })
                    related_node_uuids.add(edge["source_node_uuid"])
            
            # Obținere关联NodInformații
            related_nodes = []
            for related_uuid in related_node_uuids:
                if related_uuid in node_map:
                    related_node = node_map[related_uuid]
                    related_nodes.append({
                        "uuid": related_node["uuid"],
                        "name": related_node["name"],
                        "labels": related_node["labels"],
                        "summary": related_node.get("summary", ""),
                    })
            
            return EntityNode(
                uuid=getattr(node, 'uuid_', None) or getattr(node, 'uuid', ''),
                name=node.name or "",
                labels=node.labels or [],
                summary=node.summary or "",
                attributes=node.attributes or {},
                related_edges=related_edges,
                related_nodes=related_nodes,
            )
            
        except Exception as e:
            logger.error(f"ObținereEntitate {entity_uuid} Eșec: {str(e)}")
            return None
    
    def get_entities_by_type(
        self, 
        graph_id: str, 
        entity_type: str,
        enrich_with_edges: bool = True
    ) -> List[EntityNode]:
        """
        Obținere指定Tip所有Entitate
        
        Args:
            graph_id: GrafID
            entity_type: EntitateTip（如 "Student", "PublicFigure" 等）
            enrich_with_edges: DaNuObținere相关边Informații
            
        Returns:
            EntitateListă
        """
        result = self.filter_defined_entities(
            graph_id=graph_id,
            defined_entity_types=[entity_type],
            enrich_with_edges=enrich_with_edges
        )
        return result.entities


