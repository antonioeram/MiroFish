"""
Configurare管理
统一de laProiect根Director .env FișierÎncărcareConfigurare
"""

import os
from dotenv import load_dotenv

# ÎncărcareProiect根Director .env Fișier
# Cale: MiroFish/.env (相pentru backend/app/config.py)
project_root_env = os.path.join(os.path.dirname(__file__), '../../.env')

if os.path.exists(project_root_env):
    load_dotenv(project_root_env, override=True)
else:
    # dacă根Director没有 .env，尝试ÎncărcareMediuVariabilă（用于生产Mediu）
    load_dotenv(override=True)


class Config:
    """FlaskConfigurareClasă"""
    
    # FlaskConfigurare
    SECRET_KEY = os.environ.get('SECRET_KEY', 'mirofish-secret-key')
    DEBUG = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    
    # JSONConfigurare - 禁用ASCII转义，让文直接显示（而不Da \uXXXX Format）
    JSON_AS_ASCII = False
    
    # LLMConfigurare（统一UtilizareOpenAIFormat）
    LLM_API_KEY = os.environ.get('LLM_API_KEY')
    LLM_BASE_URL = os.environ.get('LLM_BASE_URL', 'https://api.openai.com/v1')
    LLM_MODEL_NAME = os.environ.get('LLM_MODEL_NAME', 'gpt-4o-mini')
    
    # ZepConfigurare
    ZEP_API_KEY = os.environ.get('ZEP_API_KEY')
    
    # Fișier传Configurare
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), '../uploads')
    ALLOWED_EXTENSIONS = {'pdf', 'md', 'txt', 'markdown'}
    
    # TextProcesareConfigurare
    DEFAULT_CHUNK_SIZE = 500  # 默认切块大小
    DEFAULT_CHUNK_OVERLAP = 50  # 默认重叠大小
    
    # OASISSimulareConfigurare
    OASIS_DEFAULT_MAX_ROUNDS = int(os.environ.get('OASIS_DEFAULT_MAX_ROUNDS', '10'))
    OASIS_SIMULATION_DATA_DIR = os.path.join(os.path.dirname(__file__), '../uploads/simulations')
    
    # OASISPlatformă可用AcțiuneConfigurare
    OASIS_TWITTER_ACTIONS = [
        'CREATE_POST', 'LIKE_POST', 'REPOST', 'FOLLOW', 'DO_NOTHING', 'QUOTE_POST'
    ]
    OASIS_REDDIT_ACTIONS = [
        'LIKE_POST', 'DISLIKE_POST', 'CREATE_POST', 'CREATE_COMMENT',
        'LIKE_COMMENT', 'DISLIKE_COMMENT', 'SEARCH_POSTS', 'SEARCH_USER',
        'TREND', 'REFRESH', 'DO_NOTHING', 'FOLLOW', 'MUTE'
    ]
    
    # Report AgentConfigurare
    REPORT_AGENT_MAX_TOOL_CALLS = int(os.environ.get('REPORT_AGENT_MAX_TOOL_CALLS', '5'))
    REPORT_AGENT_MAX_REFLECTION_ROUNDS = int(os.environ.get('REPORT_AGENT_MAX_REFLECTION_ROUNDS', '2'))
    REPORT_AGENT_TEMPERATURE = float(os.environ.get('REPORT_AGENT_TEMPERATURE', '0.5'))
    
    @classmethod
    def validate(cls):
        """Verificare必要Configurare"""
        errors = []
        if not cls.LLM_API_KEY:
            errors.append("LLM_API_KEY 未Configurare")
        if not cls.ZEP_API_KEY:
            errors.append("ZEP_API_KEY 未Configurare")
        return errors

