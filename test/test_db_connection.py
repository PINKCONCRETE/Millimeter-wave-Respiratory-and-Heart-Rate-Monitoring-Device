"""测试数据库连接.

验证Pipeline和Backend是否使用同一个数据库。
"""
import sys
from pathlib import Path

# 添加src到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root / "backend"))

print("=" * 60)
print("测试数据库连接")
print("=" * 60)

# 1. 检查Pipeline的数据库路径
print("\n[1/4] 检查Pipeline配置...")
from pipeline_connector import DEFAULT_DB_PATH
print(f"Pipeline数据库路径: {DEFAULT_DB_PATH}")
print(f"  - 存在: {DEFAULT_DB_PATH.exists()}")
print(f"  - 大小: {DEFAULT_DB_PATH.stat().st_size if DEFAULT_DB_PATH.exists() else 0} bytes")

# 2. 检查Backend的数据库路径  
print("\n[2/4] 检查Backend配置...")
from config import config
dev_config = config['development']
db_uri = dev_config.SQLALCHEMY_DATABASE_URI
# 提取路径: sqlite:///C:/path/to/db -> C:/path/to/db
backend_db_path = Path(db_uri.replace('sqlite:///', ''))
print(f"Backend数据库路径: {backend_db_path}")
print(f"  - 存在: {backend_db_path.exists()}")
print(f"  - 大小: {backend_db_path.stat().st_size if backend_db_path.exists() else 0} bytes")

# 3. 验证路径一致性
print("\n[3/4] 验证路径一致性...")
if DEFAULT_DB_PATH.resolve() == backend_db_path.resolve():
    print("✓ Pipeline和Backend使用相同数据库!")
    print(f"  共享路径: {DEFAULT_DB_PATH}")
else:
    print("✗ 路径不一致!")
    print(f"  Pipeline: {DEFAULT_DB_PATH.resolve()}")
    print(f"  Backend:  {backend_db_path.resolve()}")
    sys.exit(1)

# 4. 测试数据库写入读取
print("\n[4/4] 测试数据库操作...")

# 创建Flask应用用于数据库操作
from flask import Flask
from models import db, UserMove

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

# Pipeline写入
from pipeline_connector import DatabaseWriter
db_writer = DatabaseWriter(app=app, uid="test_connection")
print("  - 尝试写入人体状态...")
db_writer.write_human_status(1)
print("  ✓ Pipeline写入成功")

# Backend读取
with app.app_context():
    latest = UserMove.query.filter_by(uid="test_connection").order_by(UserMove.st_time.desc()).first()
    if latest:
        print(f"  ✓ Backend读取成功")
        print(f"    - UID: {latest.uid}")
        print(f"    - 状态: {latest.state}")
        print(f"    - 时间: {latest.st_time}")
    else:
        print("  ✗ Backend未读取到数据")
        sys.exit(1)

print("\n" + "=" * 60)
print("✓ 数据库连接测试通过!")
print("Pipeline和Backend可以正常通信")
print("=" * 60)
