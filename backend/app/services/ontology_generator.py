"""
OntologieGenerareServiciu
Interfață1：Analiză文本Conținut，Generare适合社会SimulareEntitateșiTipuri relații定义
"""

import json
from typing import Dict, Any, List, Optional
from ..utils.llm_client import LLMClient


# OntologieGenerareSistemIndicație词
ONTOLOGY_SYSTEM_PROMPT = """你Da一个专业CunoștințeGrafOntologie设计专家。你SarcinăDaAnaliză给定文本ConținutșiSimulareCerință，设计适合**社交媒体舆论Simulare**Tipuri entitățișiTipuri relații。

**重要：你必须Output有效JSONFormatDate，不要Output任何其他Conținut。**

## 核心Sarcină背景

我们正înConstruire一个**社交媒体舆论SimulareSistem**。în这个Sistem：
- 每个Entitate都Da一个可以în社交媒体发声、互动、传播Informații"账号"sau"主体"
- Entitate之间会相互影响、转发、评论、回应
- 我们需要Simulare舆论事件各方反应șiInformații传播Cale

因此，**Entitate必须Da现实Adevărat实存în、可以în社媒发声și互动主体**：

**可以Da**：
- 具体个人（公众人物、când事人、意见领袖、专家学者、普通人）
- 公司、企业（包括其官方账号）
- 组织机构（大学、协会、NGO、工会等）
- 政府部门、监管机构
- 媒体机构（报纸、电视台、自媒体、网站）
- 社交媒体Platformă本身
- 特定群体代表（如校友会、粉丝团、维权群体等）

**不可以Da**：
- 抽象概念（如"舆论"、"Emoție"、"趋势"）
- 主题/Subiect（如"学术诚信"、"教育改革"）
- Opinie/Atitudine（如"Suportă方"、"反对方"）

## OutputFormat

请OutputJSONFormat，包含以结构：

```json
{
    "entity_types": [
        {
            "name": "Tipuri entitățiNume（英文，PascalCase）",
            "description": "简短Descriere（英文，nu mai mult de100字符）",
            "attributes": [
                {
                    "name": "Proprietăți名（英文，snake_case）",
                    "type": "text",
                    "description": "ProprietățiDescriere"
                }
            ],
            "examples": ["示例Entitate1", "示例Entitate2"]
        }
    ],
    "edge_types": [
        {
            "name": "Tipuri relațiiNume（英文，UPPER_SNAKE_CASE）",
            "description": "简短Descriere（英文，nu mai mult de100字符）",
            "source_targets": [
                {"source": "源Tipuri entități", "target": "目标Tipuri entități"}
            ],
            "attributes": []
        }
    ],
    "analysis_summary": "对文本Conținut简要Analiză说明（文）"
}
```

## 设计指南（极其重要！）

### 1. Tipuri entități设计 - 必须严格遵守

**数量要求：必须正好10个Tipuri entități**

**层次结构要求（必须同时包含具体Tipși兜底Tip）**：

你10个Tipuri entități必须包含以层次：

A. **兜底Tip（必须包含，放înListă最后2个）**：
   - `Person`: 任何自然人个体兜底Tip。când一个人不属于其他更具体人物Tip时，归入此Clasă。
   - `Organization`: 任何组织机构兜底Tip。când一个组织不属于其他更具体组织Tip时，归入此Clasă。

B. **具体Tip（8个，根据文本Conținut设计）**：
   - 针对文本出现主要Rol，设计更具体Tip
   - 例如：dacă文本涉及学术事件，可以有 `Student`, `Professor`, `University`
   - 例如：dacă文本涉及商业事件，可以有 `Company`, `CEO`, `Employee`

**为什么需要兜底Tip**：
- 文本会出现各种人物，如"小学教师"、"路人甲"、"某位网友"
- dacă没有专门Tip匹配，他们应该被归入 `Person`
- 同理，小型组织、临时团体等应该归入 `Organization`

**具体Tip设计原则**：
- de la文本识别出高频出现sau关CheieRolTip
- 每个具体Tip应该有明确边界，避免重叠
- description 必须清晰说明这个Tipși兜底Tip区别

### 2. Tipuri relații设计

- 数量：6-10个
- Relație应该反映社媒互动Adevărat实联系
- 确保Relație source_targets 涵盖你定义Tipuri entități

### 3. Proprietăți设计

- 每个Tipuri entități1-3个关CheieProprietăți
- **注意**：Proprietăți名不能Utilizare `name`、`uuid`、`group_id`、`created_at`、`summary`（这些DaSistem保留字）
- 推荐Utilizare：`full_name`, `title`, `role`, `position`, `location`, `description` 等

## Tipuri entități参考

**个人Clasă（具体）**：
- Student: 学生
- Professor: 教授/学者
- Journalist: 记者
- Celebrity: 明星/网红
- Executive: 高管
- Official: 政府官员
- Lawyer: 律师
- Doctor: 医生

**个人Clasă（兜底）**：
- Person: 任何自然人（不属于述具体Tip时Utilizare）

**组织Clasă（具体）**：
- University: 高校
- Company: 公司企业
- GovernmentAgency: 政府机构
- MediaOutlet: 媒体机构
- Hospital: 医院
- School: 小学
- NGO: nu政府组织

**组织Clasă（兜底）**：
- Organization: 任何组织机构（不属于述具体Tip时Utilizare）

## Tipuri relații参考

- WORKS_FOR: 工作于
- STUDIES_AT: 就读于
- AFFILIATED_WITH: 隶属于
- REPRESENTS: 代表
- REGULATES: 监管
- REPORTS_ON: 报道
- COMMENTS_ON: 评论
- RESPONDS_TO: 回应
- SUPPORTS: Suportă
- OPPOSES: 反对
- COLLABORATES_WITH: 合作
- COMPETES_WITH: 竞争
"""


class OntologyGenerator:
    """
    OntologieGenerare器
    Analiză文本Conținut，GenerareEntitateșiTipuri relații定义
    """
    
    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client or LLMClient()
    
    def generate(
        self,
        document_texts: List[str],
        simulation_requirement: str,
        additional_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generare ontologie定义
        
        Args:
            document_texts: Documentație文本Listă
            simulation_requirement: SimulareCerințăDescriere
            additional_context: 额外文
            
        Returns:
            Ontologie定义（entity_types, edge_types等）
        """
        # ConstruireUtilizatorMesaj
        user_message = self._build_user_message(
            document_texts, 
            simulation_requirement,
            additional_context
        )
        
        messages = [
            {"role": "system", "content": ONTOLOGY_SYSTEM_PROMPT},
            {"role": "user", "content": user_message}
        ]
        
        # 调用LLM
        result = self.llm_client.chat_json(
            messages=messages,
            temperature=0.3,
            max_tokens=4096
        )
        
        # Verificareși后Procesare
        result = self._validate_and_process(result)
        
        return result
    
    # 传给 LLM 文本最大长度（5万字）
    MAX_TEXT_LENGTH_FOR_LLM = 50000
    
    def _build_user_message(
        self,
        document_texts: List[str],
        simulation_requirement: str,
        additional_context: Optional[str]
    ) -> str:
        """ConstruireUtilizatorMesaj"""
        
        # 合并文本
        combined_text = "\n\n---\n\n".join(document_texts)
        original_length = len(combined_text)
        
        # dacă文本超过5万字，截断（仅影响传给LLMConținut，不影响GrafConstruire）
        if len(combined_text) > self.MAX_TEXT_LENGTH_FOR_LLM:
            combined_text = combined_text[:self.MAX_TEXT_LENGTH_FOR_LLM]
            combined_text += f"\n\n...(原文共{original_length}字，已截取前{self.MAX_TEXT_LENGTH_FOR_LLM}字用于OntologieAnaliză)..."
        
        message = f"""## SimulareCerință

{simulation_requirement}

## DocumentațieConținut

{combined_text}
"""
        
        if additional_context:
            message += f"""
## 额外说明

{additional_context}
"""
        
        message += """
请根据以Conținut，设计适合社会舆论SimulareTipuri entitățișiTipuri relații。

**必须遵守规则**：
1. 必须正好Output10个Tipuri entități
2. 最后2个必须Da兜底Tip：Person（个人兜底）și Organization（组织兜底）
3. 前8个Da根据文本Conținut设计具体Tip
4. 所有Tipuri entități必须Da现实可以发声主体，不能Da抽象概念
5. Proprietăți名不能Utilizare name、uuid、group_id 等保留字，用 full_name、org_name 等替代
"""
        
        return message
    
    def _validate_and_process(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Verificareși后ProcesareRezultat"""
        
        # 确保必要字段存în
        if "entity_types" not in result:
            result["entity_types"] = []
        if "edge_types" not in result:
            result["edge_types"] = []
        if "analysis_summary" not in result:
            result["analysis_summary"] = ""
        
        # VerificareTipuri entități
        for entity in result["entity_types"]:
            if "attributes" not in entity:
                entity["attributes"] = []
            if "examples" not in entity:
                entity["examples"] = []
            # 确保descriptionnu mai mult de100字符
            if len(entity.get("description", "")) > 100:
                entity["description"] = entity["description"][:97] + "..."
        
        # VerificareTipuri relații
        for edge in result["edge_types"]:
            if "source_targets" not in edge:
                edge["source_targets"] = []
            if "attributes" not in edge:
                edge["attributes"] = []
            if len(edge.get("description", "")) > 100:
                edge["description"] = edge["description"][:97] + "..."
        
        # Zep API 限制：最多 10 个自定义Tipuri entități，最多 10 个自定义边Tip
        MAX_ENTITY_TYPES = 10
        MAX_EDGE_TYPES = 10
        
        # 兜底Tip定义
        person_fallback = {
            "name": "Person",
            "description": "Any individual person not fitting other specific person types.",
            "attributes": [
                {"name": "full_name", "type": "text", "description": "Full name of the person"},
                {"name": "role", "type": "text", "description": "Role or occupation"}
            ],
            "examples": ["ordinary citizen", "anonymous netizen"]
        }
        
        organization_fallback = {
            "name": "Organization",
            "description": "Any organization not fitting other specific organization types.",
            "attributes": [
                {"name": "org_name", "type": "text", "description": "Name of the organization"},
                {"name": "org_type", "type": "text", "description": "Type of organization"}
            ],
            "examples": ["small business", "community group"]
        }
        
        # VerificareDaNu已有兜底Tip
        entity_names = {e["name"] for e in result["entity_types"]}
        has_person = "Person" in entity_names
        has_organization = "Organization" in entity_names
        
        # 需要添加兜底Tip
        fallbacks_to_add = []
        if not has_person:
            fallbacks_to_add.append(person_fallback)
        if not has_organization:
            fallbacks_to_add.append(organization_fallback)
        
        if fallbacks_to_add:
            current_count = len(result["entity_types"])
            needed_slots = len(fallbacks_to_add)
            
            # dacă添加后会超过 10 个，需要移除一些现有Tip
            if current_count + needed_slots > MAX_ENTITY_TYPES:
                # 计算需要移除多少个
                to_remove = current_count + needed_slots - MAX_ENTITY_TYPES
                # de la末尾移除（保留前面更重要具体Tip）
                result["entity_types"] = result["entity_types"][:-to_remove]
            
            # 添加兜底Tip
            result["entity_types"].extend(fallbacks_to_add)
        
        # 最终确保nu mai mult de限制（防御性编程）
        if len(result["entity_types"]) > MAX_ENTITY_TYPES:
            result["entity_types"] = result["entity_types"][:MAX_ENTITY_TYPES]
        
        if len(result["edge_types"]) > MAX_EDGE_TYPES:
            result["edge_types"] = result["edge_types"][:MAX_EDGE_TYPES]
        
        return result
    
    def generate_python_code(self, ontology: Dict[str, Any]) -> str:
        """
        将Ontologie定义转换为Python代码（Clasă似ontology.py）
        
        Args:
            ontology: Ontologie定义
            
        Returns:
            Python代码Șir
        """
        code_lines = [
            '"""',
            '自定义Tipuri entități定义',
            '由MiroFish自动Generare，用于社会舆论Simulare',
            '"""',
            '',
            'from pydantic import Field',
            'from zep_cloud.external_clients.ontology import EntityModel, EntityText, EdgeModel',
            '',
            '',
            '# ============== Tipuri entități定义 ==============',
            '',
        ]
        
        # GenerareTipuri entități
        for entity in ontology.get("entity_types", []):
            name = entity["name"]
            desc = entity.get("description", f"A {name} entity.")
            
            code_lines.append(f'class {name}(EntityModel):')
            code_lines.append(f'    """{desc}"""')
            
            attrs = entity.get("attributes", [])
            if attrs:
                for attr in attrs:
                    attr_name = attr["name"]
                    attr_desc = attr.get("description", attr_name)
                    code_lines.append(f'    {attr_name}: EntityText = Field(')
                    code_lines.append(f'        description="{attr_desc}",')
                    code_lines.append(f'        default=None')
                    code_lines.append(f'    )')
            else:
                code_lines.append('    pass')
            
            code_lines.append('')
            code_lines.append('')
        
        code_lines.append('# ============== Tipuri relații定义 ==============')
        code_lines.append('')
        
        # GenerareTipuri relații
        for edge in ontology.get("edge_types", []):
            name = edge["name"]
            # 转换为PascalCaseClasă名
            class_name = ''.join(word.capitalize() for word in name.split('_'))
            desc = edge.get("description", f"A {name} relationship.")
            
            code_lines.append(f'class {class_name}(EdgeModel):')
            code_lines.append(f'    """{desc}"""')
            
            attrs = edge.get("attributes", [])
            if attrs:
                for attr in attrs:
                    attr_name = attr["name"]
                    attr_desc = attr.get("description", attr_name)
                    code_lines.append(f'    {attr_name}: EntityText = Field(')
                    code_lines.append(f'        description="{attr_desc}",')
                    code_lines.append(f'        default=None')
                    code_lines.append(f'    )')
            else:
                code_lines.append('    pass')
            
            code_lines.append('')
            code_lines.append('')
        
        # GenerareTipDicționar
        code_lines.append('# ============== TipConfigurare ==============')
        code_lines.append('')
        code_lines.append('ENTITY_TYPES = {')
        for entity in ontology.get("entity_types", []):
            name = entity["name"]
            code_lines.append(f'    "{name}": {name},')
        code_lines.append('}')
        code_lines.append('')
        code_lines.append('EDGE_TYPES = {')
        for edge in ontology.get("edge_types", []):
            name = edge["name"]
            class_name = ''.join(word.capitalize() for word in name.split('_'))
            code_lines.append(f'    "{name}": {class_name},')
        code_lines.append('}')
        code_lines.append('')
        
        # Generare边source_targets映射
        code_lines.append('EDGE_SOURCE_TARGETS = {')
        for edge in ontology.get("edge_types", []):
            name = edge["name"]
            source_targets = edge.get("source_targets", [])
            if source_targets:
                st_list = ', '.join([
                    f'{{"source": "{st.get("source", "Entity")}", "target": "{st.get("target", "Entity")}"}}'
                    for st in source_targets
                ])
                code_lines.append(f'    "{name}": [{st_list}],')
        code_lines.append('}')
        
        return '\n'.join(code_lines)

