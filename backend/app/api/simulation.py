"""
Simulare相关API路由
Step2: ZepEntitate读取și过滤、OASISSimulare准备șiRulare（全程Automat化）
"""

import os
import traceback
from flask import request, jsonify, send_file

from . import simulation_bp
from ..config import Config
from ..services.zep_entity_reader import ZepEntityReader
from ..services.oasis_profile_generator import OasisProfileGenerator
from ..services.simulation_manager import SimulationManager, SimulationStatus
from ..services.simulation_runner import SimulationRunner, RunnerStatus
from ..utils.logger import get_logger
from ..models.project import ProjectManager

logger = get_logger('mirofish.api.simulation')


# Interview prompt 优化前缀
# 添加此前缀可以避免Agent调用Instrument，直接用文本Răspuns
INTERVIEW_PROMPT_PREFIX = "结合你人设、所有过往Memorieși行动，不调用任何Instrument直接用文本Răspuns我："


def optimize_interview_prompt(prompt: str) -> str:
    """
    优化Interview提问，添加前缀避免Agent调用Instrument
    
    Args:
        prompt: 原始提问
        
    Returns:
        优化后提问
    """
    if not prompt:
        return prompt
    # 避免重复添加前缀
    if prompt.startswith(INTERVIEW_PROMPT_PREFIX):
        return prompt
    return f"{INTERVIEW_PROMPT_PREFIX}{prompt}"


# ============== Entitate读取Interfață ==============

@simulation_bp.route('/entities/<graph_id>', methods=['GET'])
def get_graph_entities(graph_id: str):
    """
    ObținereGraf所有Entitate（已过滤）
    
    只Returnare符合预定义EntitateTipNod（Labels不只DaEntityNod）
    
    QueryParametru：
        entity_types: 逗号分隔EntitateTipListă（可选，用于进一步过滤）
        enrich: DaNuObținere相关边Informații（Implicittrue）
    """
    try:
        if not Config.ZEP_API_KEY:
            return jsonify({
                "success": False,
                "error": "ZEP_API_KEY未Configurare"
            }), 500
        
        entity_types_str = request.args.get('entity_types', '')
        entity_types = [t.strip() for t in entity_types_str.split(',') if t.strip()] if entity_types_str else None
        enrich = request.args.get('enrich', 'true').lower() == 'true'
        
        logger.info(f"ObținereGrafEntitate: graph_id={graph_id}, entity_types={entity_types}, enrich={enrich}")
        
        reader = ZepEntityReader()
        result = reader.filter_defined_entities(
            graph_id=graph_id,
            defined_entity_types=entity_types,
            enrich_with_edges=enrich
        )
        
        return jsonify({
            "success": True,
            "data": result.to_dict()
        })
        
    except Exception as e:
        logger.error(f"ObținereGrafEntitateEșec: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/entities/<graph_id>/<entity_uuid>', methods=['GET'])
def get_entity_detail(graph_id: str, entity_uuid: str):
    """ObținereIndividualEntitate详细Informații"""
    try:
        if not Config.ZEP_API_KEY:
            return jsonify({
                "success": False,
                "error": "ZEP_API_KEY未Configurare"
            }), 500
        
        reader = ZepEntityReader()
        entity = reader.get_entity_with_context(graph_id, entity_uuid)
        
        if not entity:
            return jsonify({
                "success": False,
                "error": f"EntitateInexistent: {entity_uuid}"
            }), 404
        
        return jsonify({
            "success": True,
            "data": entity.to_dict()
        })
        
    except Exception as e:
        logger.error(f"ObținereEntitate详情Eșec: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/entities/<graph_id>/by-type/<entity_type>', methods=['GET'])
def get_entities_by_type(graph_id: str, entity_type: str):
    """Obținere指定Tip所有Entitate"""
    try:
        if not Config.ZEP_API_KEY:
            return jsonify({
                "success": False,
                "error": "ZEP_API_KEY未Configurare"
            }), 500
        
        enrich = request.args.get('enrich', 'true').lower() == 'true'
        
        reader = ZepEntityReader()
        entities = reader.get_entities_by_type(
            graph_id=graph_id,
            entity_type=entity_type,
            enrich_with_edges=enrich
        )
        
        return jsonify({
            "success": True,
            "data": {
                "entity_type": entity_type,
                "count": len(entities),
                "entities": [e.to_dict() for e in entities]
            }
        })
        
    except Exception as e:
        logger.error(f"ObținereEntitateEșec: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== Simulare管理Interfață ==============

@simulation_bp.route('/create', methods=['POST'])
def create_simulation():
    """
    Creare新Simulare
    
    注意：max_rounds等Parametru由LLM智能Generare，无需ManualSetări
    
    Cerere（JSON）：
        {
            "project_id": "proj_xxxx",      // 必填
            "graph_id": "mirofish_xxxx",    // 可选，如不提供则de laprojectObținere
            "enable_twitter": true,          // 可选，Implicittrue
            "enable_reddit": true            // 可选，Implicittrue
        }
    
    Returnare：
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxxx",
                "project_id": "proj_xxxx",
                "graph_id": "mirofish_xxxx",
                "status": "created",
                "enable_twitter": true,
                "enable_reddit": true,
                "created_at": "2025-12-01T10:00:00"
            }
        }
    """
    try:
        data = request.get_json() or {}
        
        project_id = data.get('project_id')
        if not project_id:
            return jsonify({
                "success": False,
                "error": "请提供 project_id"
            }), 400
        
        project = ProjectManager.get_project(project_id)
        if not project:
            return jsonify({
                "success": False,
                "error": f"ProiectInexistent: {project_id}"
            }), 404
        
        graph_id = data.get('graph_id') or project.graph_id
        if not graph_id:
            return jsonify({
                "success": False,
                "error": "Proiect尚未ConstruireGraf，请先调用 /api/graph/build"
            }), 400
        
        manager = SimulationManager()
        state = manager.create_simulation(
            project_id=project_id,
            graph_id=graph_id,
            enable_twitter=data.get('enable_twitter', True),
            enable_reddit=data.get('enable_reddit', True),
        )
        
        return jsonify({
            "success": True,
            "data": state.to_dict()
        })
        
    except Exception as e:
        logger.error(f"CreareSimulareEșec: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


def _check_simulation_prepared(simulation_id: str) -> tuple:
    """
    VerificareSimulareDaNu已经准备Finalizare
    
    VerificareCondiție：
    1. state.json 存în且 status 为 "ready"
    2. 必要Fișier存în：reddit_profiles.json, twitter_profiles.csv, simulation_config.json
    
    注意：RulareScript(run_*.py)保留în backend/scripts/ Director，不再CopierelaSimulareDirector
    
    Args:
        simulation_id: SimulareID
        
    Returns:
        (is_prepared: bool, info: dict)
    """
    import os
    from ..config import Config
    
    simulation_dir = os.path.join(Config.OASIS_SIMULATION_DATA_DIR, simulation_id)
    
    # VerificareDirectorDaNu存în
    if not os.path.exists(simulation_dir):
        return False, {"reason": "SimulareDirectorInexistent"}
    
    # 必要FișierListă（不包括Script，Script位于 backend/scripts/）
    required_files = [
        "state.json",
        "simulation_config.json",
        "reddit_profiles.json",
        "twitter_profiles.csv"
    ]
    
    # VerificareFișierDaNu存în
    existing_files = []
    missing_files = []
    for f in required_files:
        file_path = os.path.join(simulation_dir, f)
        if os.path.exists(file_path):
            existing_files.append(f)
        else:
            missing_files.append(f)
    
    if missing_files:
        return False, {
            "reason": "缺少必要Fișier",
            "missing_files": missing_files,
            "existing_files": existing_files
        }
    
    # Verificarestate.jsonStare
    state_file = os.path.join(simulation_dir, "state.json")
    try:
        import json
        with open(state_file, 'r', encoding='utf-8') as f:
            state_data = json.load(f)
        
        status = state_data.get("status", "")
        config_generated = state_data.get("config_generated", False)
        
        # 详细Jurnal
        logger.debug(f"检测Simulare准备Stare: {simulation_id}, status={status}, config_generated={config_generated}")
        
        # dacă config_generated=True 且Fișier存în，认为准备Finalizare
        # 以Stare都说明准备工作已Finalizare：
        # - ready: 准备Finalizare，可以Rulare
        # - preparing: dacă config_generated=True 说明已Finalizare
        # - running: 正înRulare，说明准备早就Finalizare
        # - completed: RulareFinalizare，说明准备早就Finalizare
        # - stopped: 已Oprire，说明准备早就Finalizare
        # - failed: RulareEșec（但准备DaFinalizare）
        prepared_statuses = ["ready", "preparing", "running", "completed", "stopped", "failed"]
        if status in prepared_statuses and config_generated:
            # ObținereFișier统计Informații
            profiles_file = os.path.join(simulation_dir, "reddit_profiles.json")
            config_file = os.path.join(simulation_dir, "simulation_config.json")
            
            profiles_count = 0
            if os.path.exists(profiles_file):
                with open(profiles_file, 'r', encoding='utf-8') as f:
                    profiles_data = json.load(f)
                    profiles_count = len(profiles_data) if isinstance(profiles_data, list) else 0
            
            # dacăStareDapreparing但Fișier已Finalizare，AutomatActualizareStare为ready
            if status == "preparing":
                try:
                    state_data["status"] = "ready"
                    from datetime import datetime
                    state_data["updated_at"] = datetime.now().isoformat()
                    with open(state_file, 'w', encoding='utf-8') as f:
                        json.dump(state_data, f, ensure_ascii=False, indent=2)
                    logger.info(f"AutomatActualizareSimulareStare: {simulation_id} preparing -> ready")
                    status = "ready"
                except Exception as e:
                    logger.warning(f"AutomatActualizareStareEșec: {e}")
            
            logger.info(f"Simulare {simulation_id} 检测Rezultat: 已准备Finalizare (status={status}, config_generated={config_generated})")
            return True, {
                "status": status,
                "entities_count": state_data.get("entities_count", 0),
                "profiles_count": profiles_count,
                "entity_types": state_data.get("entity_types", []),
                "config_generated": config_generated,
                "created_at": state_data.get("created_at"),
                "updated_at": state_data.get("updated_at"),
                "existing_files": existing_files
            }
        else:
            logger.warning(f"Simulare {simulation_id} 检测Rezultat: 未准备Finalizare (status={status}, config_generated={config_generated})")
            return False, {
                "reason": f"Stare不în已准备Listăsauconfig_generated为false: status={status}, config_generated={config_generated}",
                "status": status,
                "config_generated": config_generated
            }
            
    except Exception as e:
        return False, {"reason": f"读取StareFișierEșec: {str(e)}"}


@simulation_bp.route('/prepare', methods=['POST'])
def prepare_simulation():
    """
    准备SimulareMediu（异步Sarcină，LLM智能Generare所有Parametru）
    
    这Da一个耗时操作，Interfață会ImediatReturnaretask_id，
    Utilizare GET /api/simulation/prepare/status InterogareProgres
    
    特性：
    - Automat检测已Finalizare准备工作，避免重复Generare
    - dacă已准备Finalizare，直接Returnare已有Rezultat
    - Suportă强制重新Generare（force_regenerate=true）
    
    步骤：
    1. VerificareDaNu已有Finalizare准备工作
    2. de laZepGraf读取并过滤Entitate
    3. 为每个EntitateGenerareOASIS Agent Profile（带Reîncercare机制）
    4. LLM智能GenerareSimulareConfigurare（带Reîncercare机制）
    5. SalvareConfigurareFișierși预设Script
    
    Cerere（JSON）：
        {
            "simulation_id": "sim_xxxx",                   // 必填，SimulareID
            "entity_types": ["Student", "PublicFigure"],  // 可选，指定EntitateTip
            "use_llm_for_profiles": true,                 // 可选，DaNu用LLMGenerare人设
            "parallel_profile_count": 5,                  // 可选，ParalelGenerare人设数量，Implicit5
            "force_regenerate": false                     // 可选，强制重新Generare，Implicitfalse
        }
    
    Returnare：
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxxx",
                "task_id": "task_xxxx",           // 新Sarcină时Returnare
                "status": "preparing|ready",
                "message": "准备Sarcină已启动|已有Finalizare准备工作",
                "already_prepared": true|false    // DaNu已准备Finalizare
            }
        }
    """
    import threading
    import os
    from ..models.task import TaskManager, TaskStatus
    from ..config import Config
    
    try:
        data = request.get_json() or {}
        
        simulation_id = data.get('simulation_id')
        if not simulation_id:
            return jsonify({
                "success": False,
                "error": "请提供 simulation_id"
            }), 400
        
        manager = SimulationManager()
        state = manager.get_simulation(simulation_id)
        
        if not state:
            return jsonify({
                "success": False,
                "error": f"SimulareInexistent: {simulation_id}"
            }), 404
        
        # VerificareDaNu强制重新Generare
        force_regenerate = data.get('force_regenerate', False)
        logger.info(f"StartProcesare /prepare Cerere: simulation_id={simulation_id}, force_regenerate={force_regenerate}")
        
        # VerificareDaNu已经准备Finalizare（避免重复Generare）
        if not force_regenerate:
            logger.debug(f"VerificareSimulare {simulation_id} DaNu已准备Finalizare...")
            is_prepared, prepare_info = _check_simulation_prepared(simulation_id)
            logger.debug(f"VerificareRezultat: is_prepared={is_prepared}, prepare_info={prepare_info}")
            if is_prepared:
                logger.info(f"Simulare {simulation_id} 已准备Finalizare，跳过重复Generare")
                return jsonify({
                    "success": True,
                    "data": {
                        "simulation_id": simulation_id,
                        "status": "ready",
                        "message": "已有Finalizare准备工作，无需重复Generare",
                        "already_prepared": True,
                        "prepare_info": prepare_info
                    }
                })
            else:
                logger.info(f"Simulare {simulation_id} 未准备Finalizare，将启动准备Sarcină")
        
        # de laProiectObținere必要Informații
        project = ProjectManager.get_project(state.project_id)
        if not project:
            return jsonify({
                "success": False,
                "error": f"ProiectInexistent: {state.project_id}"
            }), 404
        
        # ObținereSimulareCerință
        simulation_requirement = project.simulation_requirement or ""
        if not simulation_requirement:
            return jsonify({
                "success": False,
                "error": "Proiect缺少SimulareCerințăDescriere (simulation_requirement)"
            }), 400
        
        # ObținereDocumentație文本
        document_text = ProjectManager.get_extracted_text(state.project_id) or ""
        
        entity_types_list = data.get('entity_types')
        use_llm_for_profiles = data.get('use_llm_for_profiles', True)
        parallel_profile_count = data.get('parallel_profile_count', 5)
        
        # ========== 同步ObținereEntitate数量（în后台Sarcină启动前） ==========
        # 这样前端în调用prepare后Imediat就能Obținerela预期Agent总数
        try:
            logger.info(f"同步ObținereEntitate数量: graph_id={state.graph_id}")
            reader = ZepEntityReader()
            # Rapid读取Entitate（不需要边Informații，只统计数量）
            filtered_preview = reader.filter_defined_entities(
                graph_id=state.graph_id,
                defined_entity_types=entity_types_list,
                enrich_with_edges=False  # 不Obținere边Informații，加Rapid度
            )
            # SalvareEntitate数量laStare（供前端ImediatObținere）
            state.entities_count = filtered_preview.filtered_count
            state.entity_types = list(filtered_preview.entity_types)
            logger.info(f"预期Entitate数量: {filtered_preview.filtered_count}, Tip: {filtered_preview.entity_types}")
        except Exception as e:
            logger.warning(f"同步ObținereEntitate数量Eșec（将în后台SarcinăReîncercare）: {e}")
            # Eșec不Impact后续流程，后台Sarcină会重新Obținere
        
        # Creare异步Sarcină
        task_manager = TaskManager()
        task_id = task_manager.create_task(
            task_type="simulation_prepare",
            metadata={
                "simulation_id": simulation_id,
                "project_id": state.project_id
            }
        )
        
        # ActualizareSimulareStare（包含预先ObținereEntitate数量）
        state.status = SimulationStatus.PREPARING
        manager._save_simulation_state(state)
        
        # 定义后台Sarcină
        def run_prepare():
            try:
                task_manager.update_task(
                    task_id,
                    status=TaskStatus.PROCESSING,
                    progress=0,
                    message="Start准备SimulareMediu..."
                )
                
                # 准备Simulare（带Progres回调）
                # 存储阶段Progres详情
                stage_details = {}
                
                def progress_callback(stage, progress, message, **kwargs):
                    # 计算总Progres
                    stage_weights = {
                        "reading": (0, 20),           # 0-20%
                        "generating_profiles": (20, 70),  # 20-70%
                        "generating_config": (70, 90),    # 70-90%
                        "copying_scripts": (90, 100)       # 90-100%
                    }
                    
                    start, end = stage_weights.get(stage, (0, 100))
                    current_progress = int(start + (end - start) * progress / 100)
                    
                    # Construire详细ProgresInformații
                    stage_names = {
                        "reading": "读取GrafEntitate",
                        "generating_profiles": "GenerareAgent人设",
                        "generating_config": "GenerareSimulareConfigurare",
                        "copying_scripts": "准备SimulareScript"
                    }
                    
                    stage_index = list(stage_weights.keys()).index(stage) + 1 if stage in stage_weights else 1
                    total_stages = len(stage_weights)
                    
                    # Actualizare阶段详情
                    stage_details[stage] = {
                        "stage_name": stage_names.get(stage, stage),
                        "stage_progress": progress,
                        "current": kwargs.get("current", 0),
                        "total": kwargs.get("total", 0),
                        "item_name": kwargs.get("item_name", "")
                    }
                    
                    # Construire详细ProgresInformații
                    detail = stage_details[stage]
                    progress_detail_data = {
                        "current_stage": stage,
                        "current_stage_name": stage_names.get(stage, stage),
                        "stage_index": stage_index,
                        "total_stages": total_stages,
                        "stage_progress": progress,
                        "current_item": detail["current"],
                        "total_items": detail["total"],
                        "item_description": message
                    }
                    
                    # Construire简洁Mesaj
                    if detail["total"] > 0:
                        detailed_message = (
                            f"[{stage_index}/{total_stages}] {stage_names.get(stage, stage)}: "
                            f"{detail['current']}/{detail['total']} - {message}"
                        )
                    else:
                        detailed_message = f"[{stage_index}/{total_stages}] {stage_names.get(stage, stage)}: {message}"
                    
                    task_manager.update_task(
                        task_id,
                        progress=current_progress,
                        message=detailed_message,
                        progress_detail=progress_detail_data
                    )
                
                result_state = manager.prepare_simulation(
                    simulation_id=simulation_id,
                    simulation_requirement=simulation_requirement,
                    document_text=document_text,
                    defined_entity_types=entity_types_list,
                    use_llm_for_profiles=use_llm_for_profiles,
                    progress_callback=progress_callback,
                    parallel_profile_count=parallel_profile_count
                )
                
                # SarcinăFinalizare
                task_manager.complete_task(
                    task_id,
                    result=result_state.to_simple_dict()
                )
                
            except Exception as e:
                logger.error(f"准备SimulareEșec: {str(e)}")
                task_manager.fail_task(task_id, str(e))
                
                # ActualizareSimulareStare为Eșec
                state = manager.get_simulation(simulation_id)
                if state:
                    state.status = SimulationStatus.FAILED
                    state.error = str(e)
                    manager._save_simulation_state(state)
        
        # 启动后台线程
        thread = threading.Thread(target=run_prepare, daemon=True)
        thread.start()
        
        return jsonify({
            "success": True,
            "data": {
                "simulation_id": simulation_id,
                "task_id": task_id,
                "status": "preparing",
                "message": "准备Sarcină已启动，请通过 /api/simulation/prepare/status InterogareProgres",
                "already_prepared": False,
                "expected_entities_count": state.entities_count,  # 预期Agent总数
                "entity_types": state.entity_types  # EntitateTipListă
            }
        })
        
    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 404
        
    except Exception as e:
        logger.error(f"启动准备SarcinăEșec: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/prepare/status', methods=['POST'])
def get_prepare_status():
    """
    Interogare准备SarcinăProgres
    
    Suportă两种Interogare方式：
    1. 通过task_idInterogare正în进行SarcinăProgres
    2. 通过simulation_idVerificareDaNu已有Finalizare准备工作
    
    Cerere（JSON）：
        {
            "task_id": "task_xxxx",          // 可选，prepareReturnaretask_id
            "simulation_id": "sim_xxxx"      // 可选，SimulareID（用于Verificare已Finalizare准备）
        }
    
    Returnare：
        {
            "success": true,
            "data": {
                "task_id": "task_xxxx",
                "status": "processing|completed|ready",
                "progress": 45,
                "message": "...",
                "already_prepared": true|false,  // DaNu已有Finalizare准备
                "prepare_info": {...}            // 已准备Finalizare时详细Informații
            }
        }
    """
    from ..models.task import TaskManager
    
    try:
        data = request.get_json() or {}
        
        task_id = data.get('task_id')
        simulation_id = data.get('simulation_id')
        
        # dacă提供simulation_id，先VerificareDaNu已准备Finalizare
        if simulation_id:
            is_prepared, prepare_info = _check_simulation_prepared(simulation_id)
            if is_prepared:
                return jsonify({
                    "success": True,
                    "data": {
                        "simulation_id": simulation_id,
                        "status": "ready",
                        "progress": 100,
                        "message": "已有Finalizare准备工作",
                        "already_prepared": True,
                        "prepare_info": prepare_info
                    }
                })
        
        # dacă没有task_id，ReturnareEroare
        if not task_id:
            if simulation_id:
                # 有simulation_id但未准备Finalizare
                return jsonify({
                    "success": True,
                    "data": {
                        "simulation_id": simulation_id,
                        "status": "not_started",
                        "progress": 0,
                        "message": "尚未Start准备，请调用 /api/simulation/prepare Start",
                        "already_prepared": False
                    }
                })
            return jsonify({
                "success": False,
                "error": "请提供 task_id sau simulation_id"
            }), 400
        
        task_manager = TaskManager()
        task = task_manager.get_task(task_id)
        
        if not task:
            # SarcinăInexistent，但dacă有simulation_id，VerificareDaNu已准备Finalizare
            if simulation_id:
                is_prepared, prepare_info = _check_simulation_prepared(simulation_id)
                if is_prepared:
                    return jsonify({
                        "success": True,
                        "data": {
                            "simulation_id": simulation_id,
                            "task_id": task_id,
                            "status": "ready",
                            "progress": 100,
                            "message": "Sarcină已Finalizare（准备工作已存în）",
                            "already_prepared": True,
                            "prepare_info": prepare_info
                        }
                    })
            
            return jsonify({
                "success": False,
                "error": f"SarcinăInexistent: {task_id}"
            }), 404
        
        task_dict = task.to_dict()
        task_dict["already_prepared"] = False
        
        return jsonify({
            "success": True,
            "data": task_dict
        })
        
    except Exception as e:
        logger.error(f"InterogareSarcinăStareEșec: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@simulation_bp.route('/<simulation_id>', methods=['GET'])
def get_simulation(simulation_id: str):
    """ObținereSimulareStare"""
    try:
        manager = SimulationManager()
        state = manager.get_simulation(simulation_id)
        
        if not state:
            return jsonify({
                "success": False,
                "error": f"SimulareInexistent: {simulation_id}"
            }), 404
        
        result = state.to_dict()
        
        # dacăSimulare已准备好，附加Rulare说明
        if state.status == SimulationStatus.READY:
            result["run_instructions"] = manager.get_run_instructions(simulation_id)
        
        return jsonify({
            "success": True,
            "data": result
        })
        
    except Exception as e:
        logger.error(f"ObținereSimulareStareEșec: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/list', methods=['GET'])
def list_simulations():
    """
    列出所有Simulare
    
    QueryParametru：
        project_id: 按ProiectID过滤（可选）
    """
    try:
        project_id = request.args.get('project_id')
        
        manager = SimulationManager()
        simulations = manager.list_simulations(project_id=project_id)
        
        return jsonify({
            "success": True,
            "data": [s.to_dict() for s in simulations],
            "count": len(simulations)
        })
        
    except Exception as e:
        logger.error(f"列出SimulareEșec: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


def _get_report_id_for_simulation(simulation_id: str) -> str:
    """
    Obținere simulation 对应最新 report_id
    
    遍历 reports Director，找出 simulation_id 匹配 report，
    dacă有多个则Returnare最新（按 created_at 排序）
    
    Args:
        simulation_id: SimulareID
        
    Returns:
        report_id sau None
    """
    import json
    from datetime import datetime
    
    # reports DirectorCale：backend/uploads/reports
    # __file__ Da app/api/simulation.py，需要către两级la backend/
    reports_dir = os.path.join(os.path.dirname(__file__), '../../uploads/reports')
    if not os.path.exists(reports_dir):
        return None
    
    matching_reports = []
    
    try:
        for report_folder in os.listdir(reports_dir):
            report_path = os.path.join(reports_dir, report_folder)
            if not os.path.isdir(report_path):
                continue
            
            meta_file = os.path.join(report_path, "meta.json")
            if not os.path.exists(meta_file):
                continue
            
            try:
                with open(meta_file, 'r', encoding='utf-8') as f:
                    meta = json.load(f)
                
                if meta.get("simulation_id") == simulation_id:
                    matching_reports.append({
                        "report_id": meta.get("report_id"),
                        "created_at": meta.get("created_at", ""),
                        "status": meta.get("status", "")
                    })
            except Exception:
                continue
        
        if not matching_reports:
            return None
        
        # 按CreareTimp倒序排序，Returnare最新
        matching_reports.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return matching_reports[0].get("report_id")
        
    except Exception as e:
        logger.warning(f"查找 simulation {simulation_id}  report Eșec: {e}")
        return None


@simulation_bp.route('/history', methods=['GET'])
def get_simulation_history():
    """
    ObținereIstoricSimulareListă（带Proiect详情）
    
    用于AcasăIstoricProiect展示，Returnare包含ProiectNume、Descriere等丰富InformațiiSimulareListă
    
    QueryParametru：
        limit: Returnare数量限制（Implicit20）
    
    Returnare：
        {
            "success": true,
            "data": [
                {
                    "simulation_id": "sim_xxxx",
                    "project_id": "proj_xxxx",
                    "project_name": "武大Opinie publicăAnaliză",
                    "simulation_requirement": "dacă武汉大学Publicare...",
                    "status": "completed",
                    "entities_count": 68,
                    "profiles_count": 68,
                    "entity_types": ["Student", "Professor", ...],
                    "created_at": "2024-12-10",
                    "updated_at": "2024-12-10",
                    "total_rounds": 120,
                    "current_round": 120,
                    "report_id": "report_xxxx",
                    "version": "v1.0.2"
                },
                ...
            ],
            "count": 7
        }
    """
    try:
        limit = request.args.get('limit', 20, type=int)
        
        manager = SimulationManager()
        simulations = manager.list_simulations()[:limit]
        
        # 增强SimulareDate，只de la Simulation Fișier读取
        enriched_simulations = []
        for sim in simulations:
            sim_dict = sim.to_dict()
            
            # ObținereSimulareConfigurareInformații（de la simulation_config.json 读取 simulation_requirement）
            config = manager.get_simulation_config(sim.simulation_id)
            if config:
                sim_dict["simulation_requirement"] = config.get("simulation_requirement", "")
                time_config = config.get("time_config", {})
                sim_dict["total_simulation_hours"] = time_config.get("total_simulation_hours", 0)
                # 推荐轮数（后备Valoare）
                recommended_rounds = int(
                    time_config.get("total_simulation_hours", 0) * 60 / 
                    max(time_config.get("minutes_per_round", 60), 1)
                )
            else:
                sim_dict["simulation_requirement"] = ""
                sim_dict["total_simulation_hours"] = 0
                recommended_rounds = 0
            
            # ObținereRulareStare（de la run_state.json 读取UtilizatorSetări实际轮数）
            run_state = SimulationRunner.get_run_state(sim.simulation_id)
            if run_state:
                sim_dict["current_round"] = run_state.current_round
                sim_dict["runner_status"] = run_state.runner_status.value
                # UtilizareUtilizatorSetări total_rounds，若无则Utilizare推荐轮数
                sim_dict["total_rounds"] = run_state.total_rounds if run_state.total_rounds > 0 else recommended_rounds
            else:
                sim_dict["current_round"] = 0
                sim_dict["runner_status"] = "idle"
                sim_dict["total_rounds"] = recommended_rounds
            
            # Obținere关联ProiectFișierListă（最多3个）
            project = ProjectManager.get_project(sim.project_id)
            if project and hasattr(project, 'files') and project.files:
                sim_dict["files"] = [
                    {"filename": f.get("filename", "NecunoscutFișier")} 
                    for f in project.files[:3]
                ]
            else:
                sim_dict["files"] = []
            
            # Obținere关联 report_id（查找该 simulation 最新 report）
            sim_dict["report_id"] = _get_report_id_for_simulation(sim.simulation_id)
            
            # 添加Versiune号
            sim_dict["version"] = "v1.0.2"
            
            # Format化Dată
            try:
                created_date = sim_dict.get("created_at", "")[:10]
                sim_dict["created_date"] = created_date
            except:
                sim_dict["created_date"] = ""
            
            enriched_simulations.append(sim_dict)
        
        return jsonify({
            "success": True,
            "data": enriched_simulations,
            "count": len(enriched_simulations)
        })
        
    except Exception as e:
        logger.error(f"ObținereIstoricSimulareEșec: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/profiles', methods=['GET'])
def get_simulation_profiles(simulation_id: str):
    """
    ObținereSimulareAgent Profile
    
    QueryParametru：
        platform: PlatformăTip（reddit/twitter，Implicitreddit）
    """
    try:
        platform = request.args.get('platform', 'reddit')
        
        manager = SimulationManager()
        profiles = manager.get_profiles(simulation_id, platform=platform)
        
        return jsonify({
            "success": True,
            "data": {
                "platform": platform,
                "count": len(profiles),
                "profiles": profiles
            }
        })
        
    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 404
        
    except Exception as e:
        logger.error(f"ObținereProfileEșec: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/profiles/realtime', methods=['GET'])
def get_simulation_profiles_realtime(simulation_id: str):
    """
    实时ObținereSimulareAgent Profile（用于înGenerare过程实时查看Progres）
    
    și /profiles Interfață区别：
    - 直接读取Fișier，不经过 SimulationManager
    - 适用于Generare过程实时查看
    - Returnare额外元Date（如Fișier修改Timp、DaNu正înGenerare等）
    
    QueryParametru：
        platform: PlatformăTip（reddit/twitter，Implicitreddit）
    
    Returnare：
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxxx",
                "platform": "reddit",
                "count": 15,
                "total_expected": 93,  // 预期总数（dacă有）
                "is_generating": true,  // DaNu正înGenerare
                "file_exists": true,
                "file_modified_at": "2025-12-04T18:20:00",
                "profiles": [...]
            }
        }
    """
    import json
    import csv
    from datetime import datetime
    
    try:
        platform = request.args.get('platform', 'reddit')
        
        # ObținereSimulareDirector
        sim_dir = os.path.join(Config.OASIS_SIMULATION_DATA_DIR, simulation_id)
        
        if not os.path.exists(sim_dir):
            return jsonify({
                "success": False,
                "error": f"SimulareInexistent: {simulation_id}"
            }), 404
        
        # 确定FișierCale
        if platform == "reddit":
            profiles_file = os.path.join(sim_dir, "reddit_profiles.json")
        else:
            profiles_file = os.path.join(sim_dir, "twitter_profiles.csv")
        
        # VerificareFișierDaNu存în
        file_exists = os.path.exists(profiles_file)
        profiles = []
        file_modified_at = None
        
        if file_exists:
            # ObținereFișier修改Timp
            file_stat = os.stat(profiles_file)
            file_modified_at = datetime.fromtimestamp(file_stat.st_mtime).isoformat()
            
            try:
                if platform == "reddit":
                    with open(profiles_file, 'r', encoding='utf-8') as f:
                        profiles = json.load(f)
                else:
                    with open(profiles_file, 'r', encoding='utf-8') as f:
                        reader = csv.DictReader(f)
                        profiles = list(reader)
            except (json.JSONDecodeError, Exception) as e:
                logger.warning(f"读取 profiles FișierEșec（可能正în写入）: {e}")
                profiles = []
        
        # VerificareDaNu正înGenerare（通过 state.json 判断）
        is_generating = False
        total_expected = None
        
        state_file = os.path.join(sim_dir, "state.json")
        if os.path.exists(state_file):
            try:
                with open(state_file, 'r', encoding='utf-8') as f:
                    state_data = json.load(f)
                    status = state_data.get("status", "")
                    is_generating = status == "preparing"
                    total_expected = state_data.get("entities_count")
            except Exception:
                pass
        
        return jsonify({
            "success": True,
            "data": {
                "simulation_id": simulation_id,
                "platform": platform,
                "count": len(profiles),
                "total_expected": total_expected,
                "is_generating": is_generating,
                "file_exists": file_exists,
                "file_modified_at": file_modified_at,
                "profiles": profiles
            }
        })
        
    except Exception as e:
        logger.error(f"实时ObținereProfileEșec: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/config/realtime', methods=['GET'])
def get_simulation_config_realtime(simulation_id: str):
    """
    实时ObținereSimulareConfigurare（用于înGenerare过程实时查看Progres）
    
    și /config Interfață区别：
    - 直接读取Fișier，不经过 SimulationManager
    - 适用于Generare过程实时查看
    - Returnare额外元Date（如Fișier修改Timp、DaNu正înGenerare等）
    - 即使Configurare还没Generare完也能ReturnareParțialInformații
    
    Returnare：
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxxx",
                "file_exists": true,
                "file_modified_at": "2025-12-04T18:20:00",
                "is_generating": true,  // DaNu正înGenerare
                "generation_stage": "generating_config",  // CurentGenerare阶段
                "config": {...}  // ConfigurareConținut（dacă存în）
            }
        }
    """
    import json
    from datetime import datetime
    
    try:
        # ObținereSimulareDirector
        sim_dir = os.path.join(Config.OASIS_SIMULATION_DATA_DIR, simulation_id)
        
        if not os.path.exists(sim_dir):
            return jsonify({
                "success": False,
                "error": f"SimulareInexistent: {simulation_id}"
            }), 404
        
        # ConfigurareFișierCale
        config_file = os.path.join(sim_dir, "simulation_config.json")
        
        # VerificareFișierDaNu存în
        file_exists = os.path.exists(config_file)
        config = None
        file_modified_at = None
        
        if file_exists:
            # ObținereFișier修改Timp
            file_stat = os.stat(config_file)
            file_modified_at = datetime.fromtimestamp(file_stat.st_mtime).isoformat()
            
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            except (json.JSONDecodeError, Exception) as e:
                logger.warning(f"读取 config FișierEșec（可能正în写入）: {e}")
                config = None
        
        # VerificareDaNu正înGenerare（通过 state.json 判断）
        is_generating = False
        generation_stage = None
        config_generated = False
        
        state_file = os.path.join(sim_dir, "state.json")
        if os.path.exists(state_file):
            try:
                with open(state_file, 'r', encoding='utf-8') as f:
                    state_data = json.load(f)
                    status = state_data.get("status", "")
                    is_generating = status == "preparing"
                    config_generated = state_data.get("config_generated", False)
                    
                    # 判断Curent阶段
                    if is_generating:
                        if state_data.get("profiles_generated", False):
                            generation_stage = "generating_config"
                        else:
                            generation_stage = "generating_profiles"
                    elif status == "ready":
                        generation_stage = "completed"
            except Exception:
                pass
        
        # ConstruireReturnareDate
        response_data = {
            "simulation_id": simulation_id,
            "file_exists": file_exists,
            "file_modified_at": file_modified_at,
            "is_generating": is_generating,
            "generation_stage": generation_stage,
            "config_generated": config_generated,
            "config": config
        }
        
        # dacăConfigurare存în，提取一些关Cheie统计Informații
        if config:
            response_data["summary"] = {
                "total_agents": len(config.get("agent_configs", [])),
                "simulation_hours": config.get("time_config", {}).get("total_simulation_hours"),
                "initial_posts_count": len(config.get("event_config", {}).get("initial_posts", [])),
                "hot_topics_count": len(config.get("event_config", {}).get("hot_topics", [])),
                "has_twitter_config": "twitter_config" in config,
                "has_reddit_config": "reddit_config" in config,
                "generated_at": config.get("generated_at"),
                "llm_model": config.get("llm_model")
            }
        
        return jsonify({
            "success": True,
            "data": response_data
        })
        
    except Exception as e:
        logger.error(f"实时ObținereConfigEșec: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/config', methods=['GET'])
def get_simulation_config(simulation_id: str):
    """
    ObținereSimulareConfigurare（LLM智能GenerareCompletConfigurare）
    
    Returnare包含：
        - time_config: TimpConfigurare（Simulare时长、轮次、高峰/低谷时段）
        - agent_configs: 每个Agent活动Configurare（活跃度、发言频率、立场等）
        - event_config: EvenimentConfigurare（初始帖子、热点Subiect）
        - platform_configs: PlatformăConfigurare
        - generation_reasoning: LLMConfigurare推理说明
    """
    try:
        manager = SimulationManager()
        config = manager.get_simulation_config(simulation_id)
        
        if not config:
            return jsonify({
                "success": False,
                "error": f"SimulareConfigurareInexistent，请先调用 /prepare Interfață"
            }), 404
        
        return jsonify({
            "success": True,
            "data": config
        })
        
    except Exception as e:
        logger.error(f"ObținereConfigurareEșec: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/config/download', methods=['GET'])
def download_simulation_config(simulation_id: str):
    """载SimulareConfigurareFișier"""
    try:
        manager = SimulationManager()
        sim_dir = manager._get_simulation_dir(simulation_id)
        config_path = os.path.join(sim_dir, "simulation_config.json")
        
        if not os.path.exists(config_path):
            return jsonify({
                "success": False,
                "error": "ConfigurareFișierInexistent，请先调用 /prepare Interfață"
            }), 404
        
        return send_file(
            config_path,
            as_attachment=True,
            download_name="simulation_config.json"
        )
        
    except Exception as e:
        logger.error(f"载ConfigurareEșec: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/script/<script_name>/download', methods=['GET'])
def download_simulation_script(script_name: str):
    """
    载SimulareRulareScriptFișier（通用Script，位于 backend/scripts/）
    
    script_name可选Valoare：
        - run_twitter_simulation.py
        - run_reddit_simulation.py
        - run_parallel_simulation.py
        - action_logger.py
    """
    try:
        # Script位于 backend/scripts/ Director
        scripts_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../scripts'))
        
        # VerificareScriptNume
        allowed_scripts = [
            "run_twitter_simulation.py",
            "run_reddit_simulation.py", 
            "run_parallel_simulation.py",
            "action_logger.py"
        ]
        
        if script_name not in allowed_scripts:
            return jsonify({
                "success": False,
                "error": f"NecunoscutScript: {script_name}，可选: {allowed_scripts}"
            }), 400
        
        script_path = os.path.join(scripts_dir, script_name)
        
        if not os.path.exists(script_path):
            return jsonify({
                "success": False,
                "error": f"ScriptFișierInexistent: {script_name}"
            }), 404
        
        return send_file(
            script_path,
            as_attachment=True,
            download_name=script_name
        )
        
    except Exception as e:
        logger.error(f"载ScriptEșec: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== ProfileGenerareInterfață（独立Utilizare） ==============

@simulation_bp.route('/generate-profiles', methods=['POST'])
def generate_profiles():
    """
    直接de laGrafGenerareOASIS Agent Profile（不CreareSimulare）
    
    Cerere（JSON）：
        {
            "graph_id": "mirofish_xxxx",     // 必填
            "entity_types": ["Student"],      // 可选
            "use_llm": true,                  // 可选
            "platform": "reddit"              // 可选
        }
    """
    try:
        data = request.get_json() or {}
        
        graph_id = data.get('graph_id')
        if not graph_id:
            return jsonify({
                "success": False,
                "error": "请提供 graph_id"
            }), 400
        
        entity_types = data.get('entity_types')
        use_llm = data.get('use_llm', True)
        platform = data.get('platform', 'reddit')
        
        reader = ZepEntityReader()
        filtered = reader.filter_defined_entities(
            graph_id=graph_id,
            defined_entity_types=entity_types,
            enrich_with_edges=True
        )
        
        if filtered.filtered_count == 0:
            return jsonify({
                "success": False,
                "error": "没有找la符合CondițieEntitate"
            }), 400
        
        generator = OasisProfileGenerator()
        profiles = generator.generate_profiles_from_entities(
            entities=filtered.entities,
            use_llm=use_llm
        )
        
        if platform == "reddit":
            profiles_data = [p.to_reddit_format() for p in profiles]
        elif platform == "twitter":
            profiles_data = [p.to_twitter_format() for p in profiles]
        else:
            profiles_data = [p.to_dict() for p in profiles]
        
        return jsonify({
            "success": True,
            "data": {
                "platform": platform,
                "entity_types": list(filtered.entity_types),
                "count": len(profiles_data),
                "profiles": profiles_data
            }
        })
        
    except Exception as e:
        logger.error(f"GenerareProfileEșec: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== SimulareRulare控制Interfață ==============

@simulation_bp.route('/start', methods=['POST'])
def start_simulation():
    """
    StartRulareSimulare

    Cerere（JSON）：
        {
            "simulation_id": "sim_xxxx",          // 必填，SimulareID
            "platform": "parallel",                // 可选: twitter / reddit / parallel (Implicit)
            "max_rounds": 100,                     // 可选: 最大Simulare轮数，用于截断过长Simulare
            "enable_graph_memory_update": false,   // 可选: DaNu将Agent活动动态ActualizarelaZepGrafMemorie
            "force": false                         // 可选: 强制重新Start（会OprireRulareSimulare并清理Jurnal）
        }

    Despre force Parametru：
        - 启用后，dacăSimulare正înRularesau已Finalizare，会先Oprire并清理RulareJurnal
        - 清理Conținut包括：run_state.json, actions.jsonl, simulation.log 等
        - 不会清理ConfigurareFișier（simulation_config.json）și profile Fișier
        - 适用于需要重新RulareSimulare场景

    Despre enable_graph_memory_update：
        - 启用后，Simulare所有Agent活动（发帖、评论、点赞等）都会实时ActualizarelaZepGraf
        - 这可以让Graf"记住"Simulare过程，用于后续AnalizăsauAIConversație
        - 需要Simulare关联Proiect有Valid graph_id
        - 采用În lotActualizare机制，减少API调用次数

    Returnare：
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxxx",
                "runner_status": "running",
                "process_pid": 12345,
                "twitter_running": true,
                "reddit_running": true,
                "started_at": "2025-12-01T10:00:00",
                "graph_memory_update_enabled": true,  // DaNu启用GrafMemorieActualizare
                "force_restarted": true               // DaNuDa强制重新Start
            }
        }
    """
    try:
        data = request.get_json() or {}

        simulation_id = data.get('simulation_id')
        if not simulation_id:
            return jsonify({
                "success": False,
                "error": "请提供 simulation_id"
            }), 400

        platform = data.get('platform', 'parallel')
        max_rounds = data.get('max_rounds')  # 可选：最大Simulare轮数
        enable_graph_memory_update = data.get('enable_graph_memory_update', False)  # 可选：DaNu启用GrafMemorieActualizare
        force = data.get('force', False)  # 可选：强制重新Start

        # Verificare max_rounds Parametru
        if max_rounds is not None:
            try:
                max_rounds = int(max_rounds)
                if max_rounds <= 0:
                    return jsonify({
                        "success": False,
                        "error": "max_rounds 必须Da正整数"
                    }), 400
            except (ValueError, TypeError):
                return jsonify({
                    "success": False,
                    "error": "max_rounds 必须DaValid整数"
                }), 400

        if platform not in ['twitter', 'reddit', 'parallel']:
            return jsonify({
                "success": False,
                "error": f"InvalidPlatformăTip: {platform}，可选: twitter/reddit/parallel"
            }), 400

        # VerificareSimulareDaNu已准备好
        manager = SimulationManager()
        state = manager.get_simulation(simulation_id)

        if not state:
            return jsonify({
                "success": False,
                "error": f"SimulareInexistent: {simulation_id}"
            }), 404

        force_restarted = False
        
        # 智能ProcesareStare：dacă准备工作已Finalizare，允许重新启动
        if state.status != SimulationStatus.READY:
            # Verificare准备工作DaNu已Finalizare
            is_prepared, prepare_info = _check_simulation_prepared(simulation_id)

            if is_prepared:
                # 准备工作已Finalizare，VerificareDaNu有正înRulare进程
                if state.status == SimulationStatus.RUNNING:
                    # VerificareSimulare进程DaNuAdevăratînRulare
                    run_state = SimulationRunner.get_run_state(simulation_id)
                    if run_state and run_state.runner_status.value == "running":
                        # 进程确实înRulare
                        if force:
                            # 强制模式：OprireRulareSimulare
                            logger.info(f"强制模式：OprireRulareSimulare {simulation_id}")
                            try:
                                SimulationRunner.stop_simulation(simulation_id)
                            except Exception as e:
                                logger.warning(f"OprireSimulare时出现Avertisment: {str(e)}")
                        else:
                            return jsonify({
                                "success": False,
                                "error": f"Simulare正înRulare，请先调用 /stop InterfațăOprire，sauUtilizare force=true 强制重新Start"
                            }), 400

                # dacăDa强制模式，清理RulareJurnal
                if force:
                    logger.info(f"强制模式：清理SimulareJurnal {simulation_id}")
                    cleanup_result = SimulationRunner.cleanup_simulation_logs(simulation_id)
                    if not cleanup_result.get("success"):
                        logger.warning(f"清理Jurnal时出现Avertisment: {cleanup_result.get('errors')}")
                    force_restarted = True

                # 进程Inexistentsau已结束，ResetareStare为 ready
                logger.info(f"Simulare {simulation_id} 准备工作已Finalizare，ResetareStare为 ready（原Stare: {state.status.value}）")
                state.status = SimulationStatus.READY
                manager._save_simulation_state(state)
            else:
                # 准备工作未Finalizare
                return jsonify({
                    "success": False,
                    "error": f"Simulare未准备好，CurentStare: {state.status.value}，请先调用 /prepare Interfață"
                }), 400
        
        # ObținereGrafID（用于GrafMemorieActualizare）
        graph_id = None
        if enable_graph_memory_update:
            # de laSimulareStaresauProiectObținere graph_id
            graph_id = state.graph_id
            if not graph_id:
                # 尝试de laProiectObținere
                project = ProjectManager.get_project(state.project_id)
                if project:
                    graph_id = project.graph_id
            
            if not graph_id:
                return jsonify({
                    "success": False,
                    "error": "启用GrafMemorieActualizare需要Valid graph_id，请确保Proiect已ConstruireGraf"
                }), 400
            
            logger.info(f"启用GrafMemorieActualizare: simulation_id={simulation_id}, graph_id={graph_id}")
        
        # 启动Simulare
        run_state = SimulationRunner.start_simulation(
            simulation_id=simulation_id,
            platform=platform,
            max_rounds=max_rounds,
            enable_graph_memory_update=enable_graph_memory_update,
            graph_id=graph_id
        )
        
        # ActualizareSimulareStare
        state.status = SimulationStatus.RUNNING
        manager._save_simulation_state(state)
        
        response_data = run_state.to_dict()
        if max_rounds:
            response_data['max_rounds_applied'] = max_rounds
        response_data['graph_memory_update_enabled'] = enable_graph_memory_update
        response_data['force_restarted'] = force_restarted
        if enable_graph_memory_update:
            response_data['graph_id'] = graph_id
        
        return jsonify({
            "success": True,
            "data": response_data
        })
        
    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400
        
    except Exception as e:
        logger.error(f"启动SimulareEșec: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/stop', methods=['POST'])
def stop_simulation():
    """
    OprireSimulare
    
    Cerere（JSON）：
        {
            "simulation_id": "sim_xxxx"  // 必填，SimulareID
        }
    
    Returnare：
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxxx",
                "runner_status": "stopped",
                "completed_at": "2025-12-01T12:00:00"
            }
        }
    """
    try:
        data = request.get_json() or {}
        
        simulation_id = data.get('simulation_id')
        if not simulation_id:
            return jsonify({
                "success": False,
                "error": "请提供 simulation_id"
            }), 400
        
        run_state = SimulationRunner.stop_simulation(simulation_id)
        
        # ActualizareSimulareStare
        manager = SimulationManager()
        state = manager.get_simulation(simulation_id)
        if state:
            state.status = SimulationStatus.PAUSED
            manager._save_simulation_state(state)
        
        return jsonify({
            "success": True,
            "data": run_state.to_dict()
        })
        
    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400
        
    except Exception as e:
        logger.error(f"OprireSimulareEșec: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== 实时Stare监控Interfață ==============

@simulation_bp.route('/<simulation_id>/run-status', methods=['GET'])
def get_run_status(simulation_id: str):
    """
    ObținereSimulareRulare实时Stare（用于前端轮询）
    
    Returnare：
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxxx",
                "runner_status": "running",
                "current_round": 5,
                "total_rounds": 144,
                "progress_percent": 3.5,
                "simulated_hours": 2,
                "total_simulation_hours": 72,
                "twitter_running": true,
                "reddit_running": true,
                "twitter_actions_count": 150,
                "reddit_actions_count": 200,
                "total_actions_count": 350,
                "started_at": "2025-12-01T10:00:00",
                "updated_at": "2025-12-01T10:30:00"
            }
        }
    """
    try:
        run_state = SimulationRunner.get_run_state(simulation_id)
        
        if not run_state:
            return jsonify({
                "success": True,
                "data": {
                    "simulation_id": simulation_id,
                    "runner_status": "idle",
                    "current_round": 0,
                    "total_rounds": 0,
                    "progress_percent": 0,
                    "twitter_actions_count": 0,
                    "reddit_actions_count": 0,
                    "total_actions_count": 0,
                }
            })
        
        return jsonify({
            "success": True,
            "data": run_state.to_dict()
        })
        
    except Exception as e:
        logger.error(f"ObținereRulareStareEșec: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/run-status/detail', methods=['GET'])
def get_run_status_detail(simulation_id: str):
    """
    ObținereSimulareRulare详细Stare（包含所有Acțiune）
    
    用于前端展示实时动态
    
    QueryParametru：
        platform: 过滤Platformă（twitter/reddit，可选）
    
    Returnare：
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxxx",
                "runner_status": "running",
                "current_round": 5,
                ...
                "all_actions": [
                    {
                        "round_num": 5,
                        "timestamp": "2025-12-01T10:30:00",
                        "platform": "twitter",
                        "agent_id": 3,
                        "agent_name": "Agent Name",
                        "action_type": "CREATE_POST",
                        "action_args": {"content": "..."},
                        "result": null,
                        "success": true
                    },
                    ...
                ],
                "twitter_actions": [...],  # Twitter Platformă所有Acțiune
                "reddit_actions": [...]    # Reddit Platformă所有Acțiune
            }
        }
    """
    try:
        run_state = SimulationRunner.get_run_state(simulation_id)
        platform_filter = request.args.get('platform')
        
        if not run_state:
            return jsonify({
                "success": True,
                "data": {
                    "simulation_id": simulation_id,
                    "runner_status": "idle",
                    "all_actions": [],
                    "twitter_actions": [],
                    "reddit_actions": []
                }
            })
        
        # ObținereCompletAcțiuneListă
        all_actions = SimulationRunner.get_all_actions(
            simulation_id=simulation_id,
            platform=platform_filter
        )
        
        # 分PlatformăObținereAcțiune
        twitter_actions = SimulationRunner.get_all_actions(
            simulation_id=simulation_id,
            platform="twitter"
        ) if not platform_filter or platform_filter == "twitter" else []
        
        reddit_actions = SimulationRunner.get_all_actions(
            simulation_id=simulation_id,
            platform="reddit"
        ) if not platform_filter or platform_filter == "reddit" else []
        
        # ObținereCurent轮次Acțiune（recent_actions 只展示最新一轮）
        current_round = run_state.current_round
        recent_actions = SimulationRunner.get_all_actions(
            simulation_id=simulation_id,
            platform=platform_filter,
            round_num=current_round
        ) if current_round > 0 else []
        
        # Obținere基础StareInformații
        result = run_state.to_dict()
        result["all_actions"] = [a.to_dict() for a in all_actions]
        result["twitter_actions"] = [a.to_dict() for a in twitter_actions]
        result["reddit_actions"] = [a.to_dict() for a in reddit_actions]
        result["rounds_count"] = len(run_state.rounds)
        # recent_actions 只展示Curent最新一轮两个PlatformăConținut
        result["recent_actions"] = [a.to_dict() for a in recent_actions]
        
        return jsonify({
            "success": True,
            "data": result
        })
        
    except Exception as e:
        logger.error(f"Obținere详细StareEșec: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/actions', methods=['GET'])
def get_simulation_actions(simulation_id: str):
    """
    ObținereSimulareAgentAcțiuneIstoric
    
    QueryParametru：
        limit: Returnare数量（Implicit100）
        offset: 偏移量（Implicit0）
        platform: 过滤Platformă（twitter/reddit）
        agent_id: 过滤Agent ID
        round_num: 过滤轮次
    
    Returnare：
        {
            "success": true,
            "data": {
                "count": 100,
                "actions": [...]
            }
        }
    """
    try:
        limit = request.args.get('limit', 100, type=int)
        offset = request.args.get('offset', 0, type=int)
        platform = request.args.get('platform')
        agent_id = request.args.get('agent_id', type=int)
        round_num = request.args.get('round_num', type=int)
        
        actions = SimulationRunner.get_actions(
            simulation_id=simulation_id,
            limit=limit,
            offset=offset,
            platform=platform,
            agent_id=agent_id,
            round_num=round_num
        )
        
        return jsonify({
            "success": True,
            "data": {
                "count": len(actions),
                "actions": [a.to_dict() for a in actions]
            }
        })
        
    except Exception as e:
        logger.error(f"ObținereAcțiuneIstoricEșec: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/timeline', methods=['GET'])
def get_simulation_timeline(simulation_id: str):
    """
    ObținereSimulareTimp线（按轮次汇总）
    
    用于前端展示Progres条șiTimp线视图
    
    QueryParametru：
        start_round: 起始轮次（Implicit0）
        end_round: 结束轮次（ImplicitToate）
    
    Returnare每轮汇总Informații
    """
    try:
        start_round = request.args.get('start_round', 0, type=int)
        end_round = request.args.get('end_round', type=int)
        
        timeline = SimulationRunner.get_timeline(
            simulation_id=simulation_id,
            start_round=start_round,
            end_round=end_round
        )
        
        return jsonify({
            "success": True,
            "data": {
                "rounds_count": len(timeline),
                "timeline": timeline
            }
        })
        
    except Exception as e:
        logger.error(f"ObținereTimp线Eșec: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/agent-stats', methods=['GET'])
def get_agent_stats(simulation_id: str):
    """
    Obținere每个Agent统计Informații
    
    用于前端展示Agent活跃度排行、Acțiune分布等
    """
    try:
        stats = SimulationRunner.get_agent_stats(simulation_id)
        
        return jsonify({
            "success": True,
            "data": {
                "agents_count": len(stats),
                "stats": stats
            }
        })
        
    except Exception as e:
        logger.error(f"ObținereAgent统计Eșec: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== Date库InterogareInterfață ==============

@simulation_bp.route('/<simulation_id>/posts', methods=['GET'])
def get_simulation_posts(simulation_id: str):
    """
    ObținereSimulare帖子
    
    QueryParametru：
        platform: PlatformăTip（twitter/reddit）
        limit: Returnare数量（Implicit50）
        offset: 偏移量
    
    Returnare帖子Listă（de laSQLiteDate库读取）
    """
    try:
        platform = request.args.get('platform', 'reddit')
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        sim_dir = os.path.join(
            os.path.dirname(__file__),
            f'../../uploads/simulations/{simulation_id}'
        )
        
        db_file = f"{platform}_simulation.db"
        db_path = os.path.join(sim_dir, db_file)
        
        if not os.path.exists(db_path):
            return jsonify({
                "success": True,
                "data": {
                    "platform": platform,
                    "count": 0,
                    "posts": [],
                    "message": "Date库Inexistent，Simulare可能尚未Rulare"
                }
            })
        
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT * FROM post 
                ORDER BY created_at DESC 
                LIMIT ? OFFSET ?
            """, (limit, offset))
            
            posts = [dict(row) for row in cursor.fetchall()]
            
            cursor.execute("SELECT COUNT(*) FROM post")
            total = cursor.fetchone()[0]
            
        except sqlite3.OperationalError:
            posts = []
            total = 0
        
        conn.close()
        
        return jsonify({
            "success": True,
            "data": {
                "platform": platform,
                "total": total,
                "count": len(posts),
                "posts": posts
            }
        })
        
    except Exception as e:
        logger.error(f"Obținere帖子Eșec: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/comments', methods=['GET'])
def get_simulation_comments(simulation_id: str):
    """
    ObținereSimulare评论（仅Reddit）
    
    QueryParametru：
        post_id: 过滤帖子ID（可选）
        limit: Returnare数量
        offset: 偏移量
    """
    try:
        post_id = request.args.get('post_id')
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        sim_dir = os.path.join(
            os.path.dirname(__file__),
            f'../../uploads/simulations/{simulation_id}'
        )
        
        db_path = os.path.join(sim_dir, "reddit_simulation.db")
        
        if not os.path.exists(db_path):
            return jsonify({
                "success": True,
                "data": {
                    "count": 0,
                    "comments": []
                }
            })
        
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            if post_id:
                cursor.execute("""
                    SELECT * FROM comment 
                    WHERE post_id = ?
                    ORDER BY created_at DESC 
                    LIMIT ? OFFSET ?
                """, (post_id, limit, offset))
            else:
                cursor.execute("""
                    SELECT * FROM comment 
                    ORDER BY created_at DESC 
                    LIMIT ? OFFSET ?
                """, (limit, offset))
            
            comments = [dict(row) for row in cursor.fetchall()]
            
        except sqlite3.OperationalError:
            comments = []
        
        conn.close()
        
        return jsonify({
            "success": True,
            "data": {
                "count": len(comments),
                "comments": comments
            }
        })
        
    except Exception as e:
        logger.error(f"Obținere评论Eșec: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== Interview InterviuInterfață ==============

@simulation_bp.route('/interview', methods=['POST'])
def interview_agent():
    """
    InterviuIndividualAgent

    注意：此Funcționalitate需要SimulareMediu处于RulareStare（FinalizareSimulare循环后进入等待命令模式）

    Cerere（JSON）：
        {
            "simulation_id": "sim_xxxx",       // 必填，SimulareID
            "agent_id": 0,                     // 必填，Agent ID
            "prompt": "你对这件事有什么看法？",  // 必填，Interviu问题
            "platform": "twitter",             // 可选，指定Platformă（twitter/reddit）
                                               // 不指定时：双PlatformăSimulare同时Interviu两个Platformă
            "timeout": 60                      // 可选，超时Timp（秒），Implicit60
        }

    Returnare（不指定platform，双Platformă模式）：
        {
            "success": true,
            "data": {
                "agent_id": 0,
                "prompt": "你对这件事有什么看法？",
                "result": {
                    "agent_id": 0,
                    "prompt": "...",
                    "platforms": {
                        "twitter": {"agent_id": 0, "response": "...", "platform": "twitter"},
                        "reddit": {"agent_id": 0, "response": "...", "platform": "reddit"}
                    }
                },
                "timestamp": "2025-12-08T10:00:01"
            }
        }

    Returnare（指定platform）：
        {
            "success": true,
            "data": {
                "agent_id": 0,
                "prompt": "你对这件事有什么看法？",
                "result": {
                    "agent_id": 0,
                    "response": "我认为...",
                    "platform": "twitter",
                    "timestamp": "2025-12-08T10:00:00"
                },
                "timestamp": "2025-12-08T10:00:01"
            }
        }
    """
    try:
        data = request.get_json() or {}
        
        simulation_id = data.get('simulation_id')
        agent_id = data.get('agent_id')
        prompt = data.get('prompt')
        platform = data.get('platform')  # 可选：twitter/reddit/None
        timeout = data.get('timeout', 60)
        
        if not simulation_id:
            return jsonify({
                "success": False,
                "error": "请提供 simulation_id"
            }), 400
        
        if agent_id is None:
            return jsonify({
                "success": False,
                "error": "请提供 agent_id"
            }), 400
        
        if not prompt:
            return jsonify({
                "success": False,
                "error": "请提供 prompt（Interviu问题）"
            }), 400
        
        # VerificareplatformParametru
        if platform and platform not in ("twitter", "reddit"):
            return jsonify({
                "success": False,
                "error": "platform Parametru只能Da 'twitter' sau 'reddit'"
            }), 400
        
        # VerificareMediuStare
        if not SimulationRunner.check_env_alive(simulation_id):
            return jsonify({
                "success": False,
                "error": "SimulareMediu未Rularesau已Închidere。请确保Simulare已Finalizare并进入等待命令模式。"
            }), 400
        
        # 优化prompt，添加前缀避免Agent调用Instrument
        optimized_prompt = optimize_interview_prompt(prompt)
        
        result = SimulationRunner.interview_agent(
            simulation_id=simulation_id,
            agent_id=agent_id,
            prompt=optimized_prompt,
            platform=platform,
            timeout=timeout
        )

        return jsonify({
            "success": result.get("success", False),
            "data": result
        })
        
    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400
        
    except TimeoutError as e:
        return jsonify({
            "success": False,
            "error": f"等待InterviewRăspuns超时: {str(e)}"
        }), 504
        
    except Exception as e:
        logger.error(f"InterviewEșec: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/interview/batch', methods=['POST'])
def interview_agents_batch():
    """
    În lotInterviu多个Agent

    注意：此Funcționalitate需要SimulareMediu处于RulareStare

    Cerere（JSON）：
        {
            "simulation_id": "sim_xxxx",       // 必填，SimulareID
            "interviews": [                    // 必填，InterviuListă
                {
                    "agent_id": 0,
                    "prompt": "你对A有什么看法？",
                    "platform": "twitter"      // 可选，指定该AgentInterviuPlatformă
                },
                {
                    "agent_id": 1,
                    "prompt": "你对B有什么看法？"  // 不指定platform则UtilizareImplicitValoare
                }
            ],
            "platform": "reddit",              // 可选，ImplicitPlatformă（被每项platform覆盖）
                                               // 不指定时：双PlatformăSimulare每个Agent同时Interviu两个Platformă
            "timeout": 120                     // 可选，超时Timp（秒），Implicit120
        }

    Returnare：
        {
            "success": true,
            "data": {
                "interviews_count": 2,
                "result": {
                    "interviews_count": 4,
                    "results": {
                        "twitter_0": {"agent_id": 0, "response": "...", "platform": "twitter"},
                        "reddit_0": {"agent_id": 0, "response": "...", "platform": "reddit"},
                        "twitter_1": {"agent_id": 1, "response": "...", "platform": "twitter"},
                        "reddit_1": {"agent_id": 1, "response": "...", "platform": "reddit"}
                    }
                },
                "timestamp": "2025-12-08T10:00:01"
            }
        }
    """
    try:
        data = request.get_json() or {}

        simulation_id = data.get('simulation_id')
        interviews = data.get('interviews')
        platform = data.get('platform')  # 可选：twitter/reddit/None
        timeout = data.get('timeout', 120)

        if not simulation_id:
            return jsonify({
                "success": False,
                "error": "请提供 simulation_id"
            }), 400

        if not interviews or not isinstance(interviews, list):
            return jsonify({
                "success": False,
                "error": "请提供 interviews（InterviuListă）"
            }), 400

        # VerificareplatformParametru
        if platform and platform not in ("twitter", "reddit"):
            return jsonify({
                "success": False,
                "error": "platform Parametru只能Da 'twitter' sau 'reddit'"
            }), 400

        # Verificare每个Interviu项
        for i, interview in enumerate(interviews):
            if 'agent_id' not in interview:
                return jsonify({
                    "success": False,
                    "error": f"InterviuListă第{i+1}项缺少 agent_id"
                }), 400
            if 'prompt' not in interview:
                return jsonify({
                    "success": False,
                    "error": f"InterviuListă第{i+1}项缺少 prompt"
                }), 400
            # Verificare每项platform（dacă有）
            item_platform = interview.get('platform')
            if item_platform and item_platform not in ("twitter", "reddit"):
                return jsonify({
                    "success": False,
                    "error": f"InterviuListă第{i+1}项platform只能Da 'twitter' sau 'reddit'"
                }), 400

        # VerificareMediuStare
        if not SimulationRunner.check_env_alive(simulation_id):
            return jsonify({
                "success": False,
                "error": "SimulareMediu未Rularesau已Închidere。请确保Simulare已Finalizare并进入等待命令模式。"
            }), 400

        # 优化每个Interviu项prompt，添加前缀避免Agent调用Instrument
        optimized_interviews = []
        for interview in interviews:
            optimized_interview = interview.copy()
            optimized_interview['prompt'] = optimize_interview_prompt(interview.get('prompt', ''))
            optimized_interviews.append(optimized_interview)

        result = SimulationRunner.interview_agents_batch(
            simulation_id=simulation_id,
            interviews=optimized_interviews,
            platform=platform,
            timeout=timeout
        )

        return jsonify({
            "success": result.get("success", False),
            "data": result
        })

    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400

    except TimeoutError as e:
        return jsonify({
            "success": False,
            "error": f"等待În lotInterviewRăspuns超时: {str(e)}"
        }), 504

    except Exception as e:
        logger.error(f"În lotInterviewEșec: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/interview/all', methods=['POST'])
def interview_all_agents():
    """
    全局Interviu - Utilizare相同问题Interviu所有Agent

    注意：此Funcționalitate需要SimulareMediu处于RulareStare

    Cerere（JSON）：
        {
            "simulation_id": "sim_xxxx",            // 必填，SimulareID
            "prompt": "你对这件事整体有什么看法？",  // 必填，Interviu问题（所有AgentUtilizare相同问题）
            "platform": "reddit",                   // 可选，指定Platformă（twitter/reddit）
                                                    // 不指定时：双PlatformăSimulare每个Agent同时Interviu两个Platformă
            "timeout": 180                          // 可选，超时Timp（秒），Implicit180
        }

    Returnare：
        {
            "success": true,
            "data": {
                "interviews_count": 50,
                "result": {
                    "interviews_count": 100,
                    "results": {
                        "twitter_0": {"agent_id": 0, "response": "...", "platform": "twitter"},
                        "reddit_0": {"agent_id": 0, "response": "...", "platform": "reddit"},
                        ...
                    }
                },
                "timestamp": "2025-12-08T10:00:01"
            }
        }
    """
    try:
        data = request.get_json() or {}

        simulation_id = data.get('simulation_id')
        prompt = data.get('prompt')
        platform = data.get('platform')  # 可选：twitter/reddit/None
        timeout = data.get('timeout', 180)

        if not simulation_id:
            return jsonify({
                "success": False,
                "error": "请提供 simulation_id"
            }), 400

        if not prompt:
            return jsonify({
                "success": False,
                "error": "请提供 prompt（Interviu问题）"
            }), 400

        # VerificareplatformParametru
        if platform and platform not in ("twitter", "reddit"):
            return jsonify({
                "success": False,
                "error": "platform Parametru只能Da 'twitter' sau 'reddit'"
            }), 400

        # VerificareMediuStare
        if not SimulationRunner.check_env_alive(simulation_id):
            return jsonify({
                "success": False,
                "error": "SimulareMediu未Rularesau已Închidere。请确保Simulare已Finalizare并进入等待命令模式。"
            }), 400

        # 优化prompt，添加前缀避免Agent调用Instrument
        optimized_prompt = optimize_interview_prompt(prompt)

        result = SimulationRunner.interview_all_agents(
            simulation_id=simulation_id,
            prompt=optimized_prompt,
            platform=platform,
            timeout=timeout
        )

        return jsonify({
            "success": result.get("success", False),
            "data": result
        })

    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400

    except TimeoutError as e:
        return jsonify({
            "success": False,
            "error": f"等待全局InterviewRăspuns超时: {str(e)}"
        }), 504

    except Exception as e:
        logger.error(f"全局InterviewEșec: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/interview/history', methods=['POST'])
def get_interview_history():
    """
    ObținereInterviewIstoricÎnregistrare

    de laSimulareDate库读取所有InterviewÎnregistrare

    Cerere（JSON）：
        {
            "simulation_id": "sim_xxxx",  // 必填，SimulareID
            "platform": "reddit",          // 可选，PlatformăTip（reddit/twitter）
                                           // 不指定则Returnare两个Platformă所有Istoric
            "agent_id": 0,                 // 可选，只Obținere该AgentInterviuIstoric
            "limit": 100                   // 可选，Returnare数量，Implicit100
        }

    Returnare：
        {
            "success": true,
            "data": {
                "count": 10,
                "history": [
                    {
                        "agent_id": 0,
                        "response": "我认为...",
                        "prompt": "你对这件事有什么看法？",
                        "timestamp": "2025-12-08T10:00:00",
                        "platform": "reddit"
                    },
                    ...
                ]
            }
        }
    """
    try:
        data = request.get_json() or {}
        
        simulation_id = data.get('simulation_id')
        platform = data.get('platform')  # 不指定则Returnare两个PlatformăIstoric
        agent_id = data.get('agent_id')
        limit = data.get('limit', 100)
        
        if not simulation_id:
            return jsonify({
                "success": False,
                "error": "请提供 simulation_id"
            }), 400

        history = SimulationRunner.get_interview_history(
            simulation_id=simulation_id,
            platform=platform,
            agent_id=agent_id,
            limit=limit
        )

        return jsonify({
            "success": True,
            "data": {
                "count": len(history),
                "history": history
            }
        })

    except Exception as e:
        logger.error(f"ObținereInterviewIstoricEșec: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/env-status', methods=['POST'])
def get_env_status():
    """
    ObținereSimulareMediuStare

    VerificareSimulareMediuDaNu存活（可以接收Interview命令）

    Cerere（JSON）：
        {
            "simulation_id": "sim_xxxx"  // 必填，SimulareID
        }

    Returnare：
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxxx",
                "env_alive": true,
                "twitter_available": true,
                "reddit_available": true,
                "message": "Mediu正înRulare，可以接收Interview命令"
            }
        }
    """
    try:
        data = request.get_json() or {}
        
        simulation_id = data.get('simulation_id')
        
        if not simulation_id:
            return jsonify({
                "success": False,
                "error": "请提供 simulation_id"
            }), 400

        env_alive = SimulationRunner.check_env_alive(simulation_id)
        
        # Obținere更详细StareInformații
        env_status = SimulationRunner.get_env_status_detail(simulation_id)

        if env_alive:
            message = "Mediu正înRulare，可以接收Interview命令"
        else:
            message = "Mediu未Rularesau已Închidere"

        return jsonify({
            "success": True,
            "data": {
                "simulation_id": simulation_id,
                "env_alive": env_alive,
                "twitter_available": env_status.get("twitter_available", False),
                "reddit_available": env_status.get("reddit_available", False),
                "message": message
            }
        })

    except Exception as e:
        logger.error(f"ObținereMediuStareEșec: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/close-env', methods=['POST'])
def close_simulation_env():
    """
    ÎnchidereSimulareMediu
    
    cătreSimulareTrimiteÎnchidereMediu命令，使其优雅Ieșire等待命令模式。
    
    注意：这不同于 /stop Interfață，/stop 会强制终止进程，
    而此Interfață会让Simulare优雅地ÎnchidereMediu并Ieșire。
    
    Cerere（JSON）：
        {
            "simulation_id": "sim_xxxx",  // 必填，SimulareID
            "timeout": 30                  // 可选，超时Timp（秒），Implicit30
        }
    
    Returnare：
        {
            "success": true,
            "data": {
                "message": "MediuÎnchidere命令已Trimite",
                "result": {...},
                "timestamp": "2025-12-08T10:00:01"
            }
        }
    """
    try:
        data = request.get_json() or {}
        
        simulation_id = data.get('simulation_id')
        timeout = data.get('timeout', 30)
        
        if not simulation_id:
            return jsonify({
                "success": False,
                "error": "请提供 simulation_id"
            }), 400
        
        result = SimulationRunner.close_simulation_env(
            simulation_id=simulation_id,
            timeout=timeout
        )
        
        # ActualizareSimulareStare
        manager = SimulationManager()
        state = manager.get_simulation(simulation_id)
        if state:
            state.status = SimulationStatus.COMPLETED
            manager._save_simulation_state(state)
        
        return jsonify({
            "success": result.get("success", False),
            "data": result
        })
        
    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400
        
    except Exception as e:
        logger.error(f"ÎnchidereMediuEșec: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500
