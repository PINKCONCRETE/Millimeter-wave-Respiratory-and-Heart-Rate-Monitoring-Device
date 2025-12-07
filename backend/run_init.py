"""快速初始化数据库脚本."""
import os
import sys

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == '__main__':
    from init_db import init_database
    init_database()
