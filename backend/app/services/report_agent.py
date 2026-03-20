"""
Serviciu Report Agent
Generează rapoarte simulate în mod ReACT folosind LangChain + Zep

Funcționalități:
1. Generează rapoarte pe baza cerințelor de simulare și informațiilor din graful Zep
2. Planifică mai întâi structura, apoi generează secțiuni
3. Fiecare secțiune folosește mod ReACT cu multiple runde de gândire și reflecție
4. Suportă conversație cu utilizatorul, apelând autonom instrumente de căutare în dialog
"""

import os
import json
import time
import re
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from ..config import Config
from ..utils.llm_client import LLMClient
from ..utils.logger import get_logger
from .zep_tools import (
    ZepToolsService,
    SearchResult,
    InsightForgeResult,
    PanoramaResult,
    InterviewResult,
)

logger = get_logger("mirofish.report_agent")


class ReportLogger:
    """
    Logger Detaliat Report Agent

    Generează fișierul agent_log.jsonl în folderul raportului, înregistrând fiecare acțiune detaliată.
    Fiecare linie este un obiect JSON complet, conținând timestamp, tip acțiune, conținut detaliat etc.
    """

    def __init__(self, report_id: str):
        """
        Inițializare logger

        Args:
            report_id: ID raport, folosit pentru a determina calea fișierului de log
        """
        self.report_id = report_id
        self.log_file_path = os.path.join(
            Config.UPLOAD_FOLDER, "reports", report_id, "agent_log.jsonl"
        )
        self.start_time = datetime.now()
        self._ensure_log_file()

    def _ensure_log_file(self):
        """Asigură că directorul fișierului de log există"""
        log_dir = os.path.dirname(self.log_file_path)
        os.makedirs(log_dir, exist_ok=True)

    def _get_elapsed_time(self) -> float:
        """Obține timpul scurs de la început (secunde)"""
        return (datetime.now() - self.start_time).total_seconds()

    def log(
        self,
        action: str,
        stage: str,
        details: Dict[str, Any],
        section_title: str = None,
        section_index: int = None,
    ):
        """
        Înregistrează o intrare de log

        Args:
            action: Tip acțiune, cum ar fi 'start', 'tool_call', 'llm_response', 'section_complete' etc.
            stage: Etapa curentă, cum ar fi 'planning', 'generating', 'completed'
            details: Dicționar conținut detaliat, netrunchiat
            section_title: Titlul capitolului curent (opțional)
            section_index: Indexul capitolului curent (opțional)
        """
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "elapsed_seconds": round(self._get_elapsed_time(), 2),
            "report_id": self.report_id,
            "action": action,
            "stage": stage,
            "section_title": section_title,
            "section_index": section_index,
            "details": details,
        }

        # 追加写入 JSONL Fișier
        with open(self.log_file_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

    def log_start(self, simulation_id: str, graph_id: str, simulation_requirement: str):
        """Înregistrează începutul generării raportului"""
        self.log(
            action="report_start",
            stage="pending",
            details={
                "simulation_id": simulation_id,
                "graph_id": graph_id,
                "simulation_requirement": simulation_requirement,
                "message": "RaportGenerareSarcinăStart",
            },
        )

    def log_planning_start(self):
        """Înregistrare大纲规划Start"""
        self.log(
            action="planning_start",
            stage="planning",
            details={"message": "Start规划Raport大纲"},
        )

    def log_planning_context(self, context: Dict[str, Any]):
        """Înregistrare规划时Obținere文Informații"""
        self.log(
            action="planning_context",
            stage="planning",
            details={"message": "ObținereSimulare文Informații", "context": context},
        )

    def log_planning_complete(self, outline_dict: Dict[str, Any]):
        """Înregistrare大纲规划Finalizare"""
        self.log(
            action="planning_complete",
            stage="planning",
            details={"message": "大纲规划Finalizare", "outline": outline_dict},
        )

    def log_section_start(self, section_title: str, section_index: int):
        """Înregistrare章节GenerareStart"""
        self.log(
            action="section_start",
            stage="generating",
            section_title=section_title,
            section_index=section_index,
            details={"message": f"StartGenerare章节: {section_title}"},
        )

    def log_react_thought(
        self, section_title: str, section_index: int, iteration: int, thought: str
    ):
        """Înregistrare ReACT 思考过程"""
        self.log(
            action="react_thought",
            stage="generating",
            section_title=section_title,
            section_index=section_index,
            details={
                "iteration": iteration,
                "thought": thought,
                "message": f"ReACT 第{iteration}轮思考",
            },
        )

    def log_tool_call(
        self,
        section_title: str,
        section_index: int,
        tool_name: str,
        parameters: Dict[str, Any],
        iteration: int,
    ):
        """ÎnregistrareInstrument调用"""
        self.log(
            action="tool_call",
            stage="generating",
            section_title=section_title,
            section_index=section_index,
            details={
                "iteration": iteration,
                "tool_name": tool_name,
                "parameters": parameters,
                "message": f"调用Instrument: {tool_name}",
            },
        )

    def log_tool_result(
        self,
        section_title: str,
        section_index: int,
        tool_name: str,
        result: str,
        iteration: int,
    ):
        """ÎnregistrareInstrument调用Rezultat（完整Conținut，不截断）"""
        self.log(
            action="tool_result",
            stage="generating",
            section_title=section_title,
            section_index=section_index,
            details={
                "iteration": iteration,
                "tool_name": tool_name,
                "result": result,  # 完整Rezultat，不截断
                "result_length": len(result),
                "message": f"Instrument {tool_name} ÎnapoiRezultat",
            },
        )

    def log_llm_response(
        self,
        section_title: str,
        section_index: int,
        response: str,
        iteration: int,
        has_tool_calls: bool,
        has_final_answer: bool,
    ):
        """Înregistrare LLM Răspuns（完整Conținut，不截断）"""
        self.log(
            action="llm_response",
            stage="generating",
            section_title=section_title,
            section_index=section_index,
            details={
                "iteration": iteration,
                "response": response,  # 完整Răspuns，不截断
                "response_length": len(response),
                "has_tool_calls": has_tool_calls,
                "has_final_answer": has_final_answer,
                "message": f"LLM Răspuns (Instrument调用: {has_tool_calls}, 最终答案: {has_final_answer})",
            },
        )

    def log_section_content(
        self,
        section_title: str,
        section_index: int,
        content: str,
        tool_calls_count: int,
    ):
        """Înregistrare章节ConținutGenerareFinalizare（仅ÎnregistrareConținut，不代表整个章节Finalizare）"""
        self.log(
            action="section_content",
            stage="generating",
            section_title=section_title,
            section_index=section_index,
            details={
                "content": content,  # 完整Conținut，不截断
                "content_length": len(content),
                "tool_calls_count": tool_calls_count,
                "message": f"章节 {section_title} ConținutGenerareFinalizare",
            },
        )

    def log_section_full_complete(
        self, section_title: str, section_index: int, full_content: str
    ):
        """
        Înregistrare章节GenerareFinalizare

        前端应监听此Jurnal来判断一个章节DaNuAdevărat正Finalizare，并Obținere完整Conținut
        """
        self.log(
            action="section_complete",
            stage="generating",
            section_title=section_title,
            section_index=section_index,
            details={
                "content": full_content,
                "content_length": len(full_content),
                "message": f"章节 {section_title} GenerareFinalizare",
            },
        )

    def log_report_complete(self, total_sections: int, total_time_seconds: float):
        """ÎnregistrareRaportGenerareFinalizare"""
        self.log(
            action="report_complete",
            stage="completed",
            details={
                "total_sections": total_sections,
                "total_time_seconds": round(total_time_seconds, 2),
                "message": "RaportGenerareFinalizare",
            },
        )

    def log_error(self, error_message: str, stage: str, section_title: str = None):
        """ÎnregistrareEroare"""
        self.log(
            action="error",
            stage=stage,
            section_title=section_title,
            section_index=None,
            details={"error": error_message, "message": f"发生Eroare: {error_message}"},
        )


class ReportConsoleLogger:
    """
    Report Agent ConsolăJurnalÎnregistrare器

    将Consolă风格Jurnal（INFO、WARNING等）写入RaportFișier夹 console_log.txt Fișier。
    这些Jurnalși agent_log.jsonl 不同，Da纯文本FormatConsolăOutput。
    """

    def __init__(self, report_id: str):
        """
        InițializareConsolăJurnalÎnregistrare器

        Args:
            report_id: ID raport, folosit pentru a determina calea fișierului de log
        """
        self.report_id = report_id
        self.log_file_path = os.path.join(
            Config.UPLOAD_FOLDER, "reports", report_id, "console_log.txt"
        )
        self._ensure_log_file()
        self._file_handler = None
        self._setup_file_handler()

    def _ensure_log_file(self):
        """Asigură că directorul fișierului de log există"""
        log_dir = os.path.dirname(self.log_file_path)
        os.makedirs(log_dir, exist_ok=True)

    def _setup_file_handler(self):
        """SetăriFișierProcesare器，将Jurnal同时写入Fișier"""
        import logging

        # CreareFișierProcesare器
        self._file_handler = logging.FileHandler(
            self.log_file_path, mode="a", encoding="utf-8"
        )
        self._file_handler.setLevel(logging.INFO)

        # UtilizareșiConsolă相同简洁Format
        formatter = logging.Formatter(
            "[%(asctime)s] %(levelname)s: %(message)s", datefmt="%H:%M:%S"
        )
        self._file_handler.setFormatter(formatter)

        # 添加la report_agent 相关 logger
        loggers_to_attach = [
            "mirofish.report_agent",
            "mirofish.zep_tools",
        ]

        for logger_name in loggers_to_attach:
            target_logger = logging.getLogger(logger_name)
            # 避免重复添加
            if self._file_handler not in target_logger.handlers:
                target_logger.addHandler(self._file_handler)

    def close(self):
        """ÎnchidereFișierProcesare器并de la logger 移除"""
        import logging

        if self._file_handler:
            loggers_to_detach = [
                "mirofish.report_agent",
                "mirofish.zep_tools",
            ]

            for logger_name in loggers_to_detach:
                target_logger = logging.getLogger(logger_name)
                if self._file_handler in target_logger.handlers:
                    target_logger.removeHandler(self._file_handler)

            self._file_handler.close()
            self._file_handler = None

    def __del__(self):
        """析构时确保ÎnchidereFișierProcesare器"""
        self.close()


class ReportStatus(str, Enum):
    """RaportStare"""

    PENDING = "pending"
    PLANNING = "planning"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ReportSection:
    """Raport章节"""

    title: str
    content: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"title": self.title, "content": self.content}

    def to_markdown(self, level: int = 2) -> str:
        """转换为MarkdownFormat"""
        md = f"{'#' * level} {self.title}\n\n"
        if self.content:
            md += f"{self.content}\n\n"
        return md


@dataclass
class ReportOutline:
    """Raport大纲"""

    title: str
    summary: str
    sections: List[ReportSection]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "summary": self.summary,
            "sections": [s.to_dict() for s in self.sections],
        }

    def to_markdown(self) -> str:
        """转换为MarkdownFormat"""
        md = f"# {self.title}\n\n"
        md += f"> {self.summary}\n\n"
        for section in self.sections:
            md += section.to_markdown()
        return md


@dataclass
class Report:
    """完整Raport"""

    report_id: str
    simulation_id: str
    graph_id: str
    simulation_requirement: str
    status: ReportStatus
    outline: Optional[ReportOutline] = None
    markdown_content: str = ""
    created_at: str = ""
    completed_at: str = ""
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "simulation_id": self.simulation_id,
            "graph_id": self.graph_id,
            "simulation_requirement": self.simulation_requirement,
            "status": self.status.value,
            "outline": self.outline.to_dict() if self.outline else None,
            "markdown_content": self.markdown_content,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "error": self.error,
        }


# ═══════════════════════════════════════════════════════════════
# Prompt 模板常量
# ═══════════════════════════════════════════════════════════════

# ── InstrumentDescriere ──

TOOL_DESC_INSIGHT_FORGE = """\
【深度洞察检索 - 强大检索Instrument】
这Da我们强大检索Funcție，专为深度Analiză设计。它会：
1. 自动将你问题分解为多个子问题
2. de la多个维度检索SimulareGrafInformații
3. 整合语义搜索、EntitateAnaliză、Relație链追踪Rezultat
4. Înapoi最全面、最深度检索Conținut

【Utilizare场景】
- 需要深入Analiză某个Subiect
- 需要解事件多个方面
- 需要Obținere支撑Raport章节丰富素材

【ÎnapoiConținut】
- 相关事实原文（可直接引用）
- 核心Entitate洞察
- Relație链Analiză"""

TOOL_DESC_PANORAMA_SEARCH = """\
【广度搜索 - Obținere全貌视图】
这个Instrument用于ObținereSimulareRezultat完整全貌，特别适合解事件演变过程。它会：
1. Obținere所有相关NodșiRelație
2. 区分când前有效事实și历史/过期事实
3. Ajutor你解舆情Da如何演变

【Utilizare场景】
- 需要解事件完整发展脉络
- 需要对比不同阶段舆情变化
- 需要Obținere全面EntitateșiRelațieInformații

【ÎnapoiConținut】
- când前有效事实（Simulare最新Rezultat）
- 历史/过期事实（演变Înregistrare）
- 所有涉及Entitate"""

TOOL_DESC_QUICK_SEARCH = """\
【简单搜索 - 快速检索】
轻量级快速检索Instrument，适合简单、直接InformațiiInterogare。

【Utilizare场景】
- 需要快速查找某个具体Informații
- 需要Verificare某个事实
- 简单Informații检索

【ÎnapoiConținut】
- șiInterogare最相关事实Listă"""

TOOL_DESC_INTERVIEW_AGENTS = """\
【深度采访 - Adevărat实Agent采访（双Platformă）】
调用OASISSimulareMediu采访API，对正înRulareSimulareAgent进行Adevărat实采访！
这不DaLLMSimulare，而Da调用Adevărat实采访InterfațăObținereSimulareAgent原始回答。
默认înTwitterșiReddit两个Platformă同时采访，Obținere更全面Opinie。

Funcționalitate流程：
1. 自动读取人设Fișier，解所有SimulareAgent
2. 智能Selectareși采访主题最相关Agent（如学生、媒体、官方等）
3. 自动Generare采访问题
4. 调用 /api/simulation/interview/batch Interfațăîn双Platformă进行Adevărat实采访
5. 整合所有采访Rezultat，提供多视角Analiză

【Utilizare场景】
- 需要de la不同Rol视角解事件看法（学生怎么看？媒体怎么看？官方怎么说？）
- 需要收集多方意见și立场
- 需要ObținereSimulareAgentAdevărat实回答（来自OASISSimulareMediu）
- 想让Raport更生动，包含"采访实录"

【ÎnapoiConținut】
- 被采访Agent身份Informații
- 各AgentînTwitterșiReddit两个Platformă采访回答
- 关Cheie引言（可直接引用）
- 采访摘要șiOpinie对比

【重要】需要OASISSimulareMediu正înRulare才能Utilizare此Funcționalitate！"""

# ── Prompt Planificare Schiță ──

PLAN_SYSTEM_PROMPT = """\
Ești un expert în redactarea de "Rapoarte de Predicție a Viitorului", având o "Perspectivă Globală" asupra lumii simulate — poți observa comportamentul, declarațiile și interacțiunile fiecărui Agent din simulare.

【Conceptul Fundamental】
Am construit o lume simulată și am injectat o "Cerință de Simulare" specifică ca variabilă. Rezultatul evoluției lumii simulate este o predicție a ceea ce s-ar putea întâmpla în viitor. Ceea ce observi nu sunt "date experimentale", ci o "repetiție a viitorului".

【Sarcina Ta】
Redactează un "Raport de Predicție a Viitorului" care răspunde la:
1. În condițiile stabilite de noi, ce se întâmplă în viitor?
2. Cum reacționează și acționează diferitele categorii de Agente (populații)?
3. Ce tendințe și riscuri viitoare demne de atenție dezvăluie această simulare?

【Poziționarea Raportului】
- ✅ Acesta este un raport de predicție viitor bazat pe simulare, dezvăluind "dacă se întâmplă asta, cum va fi viitorul"
- ✅ Se concentrează pe rezultatele predicției: evoluția evenimentelor, reacțiile grupurilor, fenomenele emergente, riscurile potențiale
- ✅ Comportamentele și declarațiile Agentei în lumea simulată sunt predicții ale comportamentului viitor al populațiilor
- ❌ Nu este o analiză a situației actuale din lumea reală
- ❌ Nu este o prezentare generală a opiniei publice

【Limita Numărului de Capitole】
- Minimum 2 capitole, maximum 5 capitole
- Nu sunt necesare sub-capitole, fiecare capitol conține conținut complet direct
- Conținutul trebuie să fie concis, concentrat pe descoperirile predictive esențiale
- Structura capitolelor este proiectată de tine în funcție de rezultatele predicției

Te rugăm să generezi schița raportului în format JSON, după cum urmează:
{
    "title": "Titlul raportului",
    "summary": "Rezumatul raportului (o propoziție care sintetizează descoperirea predictivă principală)",
    "sections": [
        {
            "title": "Titlul capitolului",
            "description": "Descrierea conținutului capitolului"
        }
    ]
}

Notă: Array-ul sections trebuie să aibă minimum 2 și maximum 5 elemente!"""

PLAN_USER_PROMPT_TEMPLATE = """\
【Setarea Scenariului Predictiv】
Variabila injectată în lumea simulată (cerință de simulare): {simulation_requirement}

【Scala Lumii Simulate】
- Număr de entități participante: {total_nodes}
- Număr de relații generate între entități: {total_edges}
- Distribuția tipurilor de entități: {entity_types}
- Număr de Agente active: {total_entities}

【Eșantion de Fapte Viitoare Predicționate】
{related_facts_json}

Te rugăm să examinezi această repetiție a viitorului din "Perspectiva Globală":
1. În condițiile stabilite de noi, ce stare prezintă viitorul?
2. Cum reacționează și acționează diferitele categorii de populații (Agente)?
3. Ce tendințe viitoare demne de atenție dezvăluie această simulare?

Proiectează cea mai potrivită structură de capitole pentru raport în funcție de rezultatele predicției.

【Reamintire】Numărul de capitole al raportului: minimum 2, maximum 5, conținutul trebuie să fie concis și concentrat pe descoperirile predictive esențiale."""

# ── Prompt Generare Capitol ──

SECTION_SYSTEM_PROMPT_TEMPLATE = """\
Ești un expert în redactarea de "Rapoarte de Predicție a Viitorului" și redactezi un capitol al raportului.

RaportTitlu: {report_title}
Raport摘要: {report_summary}
预测场景（SimulareCerință）: {simulation_requirement}

când前要撰写章节: {section_title}

═══════════════════════════════════════════════════════════════
【核心理念】
═══════════════════════════════════════════════════════════════

Lumea simulată este o repetiție a viitorului. Am injectat condiții specifice (cerință de simulare) în lumea simulată,
comportamentele și interacțiunile Agentei reprezintă predicții ale comportamentului viitor al populațiilor.

Sarcina ta este:
- Dezvăluie ce se întâmplă în viitor în condițiile stabilite
- Prezice cum reacționează și acționează diferitele categorii de populații (Agente)
- Descoperă tendințe, riscuri și oportunități viitoare demne de atenție

❌ Nu redacta ca o analiză a situației actuale din lumea reală
✅ Concentrează-te pe "cum va fi viitorul" — rezultatele simulării reprezintă viitorul prezis

═══════════════════════════════════════════════════════════════
【Cele Mai Importante Reguli - Trebuie Respectate】
═══════════════════════════════════════════════════════════════

1. 【Trebuie să apelezi instrumente pentru a observa lumea simulată】
   - Observi repetiția viitorului din "Perspectiva Globală"
   - Tot conținutul trebuie să provină din evenimentele și comportamentele Agentei din lumea simulată
   - Este interzisă utilizarea propriilor cunoștințe pentru redactarea conținutului raportului
   - Fiecare capitol trebuie să apeleze instrumente de 3-5 ori (maximum) pentru a observa lumea simulată, care reprezintă viitorul

2. 【Trebuie să citezi comportamentele și declarațiile originale ale Agentei】
   - Declarațiile și comportamentele Agentei sunt predicții ale comportamentului viitor al populațiilor
   - Folosește format de citare în raport pentru a prezenta aceste predicții, de exemplu:
     > "O anumită categorie de populație va declara: conținutul original..."
   - Aceste citate sunt dovezi predictive esențiale ale simulării

3. 【Consistența Lingvistică - Conținutul citat trebuie tradus în limba raportului】
   - Conținutul returnat de instrumente poate conține expresii în engleză sau mix englez-română
   - Dacă cerința de simulare și materialele originale sunt în română, raportul trebuie redactat complet în română
   - Când citezi conținut în engleză sau mix returnat de instrumente, trebuie să-l traduci în română fluentă înainte de a-l include în raport
   - La traducere, păstrează sensul original, asigurând o exprimare naturală și fluentă
   - Această regulă se aplică atât conținutului principal, cât și citatelor (format >)

4. 【Prezentarea Fidelă a Rezultatelor Predictive】
   - Conținutul raportului trebuie să reflecte rezultatele simulării care reprezintă viitorul
   - Nu adăuga informații care nu există în simulare
   - Dacă informațiile despre un anumit aspect sunt insuficiente, indică acest lucru onest

═══════════════════════════════════════════════════════════════
【⚠️ Specificații de Formatare - Extrem de Importante!】
═══════════════════════════════════════════════════════════════

【Un Capitol = Unitate Minimă de Conținut】
- Fiecare capitol este unitatea minimă de divizare a raportului
- ❌ Este interzisă utilizarea oricărui titlu Markdown în capitol (#, ##, ###, #### etc.)
- ❌ Este interzisă adăugarea titlului principal al capitolului la începutul conținutului
- ✅ Titlul capitolului este adăugat automat de sistem, tu trebuie doar să redactezi conținutul pur
- ✅ Folosește **text bold**, separatoare de paragrafe, citate, liste pentru a organiza conținutul, dar nu folosi titluri

【Exemplu Corect】
```
Acest capitol analizează evoluția răspândirii opiniei publice despre eveniment. Prin analiza profundă a datelor simulate, am descoperit...

**首发引爆阶段**

微博作为舆情第一现场，承担Informații首发核心Funcționalități:

> "微博贡献68%首发声量..."

**Emoție放大阶段**

抖音Platformă进一步放大事件影响力：

- 视觉冲击力强
- Emoție共鸣度高
```

【Exemplu Incorect】
```
## Rezumat Executiv          ← Eroare! Nu adăuga niciun titlu
### 1. Faza Inițială     ← Eroare! Nu folosi ### pentru sub-secțiuni
#### 1.1 Analiză Detaliată   ← Eroare! Nu folosi #### pentru subdivizare

本章节Analiză...
```

═══════════════════════════════════════════════════════════════
【Instrumente de Căutare Disponibile】 (3-5 apeluri per capitol)
═══════════════════════════════════════════════════════════════

{tools_description}

【Recomandări Utilizare Instrumente - Folosește instrumente diferite, nu doar unul】
- insight_forge: Analiză profundă, decompune automat problema și caută fapte și relații multi-dimensionale
- panorama_search: Căutare panoramică largă, înțelege imaginea de ansamblu a evenimentului, cronologia și procesul de evoluție
- quick_search: Verificare rapidă a unui punct specific de informație
- interview_agents: Intervievează Agente simulate, obține puncte de vedere în primă persoană și reacții reale ale diferitelor roluri

═══════════════════════════════════════════════════════════════
【Flux de Lucru】
═══════════════════════════════════════════════════════════════

La fiecare răspuns poți face doar unul dintre următoarele două (nu simultan):

Opțiunea A - Apelare instrument:
Expune-ți gândirea, apoi apelează un instrument folosind formatul:
<tool_call>
{{"name": "InstrumentNume", "parameters": {{"Parametru名": "ParametruValoare"}}}}
</tool_call>
Sistemul va executa instrumentul și va returna rezultatele. Nu trebuie și nu poți scrie tu rezultatele instrumentului.

Opțiunea B - Generare conținut final:
Când ai obținut suficiente informații prin instrumente, începe capitolul cu "Răspuns Final:"

⚠️ Strict Interzis:
- Este interzis să incluzi simultan apelul instrumentului și Răspunsul Final într-un singur răspuns
- Este interzis să inventezi rezultatele instrumentului (Observation), toate rezultatele sunt injectate de sistem
- Maximum un apel de instrument per răspuns

═══════════════════════════════════════════════════════════════
【Cerințe Conținut Capitol】
═══════════════════════════════════════════════════════════════

1. Conținutul trebuie bazat pe datele simulate obținute prin instrumente
2. Citează abundent textul original pentru a demonstra efectele simulării
3. Folosește format Markdown (dar fără titluri):
   - Folosește **text bold** pentru a marca punctele cheie (în loc de sub-titluri)
   - Folosește liste (- sau 1.2.3.) pentru a organiza punctele
   - Folosește linii goale pentru a separa paragrafele
   - ❌ Este interzisă utilizarea oricărei sintaxe de titlu #, ##, ###, ####
4. 【Specificații Format Citare - Trebuie să fie în paragraf separat】
   Citatele trebuie să fie în paragraf independent, cu o linie goală înainte și după, nu amestecate în paragraf:

   ✅ Format Corect:
   ```
   Răspunsul instituției a fost considerat lipsit de substanță.

   > "校方应对模式în瞬息万变社交媒体Mediu显得僵化și迟缓。"

   Această evaluare reflectă nemulțumirea generală a publicului.
   ```

   ❌ Format Incorect:
   ```
   Răspunsul instituției a fost considerat lipsit de substanță.> "校方应对模式..." 这一评价反映...
   ```
5. Menține coerența logică cu celelalte capitole
6. 【Evită Repetarea】Citește cu atenție capitolele finalizate de mai jos, nu repeta aceleași informații
7. 【Reamintire】Nu adăuga niciun titlu! Folosește **bold** în loc de sub-titluri"""

SECTION_USER_PROMPT_TEMPLATE = """\
Conținutul capitolelor finalizate (citește cu atenție, evită repetarea):
{previous_content}

═══════════════════════════════════════════════════════════════
【Sarcina Curentă】Redactează capitolul: {section_title}
═══════════════════════════════════════════════════════════════

【Reamintire Importantă】
1. Citește cu atenție capitolele finalizate de mai sus, evită repetarea aceluiași conținut!
2. Înainte de a începe, trebuie să apelezi instrumente pentru a obține date simulate
3. Folosește instrumente diferite, nu doar unul
4. Conținutul raportului trebuie să provină din rezultatele căutării, nu folosi propriile cunoștințe

【⚠️ Avertisment Formatare - Trebuie Respectat】
- ❌ Nu scrie niciun titlu (#, ##, ###, #### - toate interzise)
- ❌ Nu scrie "{section_title}" ca început
- ✅ Titlul capitolului este adăugat automat de sistem
- ✅ Scrie direct conținutul, folosește **bold** în loc de sub-titluri

请Start：
1. Mai întâi gândește-te (Thought) ce informații are nevoie acest capitol
2. Apoi apelează instrumentul (Action) pentru a obține date simulate
3. După colectarea suficientelor informații, generează Răspuns Final (doar conținut, fără titluri)"""

# ── Șabloane Mesaje în Buclă ReACT ──

REACT_OBSERVATION_TEMPLATE = """\
Observation (Rezultat Căutare):

═══ Instrumentul {tool_name} Returnează ═══
{result}

═══════════════════════════════════════════════════════════════
Apelează instrumentul de {tool_calls_count}/{max_tool_calls} ori (folosit: {used_tools_str}) {unused_hint}
- Dacă informațiile sunt suficiente: începe capitolul cu "Răspuns Final:" (trebuie să citezi textul original de mai sus)
- Dacă sunt necesare mai multe informații: apelează un instrument pentru a continua căutarea
═══════════════════════════════════════════════════════════════"""

REACT_INSUFFICIENT_TOOLS_MSG = (
    "【Atenție】Ai apelat instrumentul de doar {tool_calls_count} ori, minimul este {min_tool_calls}."
    "Te rugăm să apelezi din nou instrumentul pentru mai multe date simulate, apoi generează Răspuns Final. {unused_hint}"
)

REACT_INSUFFICIENT_TOOLS_MSG_ALT = (
    "Ai apelat instrumentul de doar {tool_calls_count} ori, minimul este {min_tool_calls}."
    "Te rugăm să apelezi instrumentul pentru a obține date simulate. {unused_hint}"
)

REACT_TOOL_LIMIT_MSG = (
    "Numărul maxim de apeluri instrument a fost atins ({tool_calls_count}/{max_tool_calls}), nu se mai pot face apeluri."
    'Te rugăm să generezi imediat conținutul capitolului începând cu "Răspuns Final:" bazat pe informațiile obținute.'
)

REACT_UNUSED_TOOLS_HINT = (
    "\n💡 Nu ai folosit încă: {unused_list}, se recomandă să încerci instrumente diferite pentru informații multi-dimensionale"
)

REACT_FORCE_FINAL_MSG = "S-a atins limita de apeluri instrument, te rugăm să generezi direct Răspuns Final: și conținutul capitolului."

# ── Prompt Chat ──

CHAT_SYSTEM_PROMPT_TEMPLATE = """\
Ești un asistent concis și eficient pentru predicții simulate.

【Context】
Condiții predicție: {simulation_requirement}

【Raport de Analiză Generat】
{report_content}

【Reguli】
1. Prioritizează răspunsul pe baza conținutului raportului de mai sus
2. Răspunde direct la întrebare, evită expuneri lungi de gândire
3. Apelează instrumente pentru căutarea a mai multor date doar când conținutul raportului este insuficient
4. Răspunsul trebuie să fie concis, clar și structurat

【Instrumente Disponibile】 (folosește doar când e necesar, maximum 1-2 apeluri)
{tools_description}

【Format Apel Instrument】
<tool_call>
{{"name": "InstrumentNume", "parameters": {{"Parametru名": "ParametruValoare"}}}}
</tool_call>

【Stil Răspuns】
- Concis și direct, nu expuneri lungi
- Folosește formatul > pentru a cita conținutul cheie
- Oferă mai întâi concluzia, apoi explică motivele"""

CHAT_OBSERVATION_SUFFIX = "\n\nTe rugăm să răspunzi concis la întrebare."


# ═══════════════════════════════════════════════════════════════
# Clasa Principală ReportAgent
# ═══════════════════════════════════════════════════════════════


class ReportAgent:
    """
    Report Agent - SimulareRaportGenerareAgent

    采用ReACT（Reasoning + Acting）模式：
    1. 规划阶段：AnalizăSimulareCerință，规划RaportDirector结构
    2. Generare阶段：逐章节GenerareConținut，每章节可多次调用InstrumentObținereInformații
    3. 反思阶段：VerificareConținut完整性și准确性
    """

    # 最大Instrument调用次数（每个章节）
    MAX_TOOL_CALLS_PER_SECTION = 5

    # 最大反思轮数
    MAX_REFLECTION_ROUNDS = 3

    # 对话最大Instrument调用次数
    MAX_TOOL_CALLS_PER_CHAT = 2

    def __init__(
        self,
        graph_id: str,
        simulation_id: str,
        simulation_requirement: str,
        llm_client: Optional[LLMClient] = None,
        zep_tools: Optional[ZepToolsService] = None,
    ):
        """
        InițializareReport Agent

        Args:
            graph_id: GrafID
            simulation_id: SimulareID
            simulation_requirement: SimulareCerințăDescriere
            llm_client: LLM客户端（可选）
            zep_tools: ZepInstrumentServiciu（可选）
        """
        self.graph_id = graph_id
        self.simulation_id = simulation_id
        self.simulation_requirement = simulation_requirement

        self.llm = llm_client or LLMClient()
        self.zep_tools = zep_tools or ZepToolsService()

        # Instrument定义
        self.tools = self._define_tools()

        # JurnalÎnregistrare器（în generate_report Inițializare）
        self.report_logger: Optional[ReportLogger] = None
        # ConsolăJurnalÎnregistrare器（în generate_report Inițializare）
        self.console_logger: Optional[ReportConsoleLogger] = None

        logger.info(
            f"ReportAgent InițializareFinalizare: graph_id={graph_id}, simulation_id={simulation_id}"
        )

    def _define_tools(self) -> Dict[str, Dict[str, Any]]:
        """定义可用Instrument"""
        return {
            "insight_forge": {
                "name": "insight_forge",
                "description": TOOL_DESC_INSIGHT_FORGE,
                "parameters": {
                    "query": "你想深入Analiză问题sauSubiect",
                    "report_context": "când前Raport章节文（可选，有助于Generare更精准子问题）",
                },
            },
            "panorama_search": {
                "name": "panorama_search",
                "description": TOOL_DESC_PANORAMA_SEARCH,
                "parameters": {
                    "query": "搜索Interogare，用于相关性排序",
                    "include_expired": "DaNu包含过期/历史Conținut（默认True）",
                },
            },
            "quick_search": {
                "name": "quick_search",
                "description": TOOL_DESC_QUICK_SEARCH,
                "parameters": {
                    "query": "搜索InterogareȘir",
                    "limit": "ÎnapoiRezultat数量（可选，默认10）",
                },
            },
            "interview_agents": {
                "name": "interview_agents",
                "description": TOOL_DESC_INTERVIEW_AGENTS,
                "parameters": {
                    "interview_topic": "采访主题sauCerințăDescriere（如：'解学生对宿舍甲醛事件看法'）",
                    "max_agents": "最多采访Agent数量（可选，默认5，最大10）",
                },
            },
        }

    def _execute_tool(
        self, tool_name: str, parameters: Dict[str, Any], report_context: str = ""
    ) -> str:
        """
        执行Instrument调用

        Args:
            tool_name: InstrumentNume
            parameters: InstrumentParametru
            report_context: Raport文（用于InsightForge）

        Returns:
            Instrument执行Rezultat（文本Format）
        """
        logger.info(f"执行Instrument: {tool_name}, Parametru: {parameters}")

        try:
            if tool_name == "insight_forge":
                query = parameters.get("query", "")
                ctx = parameters.get("report_context", "") or report_context
                result = self.zep_tools.insight_forge(
                    graph_id=self.graph_id,
                    query=query,
                    simulation_requirement=self.simulation_requirement,
                    report_context=ctx,
                )
                return result.to_text()

            elif tool_name == "panorama_search":
                # 广度搜索 - Obținere全貌
                query = parameters.get("query", "")
                include_expired = parameters.get("include_expired", True)
                if isinstance(include_expired, str):
                    include_expired = include_expired.lower() in ["true", "1", "yes"]
                result = self.zep_tools.panorama_search(
                    graph_id=self.graph_id, query=query, include_expired=include_expired
                )
                return result.to_text()

            elif tool_name == "quick_search":
                # 简单搜索 - 快速检索
                query = parameters.get("query", "")
                limit = parameters.get("limit", 10)
                if isinstance(limit, str):
                    limit = int(limit)
                result = self.zep_tools.quick_search(
                    graph_id=self.graph_id, query=query, limit=limit
                )
                return result.to_text()

            elif tool_name == "interview_agents":
                # 深度采访 - 调用Adevărat实OASIS采访APIObținereSimulareAgent回答（双Platformă）
                interview_topic = parameters.get(
                    "interview_topic", parameters.get("query", "")
                )
                max_agents = parameters.get("max_agents", 5)
                if isinstance(max_agents, str):
                    max_agents = int(max_agents)
                max_agents = min(max_agents, 10)
                result = self.zep_tools.interview_agents(
                    simulation_id=self.simulation_id,
                    interview_requirement=interview_topic,
                    simulation_requirement=self.simulation_requirement,
                    max_agents=max_agents,
                )
                return result.to_text()

            # ========== către后兼容旧Instrument（内部重定cătrela新Instrument） ==========

            elif tool_name == "search_graph":
                # 重定cătrela quick_search
                logger.info("search_graph 已重定cătrela quick_search")
                return self._execute_tool("quick_search", parameters, report_context)

            elif tool_name == "get_graph_statistics":
                result = self.zep_tools.get_graph_statistics(self.graph_id)
                return json.dumps(result, ensure_ascii=False, indent=2)

            elif tool_name == "get_entity_summary":
                entity_name = parameters.get("entity_name", "")
                result = self.zep_tools.get_entity_summary(
                    graph_id=self.graph_id, entity_name=entity_name
                )
                return json.dumps(result, ensure_ascii=False, indent=2)

            elif tool_name == "get_simulation_context":
                # 重定cătrela insight_forge，因为它更强大
                logger.info("get_simulation_context 已重定cătrela insight_forge")
                query = parameters.get("query", self.simulation_requirement)
                return self._execute_tool(
                    "insight_forge", {"query": query}, report_context
                )

            elif tool_name == "get_entities_by_type":
                entity_type = parameters.get("entity_type", "")
                nodes = self.zep_tools.get_entities_by_type(
                    graph_id=self.graph_id, entity_type=entity_type
                )
                result = [n.to_dict() for n in nodes]
                return json.dumps(result, ensure_ascii=False, indent=2)

            else:
                return f"未知Instrument: {tool_name}。请Utilizare以Instrument之一: insight_forge, panorama_search, quick_search"

        except Exception as e:
            logger.error(f"Instrument执行Eșec: {tool_name}, Eroare: {str(e)}")
            return f"Instrument执行Eșec: {str(e)}"

    # 合法InstrumentNumeSet，用于裸 JSON 兜底解析时校验
    VALID_TOOL_NAMES = {
        "insight_forge",
        "panorama_search",
        "quick_search",
        "interview_agents",
    }

    def _parse_tool_calls(self, response: str) -> List[Dict[str, Any]]:
        """
        de laLLMRăspuns解析Instrument调用

        SuportăFormat（按优先级）：
        1. <tool_call>{"name": "tool_name", "parameters": {...}}</tool_call>
        2. 裸 JSON（Răspuns整体sau单行就Da一个Instrument调用 JSON）
        """
        tool_calls = []

        # Format1: XML风格（标准Format）
        xml_pattern = r"<tool_call>\s*(\{.*?\})\s*</tool_call>"
        for match in re.finditer(xml_pattern, response, re.DOTALL):
            try:
                call_data = json.loads(match.group(1))
                tool_calls.append(call_data)
            except json.JSONDecodeError:
                pass

        if tool_calls:
            return tool_calls

        # Format2: 兜底 - LLM 直接Output裸 JSON（没包 <tool_call> 标签）
        # 只înFormat1未匹配时尝试，避免误匹配正文 JSON
        stripped = response.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            try:
                call_data = json.loads(stripped)
                if self._is_valid_tool_call(call_data):
                    tool_calls.append(call_data)
                    return tool_calls
            except json.JSONDecodeError:
                pass

        # Răspuns可能包含思考文字 + 裸 JSON，尝试提取最后一个 JSON Obiect
        json_pattern = r'(\{"(?:name|tool)"\s*:.*?\})\s*$'
        match = re.search(json_pattern, stripped, re.DOTALL)
        if match:
            try:
                call_data = json.loads(match.group(1))
                if self._is_valid_tool_call(call_data):
                    tool_calls.append(call_data)
            except json.JSONDecodeError:
                pass

        return tool_calls

    def _is_valid_tool_call(self, data: dict) -> bool:
        """校验解析出 JSON DaNuDa合法Instrument调用"""
        # Suportă {"name": ..., "parameters": ...} și {"tool": ..., "params": ...} 两种Cheie名
        tool_name = data.get("name") or data.get("tool")
        if tool_name and tool_name in self.VALID_TOOL_NAMES:
            # 统一Cheie名为 name / parameters
            if "tool" in data:
                data["name"] = data.pop("tool")
            if "params" in data and "parameters" not in data:
                data["parameters"] = data.pop("params")
            return True
        return False

    def _get_tools_description(self) -> str:
        """GenerareInstrumentDescriere文本"""
        desc_parts = ["可用Instrument："]
        for name, tool in self.tools.items():
            params_desc = ", ".join(
                [f"{k}: {v}" for k, v in tool["parameters"].items()]
            )
            desc_parts.append(f"- {name}: {tool['description']}")
            if params_desc:
                desc_parts.append(f"  Parametru: {params_desc}")
        return "\n".join(desc_parts)

    def plan_outline(
        self, progress_callback: Optional[Callable] = None
    ) -> ReportOutline:
        """
        规划Raport大纲

        UtilizareLLMAnalizăSimulareCerință，规划RaportDirector结构

        Args:
            progress_callback: Progres回调Funcție

        Returns:
            ReportOutline: Raport大纲
        """
        logger.info("Start规划Raport大纲...")

        if progress_callback:
            progress_callback("planning", 0, "正înAnalizăSimulareCerință...")

        # 首先ObținereSimulare文
        context = self.zep_tools.get_simulation_context(
            graph_id=self.graph_id, simulation_requirement=self.simulation_requirement
        )

        if progress_callback:
            progress_callback("planning", 30, "正înGenerareRaport大纲...")

        system_prompt = PLAN_SYSTEM_PROMPT
        user_prompt = PLAN_USER_PROMPT_TEMPLATE.format(
            simulation_requirement=self.simulation_requirement,
            total_nodes=context.get("graph_statistics", {}).get("total_nodes", 0),
            total_edges=context.get("graph_statistics", {}).get("total_edges", 0),
            entity_types=list(
                context.get("graph_statistics", {}).get("entity_types", {}).keys()
            ),
            total_entities=context.get("total_entities", 0),
            related_facts_json=json.dumps(
                context.get("related_facts", [])[:10], ensure_ascii=False, indent=2
            ),
        )

        try:
            response = self.llm.chat_json(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
            )

            if progress_callback:
                progress_callback("planning", 80, "正în解析大纲结构...")

            # 解析大纲
            sections = []
            for section_data in response.get("sections", []):
                sections.append(
                    ReportSection(title=section_data.get("title", ""), content="")
                )

            outline = ReportOutline(
                title=response.get("title", "SimulareAnalizăRaport"),
                summary=response.get("summary", ""),
                sections=sections,
            )

            if progress_callback:
                progress_callback("planning", 100, "大纲规划Finalizare")

            logger.info(f"大纲规划Finalizare: {len(sections)} 个章节")
            return outline

        except Exception as e:
            logger.error(f"大纲规划Eșec: {str(e)}")
            # Înapoi默认大纲（3个章节，作为fallback）
            return ReportOutline(
                title="未来预测Raport",
                summary="基于Simulare预测未来趋势și风险Analiză",
                sections=[
                    ReportSection(title="预测场景și核心发现"),
                    ReportSection(title="人群行为预测Analiză"),
                    ReportSection(title="趋势展望și风险Indicație"),
                ],
            )

    def _generate_section_react(
        self,
        section: ReportSection,
        outline: ReportOutline,
        previous_sections: List[str],
        progress_callback: Optional[Callable] = None,
        section_index: int = 0,
    ) -> str:
        """
        UtilizareReACT模式Generare单个章节Conținut

        ReACT循环：
        1. Thought（思考）- Analiză需要什么Informații
        2. Action（行动）- 调用InstrumentObținereInformații
        3. Observation（观察）- AnalizăInstrumentÎnapoiRezultat
        4. 重复直laInformații足够sau达la最大次数
        5. Final Answer（最终回答）- Generare章节Conținut

        Args:
            section: 要Generare章节
            outline: 完整大纲
            previous_sections: 之前章节Conținut（用于保持连贯性）
            progress_callback: Progres回调
            section_index: 章节Index（用于JurnalÎnregistrare）

        Returns:
            章节Conținut（MarkdownFormat）
        """
        logger.info(f"ReACTGenerare章节: {section.title}")

        # Înregistrare章节StartJurnal
        if self.report_logger:
            self.report_logger.log_section_start(section.title, section_index)

        system_prompt = SECTION_SYSTEM_PROMPT_TEMPLATE.format(
            report_title=outline.title,
            report_summary=outline.summary,
            simulation_requirement=self.simulation_requirement,
            section_title=section.title,
            tools_description=self._get_tools_description(),
        )

        # ConstruireUtilizatorprompt - 每个已Finalizare章节各传入最大4000字
        if previous_sections:
            previous_parts = []
            for sec in previous_sections:
                # 每个章节最多4000字
                truncated = sec[:4000] + "..." if len(sec) > 4000 else sec
                previous_parts.append(truncated)
            previous_content = "\n\n---\n\n".join(previous_parts)
        else:
            previous_content = "（这Da第一个章节）"

        user_prompt = SECTION_USER_PROMPT_TEMPLATE.format(
            previous_content=previous_content,
            section_title=section.title,
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        # ReACT循环
        tool_calls_count = 0
        max_iterations = 5  # 最大迭代轮数
        min_tool_calls = 3  # 最少Instrument调用次数
        conflict_retries = 0  # Instrument调用șiFinal Answer同时出现连续冲突次数
        used_tools = set()  # Înregistrare已调用过Instrument名
        all_tools = {
            "insight_forge",
            "panorama_search",
            "quick_search",
            "interview_agents",
        }

        # Raport文，用于InsightForge子问题Generare
        report_context = (
            f"章节Titlu: {section.title}\nSimulareCerință: {self.simulation_requirement}"
        )

        for iteration in range(max_iterations):
            if progress_callback:
                progress_callback(
                    "generating",
                    int((iteration / max_iterations) * 100),
                    f"深度检索și撰写 ({tool_calls_count}/{self.MAX_TOOL_CALLS_PER_SECTION})",
                )

            # 调用LLM
            response = self.llm.chat(
                messages=messages, temperature=0.5, max_tokens=4096
            )

            # Verificare LLM ÎnapoiDaNu为 None（API ExcepțiesauConținut为Gol）
            if response is None:
                logger.warning(
                    f"章节 {section.title} 第 {iteration + 1} 次迭代: LLM Înapoi None"
                )
                # dacă还有迭代次数，添加Mesaj并Reîncearcă
                if iteration < max_iterations - 1:
                    messages.append({"role": "assistant", "content": "（Răspuns为Gol）"})
                    messages.append({"role": "user", "content": "请ContinuareGenerareConținut。"})
                    continue
                # 最后一次迭代也Înapoi None，跳出循环进入强制收尾
                break

            logger.debug(f"LLMRăspuns: {response[:200]}...")

            # 解析一次，复用Rezultat
            tool_calls = self._parse_tool_calls(response)
            has_tool_calls = bool(tool_calls)
            has_final_answer = "Final Answer:" in response

            # ── 冲突Procesare：LLM 同时OutputInstrument调用și Final Answer ──
            if has_tool_calls and has_final_answer:
                conflict_retries += 1
                logger.warning(
                    f"章节 {section.title} 第 {iteration + 1} 轮: "
                    f"LLM 同时OutputInstrument调用și Final Answer（第 {conflict_retries} 次冲突）"
                )

                if conflict_retries <= 2:
                    # 前两次：丢弃本次Răspuns，要求 LLM 重新Răspuns
                    messages.append({"role": "assistant", "content": response})
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                "【FormatEroare】你în一次Răspuns同时包含Instrument调用și Final Answer，这Da不允许。\n"
                                "每次Răspuns只能做以两件事之一：\n"
                                "- 调用一个Instrument（Output一个 <tool_call> 块，不要写 Final Answer）\n"
                                "- Output最终Conținut（以 'Final Answer:' 开头，不要包含 <tool_call>）\n"
                                "请重新Răspuns，只做其一件事。"
                            ),
                        }
                    )
                    continue
                else:
                    # 第三次：降级Procesare，截断la第一个Instrument调用，强制执行
                    logger.warning(
                        f"章节 {section.title}: 连续 {conflict_retries} 次冲突，"
                        "降级为截断执行第一个Instrument调用"
                    )
                    first_tool_end = response.find("</tool_call>")
                    if first_tool_end != -1:
                        response = response[: first_tool_end + len("</tool_call>")]
                        tool_calls = self._parse_tool_calls(response)
                        has_tool_calls = bool(tool_calls)
                    has_final_answer = False
                    conflict_retries = 0

            # Înregistrare LLM RăspunsJurnal
            if self.report_logger:
                self.report_logger.log_llm_response(
                    section_title=section.title,
                    section_index=section_index,
                    response=response,
                    iteration=iteration + 1,
                    has_tool_calls=has_tool_calls,
                    has_final_answer=has_final_answer,
                )

            # ── 情况1：LLM Output Final Answer ──
            if has_final_answer:
                # Instrument调用次数不足，拒绝并要求Continuare调Instrument
                if tool_calls_count < min_tool_calls:
                    messages.append({"role": "assistant", "content": response})
                    unused_tools = all_tools - used_tools
                    unused_hint = (
                        f"（这些Instrument还未Utilizare，推荐用一他们: {', '.join(unused_tools)}）"
                        if unused_tools
                        else ""
                    )
                    messages.append(
                        {
                            "role": "user",
                            "content": REACT_INSUFFICIENT_TOOLS_MSG.format(
                                tool_calls_count=tool_calls_count,
                                min_tool_calls=min_tool_calls,
                                unused_hint=unused_hint,
                            ),
                        }
                    )
                    continue

                # 正常结束
                final_answer = response.split("Final Answer:")[-1].strip()
                logger.info(
                    f"章节 {section.title} GenerareFinalizare（Instrument调用: {tool_calls_count}次）"
                )

                if self.report_logger:
                    self.report_logger.log_section_content(
                        section_title=section.title,
                        section_index=section_index,
                        content=final_answer,
                        tool_calls_count=tool_calls_count,
                    )
                return final_answer

            # ── 情况2：LLM 尝试调用Instrument ──
            if has_tool_calls:
                # Instrument额度已耗尽 → 明确告知，要求Output Final Answer
                if tool_calls_count >= self.MAX_TOOL_CALLS_PER_SECTION:
                    messages.append({"role": "assistant", "content": response})
                    messages.append(
                        {
                            "role": "user",
                            "content": REACT_TOOL_LIMIT_MSG.format(
                                tool_calls_count=tool_calls_count,
                                max_tool_calls=self.MAX_TOOL_CALLS_PER_SECTION,
                            ),
                        }
                    )
                    continue

                # 只执行第一个Instrument调用
                call = tool_calls[0]
                if len(tool_calls) > 1:
                    logger.info(
                        f"LLM 尝试调用 {len(tool_calls)} 个Instrument，只执行第一个: {call['name']}"
                    )

                if self.report_logger:
                    self.report_logger.log_tool_call(
                        section_title=section.title,
                        section_index=section_index,
                        tool_name=call["name"],
                        parameters=call.get("parameters", {}),
                        iteration=iteration + 1,
                    )

                result = self._execute_tool(
                    call["name"],
                    call.get("parameters", {}),
                    report_context=report_context,
                )

                if self.report_logger:
                    self.report_logger.log_tool_result(
                        section_title=section.title,
                        section_index=section_index,
                        tool_name=call["name"],
                        result=result,
                        iteration=iteration + 1,
                    )

                tool_calls_count += 1
                used_tools.add(call["name"])

                # Construire未UtilizareInstrumentIndicație
                unused_tools = all_tools - used_tools
                unused_hint = ""
                if unused_tools and tool_calls_count < self.MAX_TOOL_CALLS_PER_SECTION:
                    unused_hint = REACT_UNUSED_TOOLS_HINT.format(
                        unused_list="、".join(unused_tools)
                    )

                messages.append({"role": "assistant", "content": response})
                messages.append(
                    {
                        "role": "user",
                        "content": REACT_OBSERVATION_TEMPLATE.format(
                            tool_name=call["name"],
                            result=result,
                            tool_calls_count=tool_calls_count,
                            max_tool_calls=self.MAX_TOOL_CALLS_PER_SECTION,
                            used_tools_str=", ".join(used_tools),
                            unused_hint=unused_hint,
                        ),
                    }
                )
                continue

            # ── 情况3：既没有Instrument调用，也没有 Final Answer ──
            messages.append({"role": "assistant", "content": response})

            if tool_calls_count < min_tool_calls:
                # Instrument调用次数不足，推荐未用过Instrument
                unused_tools = all_tools - used_tools
                unused_hint = (
                    f"（这些Instrument还未Utilizare，推荐用一他们: {', '.join(unused_tools)}）"
                    if unused_tools
                    else ""
                )

                messages.append(
                    {
                        "role": "user",
                        "content": REACT_INSUFFICIENT_TOOLS_MSG_ALT.format(
                            tool_calls_count=tool_calls_count,
                            min_tool_calls=min_tool_calls,
                            unused_hint=unused_hint,
                        ),
                    }
                )
                continue

            # Instrument调用已足够，LLM OutputConținut但没带 "Final Answer:" 前缀
            # 直接将这段Conținut作为最终答案，不再Gol转
            logger.info(
                f"章节 {section.title} 未检测la 'Final Answer:' 前缀，直接采纳LLMOutput作为最终Conținut（Instrument调用: {tool_calls_count}次）"
            )
            final_answer = response.strip()

            if self.report_logger:
                self.report_logger.log_section_content(
                    section_title=section.title,
                    section_index=section_index,
                    content=final_answer,
                    tool_calls_count=tool_calls_count,
                )
            return final_answer

        # 达la最大迭代次数，强制GenerareConținut
        logger.warning(f"章节 {section.title} 达la最大迭代次数，强制Generare")
        messages.append({"role": "user", "content": REACT_FORCE_FINAL_MSG})

        response = self.llm.chat(messages=messages, temperature=0.5, max_tokens=4096)

        # Verificare强制收尾时 LLM ÎnapoiDaNu为 None
        if response is None:
            logger.error(
                f"章节 {section.title} 强制收尾时 LLM Înapoi None，Utilizare默认EroareIndicație"
            )
            final_answer = f"（本章节GenerareEșec：LLM ÎnapoiGolRăspuns，请稍后Reîncearcă）"
        elif "Final Answer:" in response:
            final_answer = response.split("Final Answer:")[-1].strip()
        else:
            final_answer = response

        # Înregistrare章节ConținutGenerareFinalizareJurnal
        if self.report_logger:
            self.report_logger.log_section_content(
                section_title=section.title,
                section_index=section_index,
                content=final_answer,
                tool_calls_count=tool_calls_count,
            )

        return final_answer

    def generate_report(
        self,
        progress_callback: Optional[Callable[[str, int, str], None]] = None,
        report_id: Optional[str] = None,
    ) -> Report:
        """
        Generare完整Raport（分章节实时Output）

        每个章节GenerareFinalizare后立即SalvarelaFișier夹，不需要等待整个RaportFinalizare。
        Fișier结构：
        reports/{report_id}/
            meta.json       - Raport元Informații
            outline.json    - Raport大纲
            progress.json   - GenerareProgres
            section_01.md   - 第1章节
            section_02.md   - 第2章节
            ...
            full_report.md  - 完整Raport

        Args:
            progress_callback: Progres回调Funcție (stage, progress, message)
            report_id: RaportID（可选，dacă不传则自动Generare）

        Returns:
            Report: 完整Raport
        """
        import uuid

        # dacă没有传入 report_id，则自动Generare
        if not report_id:
            report_id = f"report_{uuid.uuid4().hex[:12]}"
        start_time = datetime.now()

        report = Report(
            report_id=report_id,
            simulation_id=self.simulation_id,
            graph_id=self.graph_id,
            simulation_requirement=self.simulation_requirement,
            status=ReportStatus.PENDING,
            created_at=datetime.now().isoformat(),
        )

        # 已Finalizare章节TitluListă（用于Progres追踪）
        completed_section_titles = []

        try:
            # Inițializare：CreareRaportFișier夹并Salvare初始Stare
            ReportManager._ensure_report_folder(report_id)

            # Inițializare logger（结构化Jurnal agent_log.jsonl）
            self.report_logger = ReportLogger(report_id)
            self.report_logger.log_start(
                simulation_id=self.simulation_id,
                graph_id=self.graph_id,
                simulation_requirement=self.simulation_requirement,
            )

            # InițializareConsolăJurnalÎnregistrare器（console_log.txt）
            self.console_logger = ReportConsoleLogger(report_id)

            ReportManager.update_progress(
                report_id, "pending", 0, "InițializareRaport...", completed_sections=[]
            )
            ReportManager.save_report(report)

            # 阶段1: 规划大纲
            report.status = ReportStatus.PLANNING
            ReportManager.update_progress(
                report_id, "planning", 5, "Start规划Raport大纲...", completed_sections=[]
            )

            # Înregistrare规划StartJurnal
            self.report_logger.log_planning_start()

            if progress_callback:
                progress_callback("planning", 0, "Start规划Raport大纲...")

            outline = self.plan_outline(
                progress_callback=lambda stage, prog, msg: progress_callback(
                    stage, prog // 5, msg
                )
                if progress_callback
                else None
            )
            report.outline = outline

            # Înregistrare规划FinalizareJurnal
            self.report_logger.log_planning_complete(outline.to_dict())

            # Salvare大纲laFișier
            ReportManager.save_outline(report_id, outline)
            ReportManager.update_progress(
                report_id,
                "planning",
                15,
                f"大纲规划Finalizare，共{len(outline.sections)}个章节",
                completed_sections=[],
            )
            ReportManager.save_report(report)

            logger.info(f"大纲已SalvarelaFișier: {report_id}/outline.json")

            # 阶段2: 逐章节Generare（分章节Salvare）
            report.status = ReportStatus.GENERATING

            total_sections = len(outline.sections)
            generated_sections = []  # SalvareConținut用于文

            for i, section in enumerate(outline.sections):
                section_num = i + 1
                base_progress = 20 + int((i / total_sections) * 70)

                # ActualizareProgres
                ReportManager.update_progress(
                    report_id,
                    "generating",
                    base_progress,
                    f"正înGenerare章节: {section.title} ({section_num}/{total_sections})",
                    current_section=section.title,
                    completed_sections=completed_section_titles,
                )

                if progress_callback:
                    progress_callback(
                        "generating",
                        base_progress,
                        f"正înGenerare章节: {section.title} ({section_num}/{total_sections})",
                    )

                # Generare主章节Conținut
                section_content = self._generate_section_react(
                    section=section,
                    outline=outline,
                    previous_sections=generated_sections,
                    progress_callback=lambda stage, prog, msg: progress_callback(
                        stage, base_progress + int(prog * 0.7 / total_sections), msg
                    )
                    if progress_callback
                    else None,
                    section_index=section_num,
                )

                section.content = section_content
                generated_sections.append(f"## {section.title}\n\n{section_content}")

                # Salvare章节
                ReportManager.save_section(report_id, section_num, section)
                completed_section_titles.append(section.title)

                # Înregistrare章节FinalizareJurnal
                full_section_content = f"## {section.title}\n\n{section_content}"

                if self.report_logger:
                    self.report_logger.log_section_full_complete(
                        section_title=section.title,
                        section_index=section_num,
                        full_content=full_section_content.strip(),
                    )

                logger.info(f"章节已Salvare: {report_id}/section_{section_num:02d}.md")

                # ActualizareProgres
                ReportManager.update_progress(
                    report_id,
                    "generating",
                    base_progress + int(70 / total_sections),
                    f"章节 {section.title} 已Finalizare",
                    current_section=None,
                    completed_sections=completed_section_titles,
                )

            # 阶段3: 组装完整Raport
            if progress_callback:
                progress_callback("generating", 95, "正în组装完整Raport...")

            ReportManager.update_progress(
                report_id,
                "generating",
                95,
                "正în组装完整Raport...",
                completed_sections=completed_section_titles,
            )

            # UtilizareReportManager组装完整Raport
            report.markdown_content = ReportManager.assemble_full_report(
                report_id, outline
            )
            report.status = ReportStatus.COMPLETED
            report.completed_at = datetime.now().isoformat()

            # 计算总耗时
            total_time_seconds = (datetime.now() - start_time).total_seconds()

            # ÎnregistrareRaportFinalizareJurnal
            if self.report_logger:
                self.report_logger.log_report_complete(
                    total_sections=total_sections, total_time_seconds=total_time_seconds
                )

            # Salvare最终Raport
            ReportManager.save_report(report)
            ReportManager.update_progress(
                report_id,
                "completed",
                100,
                "RaportGenerareFinalizare",
                completed_sections=completed_section_titles,
            )

            if progress_callback:
                progress_callback("completed", 100, "RaportGenerareFinalizare")

            logger.info(f"RaportGenerareFinalizare: {report_id}")

            # ÎnchidereConsolăJurnalÎnregistrare器
            if self.console_logger:
                self.console_logger.close()
                self.console_logger = None

            return report

        except Exception as e:
            logger.error(f"RaportGenerareEșec: {str(e)}")
            report.status = ReportStatus.FAILED
            report.error = str(e)

            # ÎnregistrareEroareJurnal
            if self.report_logger:
                self.report_logger.log_error(str(e), "failed")

            # SalvareEșecStare
            try:
                ReportManager.save_report(report)
                ReportManager.update_progress(
                    report_id,
                    "failed",
                    -1,
                    f"RaportGenerareEșec: {str(e)}",
                    completed_sections=completed_section_titles,
                )
            except Exception:
                pass  # 忽略SalvareEșecEroare

            # ÎnchidereConsolăJurnalÎnregistrare器
            if self.console_logger:
                self.console_logger.close()
                self.console_logger = None

            return report

    def chat(
        self, message: str, chat_history: List[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        șiReport Agent对话

        în对话Agent可以自主调用检索Instrument来回答问题

        Args:
            message: UtilizatorMesaj
            chat_history: 对话历史

        Returns:
            {
                "response": "AgentRăspuns",
                "tool_calls": [调用InstrumentListă],
                "sources": [Informații来源]
            }
        """
        logger.info(f"Report Agent对话: {message[:50]}...")

        chat_history = chat_history or []

        # Obținere已GenerareRaportConținut
        report_content = ""
        try:
            report = ReportManager.get_report_by_simulation(self.simulation_id)
            if report and report.markdown_content:
                # 限制Raport长度，避免文过长
                report_content = report.markdown_content[:15000]
                if len(report.markdown_content) > 15000:
                    report_content += "\n\n... [RaportConținut已截断] ..."
        except Exception as e:
            logger.warning(f"ObținereRaportConținutEșec: {e}")

        system_prompt = CHAT_SYSTEM_PROMPT_TEMPLATE.format(
            simulation_requirement=self.simulation_requirement,
            report_content=report_content if report_content else "（暂无Raport）",
            tools_description=self._get_tools_description(),
        )

        # ConstruireMesaj
        messages = [{"role": "system", "content": system_prompt}]

        # 添加历史对话
        for h in chat_history[-10:]:  # 限制历史长度
            messages.append(h)

        # 添加UtilizatorMesaj
        messages.append({"role": "user", "content": message})

        # ReACT循环（简化版）
        tool_calls_made = []
        max_iterations = 2  # 减少迭代轮数

        for iteration in range(max_iterations):
            response = self.llm.chat(messages=messages, temperature=0.5)

            # 解析Instrument调用
            tool_calls = self._parse_tool_calls(response)

            if not tool_calls:
                # 没有Instrument调用，直接ÎnapoiRăspuns
                clean_response = re.sub(
                    r"<tool_call>.*?</tool_call>", "", response, flags=re.DOTALL
                )
                clean_response = re.sub(r"\[TOOL_CALL\].*?\)", "", clean_response)

                return {
                    "response": clean_response.strip(),
                    "tool_calls": tool_calls_made,
                    "sources": [
                        tc.get("parameters", {}).get("query", "")
                        for tc in tool_calls_made
                    ],
                }

            # 执行Instrument调用（限制数量）
            tool_results = []
            for call in tool_calls[:1]:  # 每轮最多执行1次Instrument调用
                if len(tool_calls_made) >= self.MAX_TOOL_CALLS_PER_CHAT:
                    break
                result = self._execute_tool(call["name"], call.get("parameters", {}))
                tool_results.append(
                    {
                        "tool": call["name"],
                        "result": result[:1500],  # 限制Rezultat长度
                    }
                )
                tool_calls_made.append(call)

            # 将Rezultat添加laMesaj
            messages.append({"role": "assistant", "content": response})
            observation = "\n".join(
                [f"[{r['tool']}Rezultat]\n{r['result']}" for r in tool_results]
            )
            messages.append(
                {"role": "user", "content": observation + CHAT_OBSERVATION_SUFFIX}
            )

        # 达la最大迭代，Obținere最终Răspuns
        final_response = self.llm.chat(messages=messages, temperature=0.5)

        # 清理Răspuns
        clean_response = re.sub(
            r"<tool_call>.*?</tool_call>", "", final_response, flags=re.DOTALL
        )
        clean_response = re.sub(r"\[TOOL_CALL\].*?\)", "", clean_response)

        return {
            "response": clean_response.strip(),
            "tool_calls": tool_calls_made,
            "sources": [
                tc.get("parameters", {}).get("query", "") for tc in tool_calls_made
            ],
        }


class ReportManager:
    """
    Raport管理器

    负责Raport持久化存储și检索

    Fișier结构（分章节Output）：
    reports/
      {report_id}/
        meta.json          - Raport元InformațiișiStare
        outline.json       - Raport大纲
        progress.json      - GenerareProgres
        section_01.md      - 第1章节
        section_02.md      - 第2章节
        ...
        full_report.md     - 完整Raport
    """

    # Raport存储Director
    REPORTS_DIR = os.path.join(Config.UPLOAD_FOLDER, "reports")

    @classmethod
    def _ensure_reports_dir(cls):
        """确保Raport根Director存în"""
        os.makedirs(cls.REPORTS_DIR, exist_ok=True)

    @classmethod
    def _get_report_folder(cls, report_id: str) -> str:
        """ObținereRaportFișier夹Cale"""
        return os.path.join(cls.REPORTS_DIR, report_id)

    @classmethod
    def _ensure_report_folder(cls, report_id: str) -> str:
        """确保RaportFișier夹存în并ÎnapoiCale"""
        folder = cls._get_report_folder(report_id)
        os.makedirs(folder, exist_ok=True)
        return folder

    @classmethod
    def _get_report_path(cls, report_id: str) -> str:
        """ObținereRaport元InformațiiFișierCale"""
        return os.path.join(cls._get_report_folder(report_id), "meta.json")

    @classmethod
    def _get_report_markdown_path(cls, report_id: str) -> str:
        """Obținere完整RaportMarkdownFișierCale"""
        return os.path.join(cls._get_report_folder(report_id), "full_report.md")

    @classmethod
    def _get_outline_path(cls, report_id: str) -> str:
        """Obținere大纲FișierCale"""
        return os.path.join(cls._get_report_folder(report_id), "outline.json")

    @classmethod
    def _get_progress_path(cls, report_id: str) -> str:
        """ObținereProgresFișierCale"""
        return os.path.join(cls._get_report_folder(report_id), "progress.json")

    @classmethod
    def _get_section_path(cls, report_id: str, section_index: int) -> str:
        """Obținere章节MarkdownFișierCale"""
        return os.path.join(
            cls._get_report_folder(report_id), f"section_{section_index:02d}.md"
        )

    @classmethod
    def _get_agent_log_path(cls, report_id: str) -> str:
        """Obținere Agent JurnalFișierCale"""
        return os.path.join(cls._get_report_folder(report_id), "agent_log.jsonl")

    @classmethod
    def _get_console_log_path(cls, report_id: str) -> str:
        """ObținereConsolăJurnalFișierCale"""
        return os.path.join(cls._get_report_folder(report_id), "console_log.txt")

    @classmethod
    def get_console_log(cls, report_id: str, from_line: int = 0) -> Dict[str, Any]:
        """
        ObținereConsolăJurnalConținut

        这DaRaportGenerare过程ConsolăOutputJurnal（INFO、WARNING等），
        și agent_log.jsonl 结构化Jurnal不同。

        Args:
            report_id: RaportID
            from_line: de la第几行Start读取（用于增量Obținere，0 表示de la头Start）

        Returns:
            {
                "logs": [Jurnal行Listă],
                "total_lines": 总行数,
                "from_line": 起始行号,
                "has_more": DaNu还有Mai multJurnal
            }
        """
        log_path = cls._get_console_log_path(report_id)

        if not os.path.exists(log_path):
            return {"logs": [], "total_lines": 0, "from_line": 0, "has_more": False}

        logs = []
        total_lines = 0

        with open(log_path, "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                total_lines = i + 1
                if i >= from_line:
                    # 保留原始Jurnal行，去掉末尾换行符
                    logs.append(line.rstrip("\n\r"))

        return {
            "logs": logs,
            "total_lines": total_lines,
            "from_line": from_line,
            "has_more": False,  # 已读取la末尾
        }

    @classmethod
    def get_console_log_stream(cls, report_id: str) -> List[str]:
        """
        Obținere完整ConsolăJurnal（一次性Obținere全部）

        Args:
            report_id: RaportID

        Returns:
            Jurnal行Listă
        """
        result = cls.get_console_log(report_id, from_line=0)
        return result["logs"]

    @classmethod
    def get_agent_log(cls, report_id: str, from_line: int = 0) -> Dict[str, Any]:
        """
        Obținere Agent JurnalConținut

        Args:
            report_id: RaportID
            from_line: de la第几行Start读取（用于增量Obținere，0 表示de la头Start）

        Returns:
            {
                "logs": [Jurnal条目Listă],
                "total_lines": 总行数,
                "from_line": 起始行号,
                "has_more": DaNu还有Mai multJurnal
            }
        """
        log_path = cls._get_agent_log_path(report_id)

        if not os.path.exists(log_path):
            return {"logs": [], "total_lines": 0, "from_line": 0, "has_more": False}

        logs = []
        total_lines = 0

        with open(log_path, "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                total_lines = i + 1
                if i >= from_line:
                    try:
                        log_entry = json.loads(line.strip())
                        logs.append(log_entry)
                    except json.JSONDecodeError:
                        # 跳过解析Eșec行
                        continue

        return {
            "logs": logs,
            "total_lines": total_lines,
            "from_line": from_line,
            "has_more": False,  # 已读取la末尾
        }

    @classmethod
    def get_agent_log_stream(cls, report_id: str) -> List[Dict[str, Any]]:
        """
        Obținere完整 Agent Jurnal（用于一次性Obținere全部）

        Args:
            report_id: RaportID

        Returns:
            Jurnal条目Listă
        """
        result = cls.get_agent_log(report_id, from_line=0)
        return result["logs"]

    @classmethod
    def save_outline(cls, report_id: str, outline: ReportOutline) -> None:
        """
        SalvareRaport大纲

        în规划阶段Finalizare后立即调用
        """
        cls._ensure_report_folder(report_id)

        with open(cls._get_outline_path(report_id), "w", encoding="utf-8") as f:
            json.dump(outline.to_dict(), f, ensure_ascii=False, indent=2)

        logger.info(f"大纲已Salvare: {report_id}")

    @classmethod
    def save_section(
        cls, report_id: str, section_index: int, section: ReportSection
    ) -> str:
        """
        Salvare单个章节

        în每个章节GenerareFinalizare后立即调用，实现分章节Output

        Args:
            report_id: RaportID
            section_index: 章节Index（de la1Start）
            section: 章节Obiect

        Returns:
            SalvareFișierCale
        """
        cls._ensure_report_folder(report_id)

        # Construire章节MarkdownConținut - 清理可能存în重复Titlu
        cleaned_content = cls._clean_section_content(section.content, section.title)
        md_content = f"## {section.title}\n\n"
        if cleaned_content:
            md_content += f"{cleaned_content}\n\n"

        # SalvareFișier
        file_suffix = f"section_{section_index:02d}.md"
        file_path = os.path.join(cls._get_report_folder(report_id), file_suffix)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(md_content)

        logger.info(f"章节已Salvare: {report_id}/{file_suffix}")
        return file_path

    @classmethod
    def _clean_section_content(cls, content: str, section_title: str) -> str:
        """
        清理章节Conținut

        1. 移除Conținut开头și章节Titlu重复MarkdownTitlu行
        2. 将所有 ### 及以级别Titlu转换为粗体文本

        Args:
            content: 原始Conținut
            section_title: 章节Titlu

        Returns:
            清理后Conținut
        """
        import re

        if not content:
            return content

        content = content.strip()
        lines = content.split("\n")
        cleaned_lines = []
        skip_next_empty = False

        for i, line in enumerate(lines):
            stripped = line.strip()

            # VerificareDaNuDaMarkdownTitlu行
            heading_match = re.match(r"^(#{1,6})\s+(.+)$", stripped)

            if heading_match:
                level = len(heading_match.group(1))
                title_text = heading_match.group(2).strip()

                # VerificareDaNuDași章节Titlu重复Titlu（跳过前5行内重复）
                if i < 5:
                    if title_text == section_title or title_text.replace(
                        " ", ""
                    ) == section_title.replace(" ", ""):
                        skip_next_empty = True
                        continue

                # 将所有级别Titlu（#, ##, ###, ####等）转换为粗体
                # 因为章节Titlu由Sistem添加，Conținut不应有任何Titlu
                cleaned_lines.append(f"**{title_text}**")
                cleaned_lines.append("")  # 添加Gol行
                continue

            # dacă一行Da被跳过Titlu，且când前行为Gol，也跳过
            if skip_next_empty and stripped == "":
                skip_next_empty = False
                continue

            skip_next_empty = False
            cleaned_lines.append(line)

        # 移除开头Gol行
        while cleaned_lines and cleaned_lines[0].strip() == "":
            cleaned_lines.pop(0)

        # 移除开头分隔线
        while cleaned_lines and cleaned_lines[0].strip() in ["---", "***", "___"]:
            cleaned_lines.pop(0)
            # 同时移除分隔线后Gol行
            while cleaned_lines and cleaned_lines[0].strip() == "":
                cleaned_lines.pop(0)

        return "\n".join(cleaned_lines)

    @classmethod
    def update_progress(
        cls,
        report_id: str,
        status: str,
        progress: int,
        message: str,
        current_section: str = None,
        completed_sections: List[str] = None,
    ) -> None:
        """
        ActualizareRaportGenerareProgres

        前端可以通过读取progress.jsonObținere实时Progres
        """
        cls._ensure_report_folder(report_id)

        progress_data = {
            "status": status,
            "progress": progress,
            "message": message,
            "current_section": current_section,
            "completed_sections": completed_sections or [],
            "updated_at": datetime.now().isoformat(),
        }

        with open(cls._get_progress_path(report_id), "w", encoding="utf-8") as f:
            json.dump(progress_data, f, ensure_ascii=False, indent=2)

    @classmethod
    def get_progress(cls, report_id: str) -> Optional[Dict[str, Any]]:
        """ObținereRaportGenerareProgres"""
        path = cls._get_progress_path(report_id)

        if not os.path.exists(path):
            return None

        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    @classmethod
    def get_generated_sections(cls, report_id: str) -> List[Dict[str, Any]]:
        """
        Obținere已Generare章节Listă

        Înapoi所有已Salvare章节FișierInformații
        """
        folder = cls._get_report_folder(report_id)

        if not os.path.exists(folder):
            return []

        sections = []
        for filename in sorted(os.listdir(folder)):
            if filename.startswith("section_") and filename.endswith(".md"):
                file_path = os.path.join(folder, filename)
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()

                # de laFișier名解析章节Index
                parts = filename.replace(".md", "").split("_")
                section_index = int(parts[1])

                sections.append(
                    {
                        "filename": filename,
                        "section_index": section_index,
                        "content": content,
                    }
                )

        return sections

    @classmethod
    def assemble_full_report(cls, report_id: str, outline: ReportOutline) -> str:
        """
        组装完整Raport

        de la已Salvare章节Fișier组装完整Raport，并进行Titlu清理
        """
        folder = cls._get_report_folder(report_id)

        # ConstruireRaport头部
        md_content = f"# {outline.title}\n\n"
        md_content += f"> {outline.summary}\n\n"
        md_content += f"---\n\n"

        # 按顺序读取所有章节Fișier
        sections = cls.get_generated_sections(report_id)
        for section_info in sections:
            md_content += section_info["content"]

        # 后Procesare：清理整个RaportTitlu问题
        md_content = cls._post_process_report(md_content, outline)

        # Salvare完整Raport
        full_path = cls._get_report_markdown_path(report_id)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(md_content)

        logger.info(f"完整Raport已组装: {report_id}")
        return md_content

    @classmethod
    def _post_process_report(cls, content: str, outline: ReportOutline) -> str:
        """
        后ProcesareRaportConținut

        1. 移除重复Titlu
        2. 保留Raport主Titlu(#)și章节Titlu(##)，移除其他级别Titlu(###, ####等)
        3. 清理多余Gol行și分隔线

        Args:
            content: 原始RaportConținut
            outline: Raport大纲

        Returns:
            Procesare后Conținut
        """
        import re

        lines = content.split("\n")
        processed_lines = []
        prev_was_heading = False

        # 收集大纲所有章节Titlu
        section_titles = set()
        for section in outline.sections:
            section_titles.add(section.title)

        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            # VerificareDaNuDaTitlu行
            heading_match = re.match(r"^(#{1,6})\s+(.+)$", stripped)

            if heading_match:
                level = len(heading_match.group(1))
                title = heading_match.group(2).strip()

                # VerificareDaNuDa重复Titlu（în连续5行内出现相同ConținutTitlu）
                is_duplicate = False
                for j in range(max(0, len(processed_lines) - 5), len(processed_lines)):
                    prev_line = processed_lines[j].strip()
                    prev_match = re.match(r"^(#{1,6})\s+(.+)$", prev_line)
                    if prev_match:
                        prev_title = prev_match.group(2).strip()
                        if prev_title == title:
                            is_duplicate = True
                            break

                if is_duplicate:
                    # 跳过重复Titlu及其后Gol行
                    i += 1
                    while i < len(lines) and lines[i].strip() == "":
                        i += 1
                    continue

                # Titlu层级Procesare：
                # - # (level=1) 只保留Raport主Titlu
                # - ## (level=2) 保留章节Titlu
                # - ### 及以 (level>=3) 转换为粗体文本

                if level == 1:
                    if title == outline.title:
                        # 保留Raport主Titlu
                        processed_lines.append(line)
                        prev_was_heading = True
                    elif title in section_titles:
                        # 章节TitluEroareUtilizare#，修正为##
                        processed_lines.append(f"## {title}")
                        prev_was_heading = True
                    else:
                        # 其他一级Titlu转为粗体
                        processed_lines.append(f"**{title}**")
                        processed_lines.append("")
                        prev_was_heading = False
                elif level == 2:
                    if title in section_titles or title == outline.title:
                        # 保留章节Titlu
                        processed_lines.append(line)
                        prev_was_heading = True
                    else:
                        # nu章节二级Titlu转为粗体
                        processed_lines.append(f"**{title}**")
                        processed_lines.append("")
                        prev_was_heading = False
                else:
                    # ### 及以级别Titlu转换为粗体文本
                    processed_lines.append(f"**{title}**")
                    processed_lines.append("")
                    prev_was_heading = False

                i += 1
                continue

            elif stripped == "---" and prev_was_heading:
                # 跳过Titlu后紧跟分隔线
                i += 1
                continue

            elif stripped == "" and prev_was_heading:
                # Titlu后只保留一个Gol行
                if processed_lines and processed_lines[-1].strip() != "":
                    processed_lines.append(line)
                prev_was_heading = False

            else:
                processed_lines.append(line)
                prev_was_heading = False

            i += 1

        # 清理连续多个Gol行（保留最多2个）
        result_lines = []
        empty_count = 0
        for line in processed_lines:
            if line.strip() == "":
                empty_count += 1
                if empty_count <= 2:
                    result_lines.append(line)
            else:
                empty_count = 0
                result_lines.append(line)

        return "\n".join(result_lines)

    @classmethod
    def save_report(cls, report: Report) -> None:
        """SalvareRaport元Informațiiși完整Raport"""
        cls._ensure_report_folder(report.report_id)

        # Salvare元InformațiiJSON
        with open(cls._get_report_path(report.report_id), "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, ensure_ascii=False, indent=2)

        # Salvare大纲
        if report.outline:
            cls.save_outline(report.report_id, report.outline)

        # Salvare完整MarkdownRaport
        if report.markdown_content:
            with open(
                cls._get_report_markdown_path(report.report_id), "w", encoding="utf-8"
            ) as f:
                f.write(report.markdown_content)

        logger.info(f"Raport已Salvare: {report.report_id}")

    @classmethod
    def get_report(cls, report_id: str) -> Optional[Report]:
        """ObținereRaport"""
        path = cls._get_report_path(report_id)

        if not os.path.exists(path):
            # 兼容旧Format：Verificare直接存储înreportsDirectorFișier
            old_path = os.path.join(cls.REPORTS_DIR, f"{report_id}.json")
            if os.path.exists(old_path):
                path = old_path
            else:
                return None

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 重建ReportObiect
        outline = None
        if data.get("outline"):
            outline_data = data["outline"]
            sections = []
            for s in outline_data.get("sections", []):
                sections.append(
                    ReportSection(title=s["title"], content=s.get("content", ""))
                )
            outline = ReportOutline(
                title=outline_data["title"],
                summary=outline_data["summary"],
                sections=sections,
            )

        # dacămarkdown_content为Gol，尝试de lafull_report.md读取
        markdown_content = data.get("markdown_content", "")
        if not markdown_content:
            full_report_path = cls._get_report_markdown_path(report_id)
            if os.path.exists(full_report_path):
                with open(full_report_path, "r", encoding="utf-8") as f:
                    markdown_content = f.read()

        return Report(
            report_id=data["report_id"],
            simulation_id=data["simulation_id"],
            graph_id=data["graph_id"],
            simulation_requirement=data["simulation_requirement"],
            status=ReportStatus(data["status"]),
            outline=outline,
            markdown_content=markdown_content,
            created_at=data.get("created_at", ""),
            completed_at=data.get("completed_at", ""),
            error=data.get("error"),
        )

    @classmethod
    def get_report_by_simulation(cls, simulation_id: str) -> Optional[Report]:
        """根据SimulareIDObținereRaport"""
        cls._ensure_reports_dir()

        for item in os.listdir(cls.REPORTS_DIR):
            item_path = os.path.join(cls.REPORTS_DIR, item)
            # 新Format：Fișier夹
            if os.path.isdir(item_path):
                report = cls.get_report(item)
                if report and report.simulation_id == simulation_id:
                    return report
            # 兼容旧Format：JSONFișier
            elif item.endswith(".json"):
                report_id = item[:-5]
                report = cls.get_report(report_id)
                if report and report.simulation_id == simulation_id:
                    return report

        return None

    @classmethod
    def list_reports(
        cls, simulation_id: Optional[str] = None, limit: int = 50
    ) -> List[Report]:
        """列出Raport"""
        cls._ensure_reports_dir()

        reports = []
        for item in os.listdir(cls.REPORTS_DIR):
            item_path = os.path.join(cls.REPORTS_DIR, item)
            # 新Format：Fișier夹
            if os.path.isdir(item_path):
                report = cls.get_report(item)
                if report:
                    if simulation_id is None or report.simulation_id == simulation_id:
                        reports.append(report)
            # 兼容旧Format：JSONFișier
            elif item.endswith(".json"):
                report_id = item[:-5]
                report = cls.get_report(report_id)
                if report:
                    if simulation_id is None or report.simulation_id == simulation_id:
                        reports.append(report)

        # 按CreareTimp倒序
        reports.sort(key=lambda r: r.created_at, reverse=True)

        return reports[:limit]

    @classmethod
    def delete_report(cls, report_id: str) -> bool:
        """ȘtergereRaport（整个Fișier夹）"""
        import shutil

        folder_path = cls._get_report_folder(report_id)

        # 新Format：Ștergere整个Fișier夹
        if os.path.exists(folder_path) and os.path.isdir(folder_path):
            shutil.rmtree(folder_path)
            logger.info(f"RaportFișier夹已Ștergere: {report_id}")
            return True

        # 兼容旧Format：Ștergere单独Fișier
        deleted = False
        old_json_path = os.path.join(cls.REPORTS_DIR, f"{report_id}.json")
        old_md_path = os.path.join(cls.REPORTS_DIR, f"{report_id}.md")

        if os.path.exists(old_json_path):
            os.remove(old_json_path)
            deleted = True
        if os.path.exists(old_md_path):
            os.remove(old_md_path)
            deleted = True

        return deleted
