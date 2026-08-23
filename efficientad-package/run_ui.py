"""EfficientAD UI 免安装启动器。

用法（在本目录下）:
    python run_ui.py [--image 图] [--model30 模型目录] [--model31 模型目录]

自动把 src/ 加入模块搜索路径，无需 pip install。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from efficientad.application.ui.app1 import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
