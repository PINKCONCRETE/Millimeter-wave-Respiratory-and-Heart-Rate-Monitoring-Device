"""验证pipeline_connector和backend使用同一个数据库."""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root / "backend"))

print("=" * 70)
print("验证数据库统一性")
print("=" * 70)

# 1. 检查backend的数据库路径
print("\n[1] Backend数据库配置:")
from config import config
backend_db_uri = config["development"].SQLALCHEMY_DATABASE_URI
print(f"  URI: {backend_db_uri}")

# 提取实际路径
import re
match = re.search(r'sqlite:///(.+)', backend_db_uri)
if match:
    backend_db_path = Path(match.group(1))
    print(f"  路径: {backend_db_path}")
    print(f"  存在: {backend_db_path.exists()}")
    if backend_db_path.exists():
        print(f"  大小: {backend_db_path.stat().st_size} bytes")

# 2. 检查pipeline_connector的数据库路径
print("\n[2] Pipeline数据库配置:")
from pipeline_connector import MMWPipeline, DEFAULT_DB_PATH

print(f"  默认路径: {DEFAULT_DB_PATH}")
print(f"  存在: {DEFAULT_DB_PATH.exists()}")
if DEFAULT_DB_PATH.exists():
    print(f"  大小: {DEFAULT_DB_PATH.stat().st_size} bytes")

# 创建pipeline实例检查
pipeline = MMWPipeline(serial_port="COM7", uid="test")
pipeline_db_uri = pipeline.app.config["SQLALCHEMY_DATABASE_URI"]
print(f"  Pipeline URI: {pipeline_db_uri}")

# 3. 验证路径一致性
print("\n[3] 路径一致性检查:")
if match:
    backend_path_resolved = backend_db_path.resolve()
    pipeline_path_resolved = DEFAULT_DB_PATH.resolve()
    
    print(f"  Backend:  {backend_path_resolved}")
    print(f"  Pipeline: {pipeline_path_resolved}")
    
    if backend_path_resolved == pipeline_path_resolved:
        print("  ✓ 路径一致 - 前后端使用同一数据库")
    else:
        print("  ✗ 路径不一致 - 需要修正配置")

# 4. 测试数据互通
print("\n[4] 测试数据互通:")
from flask import Flask
from models import db, UserWaveform
import json
import logging

# 禁用日志
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)

# 使用pipeline写入数据
test_uid = "test_unified_db"
try:
    print(f"  [Pipeline] 写入测试数据 (uid={test_uid})...")
    test_scg = [0.1 * i for i in range(200)]
    pipeline.db_writer.write_scg_waveform(test_scg, frame_idx=0)
    print("  ✓ Pipeline写入成功")
    
    # 使用backend读取数据
    print(f"  [Backend] 读取测试数据...")
    backend_app = Flask(__name__)
    backend_app.config.from_object(config["development"])
    backend_app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(backend_app)
    
    with backend_app.app_context():
        wave = db.session.query(UserWaveform).filter_by(uid=test_uid).first()
        if wave and wave.scg_wave:
            scg_data = json.loads(wave.scg_wave)
            print(f"  ✓ Backend读取成功: {len(scg_data)} 个数据点")
            print(f"    前5个点: {scg_data[:5]}")
            
            # 清理测试数据
            db.session.delete(wave)
            db.session.commit()
            print("  ✓ 测试数据已清理")
            
            print("\n" + "=" * 70)
            print("✓ 数据库统一验证成功! 前后端可以正常通信")
            print("=" * 70)
        else:
            print("  ✗ Backend无法读取Pipeline写入的数据")
            
except Exception as e:
    print(f"  ✗ 错误: {e}")
    import traceback
    traceback.print_exc()

print("\n提示: 启动pipeline时将自动使用backend的数据库")
print(f"  数据库位置: {DEFAULT_DB_PATH}")
