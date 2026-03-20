"""
JurnalConfigurare模块
提供统一的Jurnal管理，同时输出到控制台和Fișier
"""

import os
import sys
import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler


def _ensure_utf8_stdout():
    """
    确保 stdout/stderr 使用 UTF-8 编码
    解决 Windows 控制台中文乱码问题
    """
    if sys.platform == 'win32':
        # Windows 下重新Configurare标准输出为 UTF-8
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')


# Jurnal目录
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'logs')


def setup_logger(name: str = 'mirofish', level: int = logging.DEBUG) -> logging.Logger:
    """
    设置Jurnal器
    
    Args:
        name: Jurnal器Nume
        level: Jurnal级别
        
    Returns:
        Configurare好的Jurnal器
    """
    # 确保Jurnal目录存在
    os.makedirs(LOG_DIR, exist_ok=True)
    
    # CreareJurnal器
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # 阻止Jurnal向上传播到根 logger，避免重复输出
    logger.propagate = False
    
    # 如果已经有Procesare器，不重复添加
    if logger.handlers:
        return logger
    
    # Jurnal格式
    detailed_formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    simple_formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s: %(message)s',
        datefmt='%H:%M:%S'
    )
    
    # 1. FișierProcesare器 - 详细Jurnal（按日期命名，带轮转）
    log_filename = datetime.now().strftime('%Y-%m-%d') + '.log'
    file_handler = RotatingFileHandler(
        os.path.join(LOG_DIR, log_filename),
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(detailed_formatter)
    
    # 2. 控制台Procesare器 - 简洁Jurnal（INFO及以上）
    # 确保 Windows 下使用 UTF-8 编码，避免中文乱码
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
    ObținereJurnal器（如果不存在则Creare）
    
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


# 便捷方法
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

