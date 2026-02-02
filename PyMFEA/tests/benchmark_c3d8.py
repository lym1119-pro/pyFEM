# 用于单独测试 C3D8 单元
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.node import Node
from core.element import C3D8Element
from core.material import LinearElastic

print("测试 C3D8 单元...")
mat = LinearElastic(210e9, 0.3)
# ... 测试逻辑
