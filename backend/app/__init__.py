"""
MiroFish Backend - FlaskAplicare工厂
"""

import os
import warnings

# 抑制 multiprocessing resource_tracker Avertisment（来自第三方库如 transformers）
# 需要în所有其他导入之前Setări
warnings.filterwarnings("ignore", message=".*resource_tracker.*")

from flask import Flask, request
from flask_cors import CORS

from .config import Config
from .utils.logger import setup_logger, get_logger


def create_app(config_class=Config):
    """FlaskAplicare工厂Funcție"""
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # SetăriJSON编码：确保文直接显示（而不Da \uXXXX Format）
    # Flask >= 2.3 Utilizare app.json.ensure_ascii，旧VersiuneUtilizare JSON_AS_ASCII Configurare
    if hasattr(app, 'json') and hasattr(app.json, 'ensure_ascii'):
        app.json.ensure_ascii = False
    
    # SetăriJurnal
    logger = setup_logger('mirofish')
    
    # 只în reloader 子进程打印启动Informații（避免 debug 模式打印两次）
    is_reloader_process = os.environ.get('WERKZEUG_RUN_MAIN') == 'true'
    debug_mode = app.config.get('DEBUG', False)
    should_log_startup = not debug_mode or is_reloader_process
    
    if should_log_startup:
        logger.info("=" * 50)
        logger.info("MiroFish Backend 启动...")
        logger.info("=" * 50)
    
    # 启用CORS
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    
    # 注册Simulare进程清理Funcție（确保Serviciu器Închidere时终止所有Simulare进程）
    from .services.simulation_runner import SimulationRunner
    SimulationRunner.register_cleanup()
    if should_log_startup:
        logger.info("已注册Simulare进程清理Funcție")
    
    # CerereJurnal间件
    @app.before_request
    def log_request():
        logger = get_logger('mirofish.request')
        logger.debug(f"Cerere: {request.method} {request.path}")
        if request.content_type and 'json' in request.content_type:
            logger.debug(f"Cerere体: {request.get_json(silent=True)}")
    
    @app.after_request
    def log_response(response):
        logger = get_logger('mirofish.request')
        logger.debug(f"Răspuns: {response.status_code}")
        return response
    
    # 注册蓝图
    from .api import graph_bp, simulation_bp, report_bp
    app.register_blueprint(graph_bp, url_prefix='/api/graph')
    app.register_blueprint(simulation_bp, url_prefix='/api/simulation')
    app.register_blueprint(report_bp, url_prefix='/api/report')
    
    # 健康Verificare
    @app.route('/health')
    def health():
        return {'status': 'ok', 'service': 'MiroFish Backend'}
    
    if should_log_startup:
        logger.info("MiroFish Backend 启动Finalizare")
    
    return app

