"""
MiroFish Backend 启动入口
"""

import os
import sys

# 解决 Windows Consolă文乱码问题：în所有导入之前Setări UTF-8 编码
if sys.platform == 'win32':
    # SetăriMediuVariabilă确保 Python Utilizare UTF-8
    os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
    # 重新Configurare标准Output流为 UTF-8
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# 添加Proiect根DirectorlaCale
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.config import Config


def main():
    """主Funcție"""
    # VerificareConfigurare
    errors = Config.validate()
    if errors:
        print("ConfigurareEroare:")
        for err in errors:
            print(f"  - {err}")
        print("\n请Verificare .env FișierConfigurare")
        sys.exit(1)
    
    # CreareAplicare
    app = create_app()
    
    # ObținereRulareConfigurare
    host = os.environ.get('FLASK_HOST', '0.0.0.0')
    port = int(os.environ.get('FLASK_PORT', 5001))
    debug = Config.DEBUG
    
    # 启动Serviciu
    app.run(host=host, port=port, debug=debug, threaded=True)


if __name__ == '__main__':
    main()

