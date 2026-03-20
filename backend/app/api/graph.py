"""
Graf相关API路由
采用项目文机制，Serviciu端持久化Stare
"""

import os
import traceback
import threading
from flask import request, jsonify

from . import graph_bp
from ..config import Config
from ..services.ontology_generator import OntologyGenerator
from ..services.graph_builder import GraphBuilderService
from ..services.text_processor import TextProcessor
from ..utils.file_parser import FileParser
from ..utils.logger import get_logger
from ..models.task import TaskManager, TaskStatus
from ..models.project import ProjectManager, ProjectStatus

# ObținereJurnal器
logger = get_logger('mirofish.api')


def allowed_file(filename: str) -> bool:
    """VerificareFișier扩展名DaNu允许"""
    if not filename or '.' not in filename:
        return False
    ext = os.path.splitext(filename)[1].lower().lstrip('.')
    return ext in Config.ALLOWED_EXTENSIONS


# ============== 项目管理Interfață ==============

@graph_bp.route('/project/<project_id>', methods=['GET'])
def get_project(project_id: str):
    """
    Obținere项目详情
    """
    project = ProjectManager.get_project(project_id)
    
    if not project:
        return jsonify({
            "success": False,
            "error": f"项目Inexistent: {project_id}"
        }), 404
    
    return jsonify({
        "success": True,
        "data": project.to_dict()
    })


@graph_bp.route('/project/list', methods=['GET'])
def list_projects():
    """
    列出所有项目
    """
    limit = request.args.get('limit', 50, type=int)
    projects = ProjectManager.list_projects(limit=limit)
    
    return jsonify({
        "success": True,
        "data": [p.to_dict() for p in projects],
        "count": len(projects)
    })


@graph_bp.route('/project/<project_id>', methods=['DELETE'])
def delete_project(project_id: str):
    """
    Ștergere项目
    """
    success = ProjectManager.delete_project(project_id)
    
    if not success:
        return jsonify({
            "success": False,
            "error": f"项目InexistentsauȘtergereEșec: {project_id}"
        }), 404
    
    return jsonify({
        "success": True,
        "message": f"项目已Ștergere: {project_id}"
    })


@graph_bp.route('/project/<project_id>/reset', methods=['POST'])
def reset_project(project_id: str):
    """
    重置项目Stare（用于重新ConstruireGraf）
    """
    project = ProjectManager.get_project(project_id)
    
    if not project:
        return jsonify({
            "success": False,
            "error": f"项目Inexistent: {project_id}"
        }), 404
    
    # 重置laOntologie已GenerareStare
    if project.ontology:
        project.status = ProjectStatus.ONTOLOGY_GENERATED
    else:
        project.status = ProjectStatus.CREATED
    
    project.graph_id = None
    project.graph_build_task_id = None
    project.error = None
    ProjectManager.save_project(project)
    
    return jsonify({
        "success": True,
        "message": f"项目已重置: {project_id}",
        "data": project.to_dict()
    })


# ============== Interfață1：传Fișier并GenerareOntologie ==============

@graph_bp.route('/ontology/generate', methods=['POST'])
def generate_ontology():
    """
    Interfață1：传Fișier，AnalizăGenerareOntologie定义
    
    Cerere方式：multipart/form-data
    
    Parametru：
        files: 传Fișier（PDF/MD/TXT），可多个
        simulation_requirement: SimulareCerințăDescriere（必填）
        project_name: 项目Nume（可选）
        additional_context: 额外说明（可选）
        
    Returnare：
        {
            "success": true,
            "data": {
                "project_id": "proj_xxxx",
                "ontology": {
                    "entity_types": [...],
                    "edge_types": [...],
                    "analysis_summary": "..."
                },
                "files": [...],
                "total_text_length": 12345
            }
        }
    """
    try:
        logger.info("=== StartGenerareOntologie定义 ===")
        
        # ObținereParametru
        simulation_requirement = request.form.get('simulation_requirement', '')
        project_name = request.form.get('project_name', 'Unnamed Project')
        additional_context = request.form.get('additional_context', '')
        
        logger.debug(f"项目Nume: {project_name}")
        logger.debug(f"SimulareCerință: {simulation_requirement[:100]}...")
        
        if not simulation_requirement:
            return jsonify({
                "success": False,
                "error": "请提供SimulareCerințăDescriere (simulation_requirement)"
            }), 400
        
        # Obținere传Fișier
        uploaded_files = request.files.getlist('files')
        if not uploaded_files or all(not f.filename for f in uploaded_files):
            return jsonify({
                "success": False,
                "error": "请至少传一个文档Fișier"
            }), 400
        
        # Creare项目
        project = ProjectManager.create_project(name=project_name)
        project.simulation_requirement = simulation_requirement
        logger.info(f"Creare项目: {project.project_id}")
        
        # SalvareFișier并提取文本
        document_texts = []
        all_text = ""
        
        for file in uploaded_files:
            if file and file.filename and allowed_file(file.filename):
                # SalvareFișierla项目Director
                file_info = ProjectManager.save_file_to_project(
                    project.project_id, 
                    file, 
                    file.filename
                )
                project.files.append({
                    "filename": file_info["original_filename"],
                    "size": file_info["size"]
                })
                
                # 提取文本
                text = FileParser.extract_text(file_info["path"])
                text = TextProcessor.preprocess_text(text)
                document_texts.append(text)
                all_text += f"\n\n=== {file_info['original_filename']} ===\n{text}"
        
        if not document_texts:
            ProjectManager.delete_project(project.project_id)
            return jsonify({
                "success": False,
                "error": "没有SuccesProcesare任何文档，请VerificareFișier格式"
            }), 400
        
        # Salvare提取文本
        project.total_text_length = len(all_text)
        ProjectManager.save_extracted_text(project.project_id, all_text)
        logger.info(f"文本提取Finalizare，共 {len(all_text)} 字符")
        
        # GenerareOntologie
        logger.info("调用 LLM GenerareOntologie定义...")
        generator = OntologyGenerator()
        ontology = generator.generate(
            document_texts=document_texts,
            simulation_requirement=simulation_requirement,
            additional_context=additional_context if additional_context else None
        )
        
        # SalvareOntologiela项目
        entity_count = len(ontology.get("entity_types", []))
        edge_count = len(ontology.get("edge_types", []))
        logger.info(f"OntologieGenerareFinalizare: {entity_count} 个EntitateTip, {edge_count} 个RelațieTip")
        
        project.ontology = {
            "entity_types": ontology.get("entity_types", []),
            "edge_types": ontology.get("edge_types", [])
        }
        project.analysis_summary = ontology.get("analysis_summary", "")
        project.status = ProjectStatus.ONTOLOGY_GENERATED
        ProjectManager.save_project(project)
        logger.info(f"=== OntologieGenerareFinalizare === 项目ID: {project.project_id}")
        
        return jsonify({
            "success": True,
            "data": {
                "project_id": project.project_id,
                "project_name": project.name,
                "ontology": project.ontology,
                "analysis_summary": project.analysis_summary,
                "files": project.files,
                "total_text_length": project.total_text_length
            }
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== Interfață2：ConstruireGraf ==============

@graph_bp.route('/build', methods=['POST'])
def build_graph():
    """
    Interfață2：根据project_idConstruireGraf
    
    Cerere（JSON）：
        {
            "project_id": "proj_xxxx",  // 必填，来自Interfață1
            "graph_name": "GrafNume",    // 可选
            "chunk_size": 500,          // 可选，Implicit500
            "chunk_overlap": 50         // 可选，Implicit50
        }
        
    Returnare：
        {
            "success": true,
            "data": {
                "project_id": "proj_xxxx",
                "task_id": "task_xxxx",
                "message": "GrafConstruire任务已启动"
            }
        }
    """
    try:
        logger.info("=== StartConstruireGraf ===")
        
        # VerificareConfigurare
        errors = []
        if not Config.ZEP_API_KEY:
            errors.append("ZEP_API_KEY未Configurare")
        if errors:
            logger.error(f"ConfigurareEroare: {errors}")
            return jsonify({
                "success": False,
                "error": "ConfigurareEroare: " + "; ".join(errors)
            }), 500
        
        # 解析Cerere
        data = request.get_json() or {}
        project_id = data.get('project_id')
        logger.debug(f"CerereParametru: project_id={project_id}")
        
        if not project_id:
            return jsonify({
                "success": False,
                "error": "请提供 project_id"
            }), 400
        
        # Obținere项目
        project = ProjectManager.get_project(project_id)
        if not project:
            return jsonify({
                "success": False,
                "error": f"项目Inexistent: {project_id}"
            }), 404
        
        # Verificare项目Stare
        force = data.get('force', False)  # 强制重新Construire
        
        if project.status == ProjectStatus.CREATED:
            return jsonify({
                "success": False,
                "error": "项目尚未GenerareOntologie，请先调用 /ontology/generate"
            }), 400
        
        if project.status == ProjectStatus.GRAPH_BUILDING and not force:
            return jsonify({
                "success": False,
                "error": "Graf正înConstruire，请勿重复提交。如需强制重建，请添加 force: true",
                "task_id": project.graph_build_task_id
            }), 400
        
        # dacă强制重建，重置Stare
        if force and project.status in [ProjectStatus.GRAPH_BUILDING, ProjectStatus.FAILED, ProjectStatus.GRAPH_COMPLETED]:
            project.status = ProjectStatus.ONTOLOGY_GENERATED
            project.graph_id = None
            project.graph_build_task_id = None
            project.error = None
        
        # ObținereConfigurare
        graph_name = data.get('graph_name', project.name or 'MiroFish Graph')
        chunk_size = data.get('chunk_size', project.chunk_size or Config.DEFAULT_CHUNK_SIZE)
        chunk_overlap = data.get('chunk_overlap', project.chunk_overlap or Config.DEFAULT_CHUNK_OVERLAP)
        
        # Actualizare项目Configurare
        project.chunk_size = chunk_size
        project.chunk_overlap = chunk_overlap
        
        # Obținere提取文本
        text = ProjectManager.get_extracted_text(project_id)
        if not text:
            return jsonify({
                "success": False,
                "error": "Negăsit提取文本Conținut"
            }), 400
        
        # ObținereOntologie
        ontology = project.ontology
        if not ontology:
            return jsonify({
                "success": False,
                "error": "NegăsitOntologie定义"
            }), 400
        
        # Creare异步任务
        task_manager = TaskManager()
        task_id = task_manager.create_task(f"ConstruireGraf: {graph_name}")
        logger.info(f"CreareGrafConstruire任务: task_id={task_id}, project_id={project_id}")
        
        # Actualizare项目Stare
        project.status = ProjectStatus.GRAPH_BUILDING
        project.graph_build_task_id = task_id
        ProjectManager.save_project(project)
        
        # 启动后台任务
        def build_task():
            build_logger = get_logger('mirofish.build')
            try:
                build_logger.info(f"[{task_id}] StartConstruireGraf...")
                task_manager.update_task(
                    task_id, 
                    status=TaskStatus.PROCESSING,
                    message="InițializareGrafConstruireServiciu..."
                )
                
                # CreareGrafConstruireServiciu
                builder = GraphBuilderService(api_key=Config.ZEP_API_KEY)
                
                # 分块
                task_manager.update_task(
                    task_id,
                    message="文本分块...",
                    progress=5
                )
                chunks = TextProcessor.split_text(
                    text, 
                    chunk_size=chunk_size, 
                    overlap=chunk_overlap
                )
                total_chunks = len(chunks)
                
                # CreareGraf
                task_manager.update_task(
                    task_id,
                    message="CreareZepGraf...",
                    progress=10
                )
                graph_id = builder.create_graph(name=graph_name)
                
                # Actualizare项目graph_id
                project.graph_id = graph_id
                ProjectManager.save_project(project)
                
                # 设置Ontologie
                task_manager.update_task(
                    task_id,
                    message="设置Ontologie定义...",
                    progress=15
                )
                builder.set_ontology(graph_id, ontology)
                
                # 添加文本（progress_callback 签名Da (msg, progress_ratio)）
                def add_progress_callback(msg, progress_ratio):
                    progress = 15 + int(progress_ratio * 40)  # 15% - 55%
                    task_manager.update_task(
                        task_id,
                        message=msg,
                        progress=progress
                    )
                
                task_manager.update_task(
                    task_id,
                    message=f"Start添加 {total_chunks} 个文本块...",
                    progress=15
                )
                
                episode_uuids = builder.add_text_batches(
                    graph_id, 
                    chunks,
                    batch_size=3,
                    progress_callback=add_progress_callback
                )
                
                # 等待ZepProcesareFinalizare（Interogare每个episodeprocessedStare）
                task_manager.update_task(
                    task_id,
                    message="等待ZepProcesareDate...",
                    progress=55
                )
                
                def wait_progress_callback(msg, progress_ratio):
                    progress = 55 + int(progress_ratio * 35)  # 55% - 90%
                    task_manager.update_task(
                        task_id,
                        message=msg,
                        progress=progress
                    )
                
                builder._wait_for_episodes(episode_uuids, wait_progress_callback)
                
                # ObținereGrafDate
                task_manager.update_task(
                    task_id,
                    message="ObținereGrafDate...",
                    progress=95
                )
                graph_data = builder.get_graph_data(graph_id)
                
                # Actualizare项目Stare
                project.status = ProjectStatus.GRAPH_COMPLETED
                ProjectManager.save_project(project)
                
                node_count = graph_data.get("node_count", 0)
                edge_count = graph_data.get("edge_count", 0)
                build_logger.info(f"[{task_id}] GrafConstruireFinalizare: graph_id={graph_id}, Nod={node_count}, 边={edge_count}")
                
                # Finalizare
                task_manager.update_task(
                    task_id,
                    status=TaskStatus.COMPLETED,
                    message="GrafConstruireFinalizare",
                    progress=100,
                    result={
                        "project_id": project_id,
                        "graph_id": graph_id,
                        "node_count": node_count,
                        "edge_count": edge_count,
                        "chunk_count": total_chunks
                    }
                )
                
            except Exception as e:
                # Actualizare项目Stare为Eșec
                build_logger.error(f"[{task_id}] GrafConstruireEșec: {str(e)}")
                build_logger.debug(traceback.format_exc())
                
                project.status = ProjectStatus.FAILED
                project.error = str(e)
                ProjectManager.save_project(project)
                
                task_manager.update_task(
                    task_id,
                    status=TaskStatus.FAILED,
                    message=f"ConstruireEșec: {str(e)}",
                    error=traceback.format_exc()
                )
        
        # 启动后台线程
        thread = threading.Thread(target=build_task, daemon=True)
        thread.start()
        
        return jsonify({
            "success": True,
            "data": {
                "project_id": project_id,
                "task_id": task_id,
                "message": "GrafConstruire任务已启动，请通过 /task/{task_id} Interogare进度"
            }
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== 任务InterogareInterfață ==============

@graph_bp.route('/task/<task_id>', methods=['GET'])
def get_task(task_id: str):
    """
    Interogare任务Stare
    """
    task = TaskManager().get_task(task_id)
    
    if not task:
        return jsonify({
            "success": False,
            "error": f"任务Inexistent: {task_id}"
        }), 404
    
    return jsonify({
        "success": True,
        "data": task.to_dict()
    })


@graph_bp.route('/tasks', methods=['GET'])
def list_tasks():
    """
    列出所有任务
    """
    tasks = TaskManager().list_tasks()
    
    return jsonify({
        "success": True,
        "data": [t.to_dict() for t in tasks],
        "count": len(tasks)
    })


# ============== GrafDateInterfață ==============

@graph_bp.route('/data/<graph_id>', methods=['GET'])
def get_graph_data(graph_id: str):
    """
    ObținereGrafDate（Nodși边）
    """
    try:
        if not Config.ZEP_API_KEY:
            return jsonify({
                "success": False,
                "error": "ZEP_API_KEY未Configurare"
            }), 500
        
        builder = GraphBuilderService(api_key=Config.ZEP_API_KEY)
        graph_data = builder.get_graph_data(graph_id)
        
        return jsonify({
            "success": True,
            "data": graph_data
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@graph_bp.route('/delete/<graph_id>', methods=['DELETE'])
def delete_graph(graph_id: str):
    """
    ȘtergereZepGraf
    """
    try:
        if not Config.ZEP_API_KEY:
            return jsonify({
                "success": False,
                "error": "ZEP_API_KEY未Configurare"
            }), 500
        
        builder = GraphBuilderService(api_key=Config.ZEP_API_KEY)
        builder.delete_graph(graph_id)
        
        return jsonify({
            "success": True,
            "message": f"Graf已Ștergere: {graph_id}"
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500
