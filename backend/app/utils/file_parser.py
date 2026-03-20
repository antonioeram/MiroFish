"""
FișierAnalizăInstrument
SuportăPDF、Markdown、TXTFișierText提取
"""

import os
from pathlib import Path
from typing import List, Optional


def _read_text_with_fallback(file_path: str) -> str:
    """
    读取TextFișier，UTF-8Eșec时自动探测编码。
    
    采用多级回退策略：
    1. 首先尝试 UTF-8 解码
    2. Utilizare charset_normalizer 检测编码
    3. 回退la chardet 检测编码
    4. 最终Utilizare UTF-8 + errors='replace' 兜底
    
    Args:
        file_path: FișierCale
        
    Returns:
        解码后TextConținut
    """
    data = Path(file_path).read_bytes()
    
    # 首先尝试 UTF-8
    try:
        return data.decode('utf-8')
    except UnicodeDecodeError:
        pass
    
    # 尝试Utilizare charset_normalizer 检测编码
    encoding = None
    try:
        from charset_normalizer import from_bytes
        best = from_bytes(data).best()
        if best and best.encoding:
            encoding = best.encoding
    except Exception:
        pass
    
    # 回退la chardet
    if not encoding:
        try:
            import chardet
            result = chardet.detect(data)
            encoding = result.get('encoding') if result else None
        except Exception:
            pass
    
    # 最终兜底：Utilizare UTF-8 + replace
    if not encoding:
        encoding = 'utf-8'
    
    return data.decode(encoding, errors='replace')


class FileParser:
    """FișierAnaliză器"""
    
    SUPPORTED_EXTENSIONS = {'.pdf', '.md', '.markdown', '.txt'}
    
    @classmethod
    def extract_text(cls, file_path: str) -> str:
        """
        de laFișier提取Text
        
        Args:
            file_path: FișierCale
            
        Returns:
            提取TextConținut
        """
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"Fișier不存în: {file_path}")
        
        suffix = path.suffix.lower()
        
        if suffix not in cls.SUPPORTED_EXTENSIONS:
            raise ValueError(f"不SuportăFișierFormat: {suffix}")
        
        if suffix == '.pdf':
            return cls._extract_from_pdf(file_path)
        elif suffix in {'.md', '.markdown'}:
            return cls._extract_from_md(file_path)
        elif suffix == '.txt':
            return cls._extract_from_txt(file_path)
        
        raise ValueError(f"无法ProcesareFișierFormat: {suffix}")
    
    @staticmethod
    def _extract_from_pdf(file_path: str) -> str:
        """de laPDF提取Text"""
        try:
            import fitz  # PyMuPDF
        except ImportError:
            raise ImportError("需要安装PyMuPDF: pip install PyMuPDF")
        
        text_parts = []
        with fitz.open(file_path) as doc:
            for page in doc:
                text = page.get_text()
                if text.strip():
                    text_parts.append(text)
        
        return "\n\n".join(text_parts)
    
    @staticmethod
    def _extract_from_md(file_path: str) -> str:
        """de laMarkdown提取Text，Suportă自动编码检测"""
        return _read_text_with_fallback(file_path)
    
    @staticmethod
    def _extract_from_txt(file_path: str) -> str:
        """de laTXT提取Text，Suportă自动编码检测"""
        return _read_text_with_fallback(file_path)
    
    @classmethod
    def extract_from_multiple(cls, file_paths: List[str]) -> str:
        """
        de la多个Fișier提取Text并合并
        
        Args:
            file_paths: FișierCaleListă
            
        Returns:
            合并后Text
        """
        all_texts = []
        
        for i, file_path in enumerate(file_paths, 1):
            try:
                text = cls.extract_text(file_path)
                filename = Path(file_path).name
                all_texts.append(f"=== Documentație {i}: {filename} ===\n{text}")
            except Exception as e:
                all_texts.append(f"=== Documentație {i}: {file_path} (提取Eșec: {str(e)}) ===")
        
        return "\n\n".join(all_texts)


def split_text_into_chunks(
    text: str, 
    chunk_size: int = 500, 
    overlap: int = 50
) -> List[str]:
    """
    将Text分割成小块
    
    Args:
        text: 原始Text
        chunk_size: 每块字符数
        overlap: 重叠字符数
        
    Returns:
        Text块Listă
    """
    if len(text) <= chunk_size:
        return [text] if text.strip() else []
    
    chunks = []
    start = 0
    
    while start < len(text):
        end = start + chunk_size
        
        # 尝试în句子边界处分割
        if end < len(text):
            # 查找最近句子结束符
            for sep in ['。', '！', '？', '.\n', '!\n', '?\n', '\n\n', '. ', '! ', '? ']:
                last_sep = text[start:end].rfind(sep)
                if last_sep != -1 and last_sep > chunk_size * 0.3:
                    end = start + last_sep + len(sep)
                    break
        
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        
        # 一个块de la重叠位置Start
        start = end - overlap if end < len(text) else len(text)
    
    return chunks

