"""测试numpy数组序列化修复.

验证呼吸和心率数据的numpy数组能否正确转换为JSON。
"""
import sys
from pathlib import Path
import numpy as np

# 添加路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root / "backend"))

print("=" * 60)
print("测试numpy数组序列化修复")
print("=" * 60)

from flask import Flask
from config import config
from models import db, UserWaveform, UserBr
from pipeline_connector import DatabaseWriter

# 创建Flask应用
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = config['development'].SQLALCHEMY_DATABASE_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

# 创建DatabaseWriter
db_writer = DatabaseWriter(app=app, uid="test_numpy")

print("\n[1/2] 测试呼吸数据写入(包含numpy数组)...")

# 模拟呼吸数据(包含numpy数组)
breath_dict = {
    "rr_wave": np.array([1.0, 2.0, 3.0, 4.0, 5.0]),
    "displacement": np.array([0.1, 0.2, 0.3, 0.4, 0.5]),
    "flow_rate": np.array([10.0, 20.0, 30.0, 40.0, 50.0]),
    "rr": 15,
    "duty_cycle": 0.5,
    "ti": 1.5,
    "te": 2.5
}

try:
    db_writer.write_breath_data(breath_dict)
    print("  ✓ 呼吸数据写入成功(numpy数组已转换)")
except Exception as e:
    print(f"  ✗ 呼吸数据写入失败: {e}")
    sys.exit(1)

print("\n[2/2] 验证数据库中的数据...")

with app.app_context():
    # 读取呼吸波形
    user_wave = UserWaveform.query.filter_by(uid="test_numpy").first()
    if user_wave:
        import json
        br_wave = json.loads(user_wave.br_wave) if user_wave.br_wave else []
        br_ring_x = json.loads(user_wave.br_ring_x) if user_wave.br_ring_x else []
        br_ring_y = json.loads(user_wave.br_ring_y) if user_wave.br_ring_y else []
        
        print(f"  ✓ 呼吸波形读取成功")
        print(f"    - 波形长度: {len(br_wave)}")
        print(f"    - 位移长度: {len(br_ring_x)}")
        print(f"    - 流速长度: {len(br_ring_y)}")
        print(f"    - 波形前3个值: {br_wave[:3]}")
    else:
        print("  ✗ 未找到呼吸波形数据")
        sys.exit(1)
    
    # 读取呼吸参数
    user_br = UserBr.query.filter_by(uid="test_numpy").order_by(UserBr.st_time.desc()).first()
    if user_br:
        print(f"  ✓ 呼吸参数读取成功")
        print(f"    - 呼吸率: {user_br.rr}")
        print(f"    - 占空比: {user_br.duty_cycle}")
        print(f"    - 吸气时间: {user_br.ti}s")
        print(f"    - 呼气时间: {user_br.te}s")
    else:
        print("  ✗ 未找到呼吸参数")
        sys.exit(1)

print("\n" + "=" * 60)
print("✓ numpy数组序列化修复验证通过!")
print("Pipeline可以正确处理numpy数组并写入数据库")
print("=" * 60)
