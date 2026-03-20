"""
JurnalConfigurareModul
提供统一Jurnal管理，同时OutputlaConsolășiFișier
"""

import os
import sys
import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler


def _ensure_utf8_stdout():
    """
    确保 stdout/stderr Utilizare UTF-8 编码
    解决 Windows Consolă文乱码问题
    """
    if sys.platform == 'win32':
        # Windows 重新Configurare标准Output为 UTF-8
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')


# JurnalDirector
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'logs')


def setup_logger(name: str = 'mirofish', level: int = logging.DEBUG) -> logging.Logger:
    """
    SetăriJurnal器
    
    Args:
        name: Jurnal器Nume
        level: Jurnal级别
        
    Returns:
        Configurare好Jurnal器
    """
    # 确保JurnalDirector存în
    os.makedirs(LOG_DIR, exist_ok=True)
    
    # CreareJurnal器
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # 阻止Jurnalcătre传播la根 logger，避免重复Output
    logger.propagate = False
    
    # dacă已经有Procesare器，不重复添加
    if logger.handlers:
        return logger
    
    # JurnalFormat
    detailed_formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    simple_formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s: %(message)s',
        datefmt='%H:%M:%S'
    )
    
    # 1. FișierProcesare器 - 详细Jurnal（按Dată命名，带轮转）
    log_filename = datetime.now().strftime('%Y-%m-%d') + '.log'
    file_handler = RotatingFileHandler(
        os.path.join(LOG_DIR, log_filename),
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(detailed_formatter)
    
    # 2. ConsolăProcesare器 - 简洁Jurnal（INFO及以）
    # 确保 Windows Utilizare UTF-8 编码，避免文乱码
    _ensure_utf8_stdout()
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(simple_formatter)
    
    # 添加Procesare器
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger


def get_logger(name: str = 'mirofish') -> logging.Logger:
    """
    ObținereJurnal器（dacă不存în则Creare）
    
    Args:
        name: Jurnal器Nume
        
    Returns:
        Jurnal器实例
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        return setup_logger(name)
    return logger


# Creare默认Jurnal器
logger = setup_logger()


# 便捷Metodă
def debug(msg, *args, **kwargs):
    logger.debug(msg, *args, **kwargs)

def info(msg, *args, **kwargs):
    logger.info(msg, *args, **kwargs)

def warning(msg, *args, **kwargs):
    logger.warning(msg, *args, **kwargs)

def error(msg, *args, **kwargs):
    logger.error(msg, *args, **kwargs)

def critical(msg, *args, **kwargs):
    logger.critical(msg, *args, **kwargs)

