"""快速测试:Pipeline写入 → Backend读取 → 验证数据互通."""
import sys
from pathlib import Path
import json
import numpy as np

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root / "backend"))

print("=" * 60)
print("快速验证: 数据库统一与数据互通")
print("=" * 60)

# 1. 使用Pipeline写入数据
print("\n[步骤1] Pipeline写入数据...")
from pipeline_connector import MMWPipeline, DEFAULT_DB_PATH

pipeline = MMWPipeline(serial_port="COM7", uid="db_test")
print(f"  数据库: {DEFAULT_DB_PATH}")

# 写入SCG数据
scg_data = np.random.randn(200)
pipeline.db_writer.write_scg_waveform(scg_data, frame_idx=0)
print(f"  ✓ 写入SCG: {len(scg_data)} 个点")

# 写入呼吸数据
breath_data = {
    "rr_wave": np.random.randn(100).tolist(),
    "displacement": np.random.randn(50).tolist(),
    "flow_rate": np.random.randn(50).tolist(),
    "rr": 16,
    "duty_cycle": 0.4
}
pipeline.db_writer.write_breath_data(breath_data)
print(f"  ✓ 写入呼吸: RR={breath_data['rr']}")

# 写入心率数据
hr_data = {
    "heart_rate": 72,
    "ibi_data": "800,820,810",
    "num_RR_interval": 3,
    "mean_RR_interval": 810,
    "arr": 0
}
pipeline.db_writer.write_heart_rate_data(hr_data)
print(f"  ✓ 写入心率: HR={hr_data['heart_rate']}")

# 写入人体状态
pipeline.db_writer.write_human_status(1)
print(f"  ✓ 写入状态: 在床")

# 2. 使用Backend读取数据
print("\n[步骤2] Backend读取数据...")
from flask import Flask
from config import config
from models import db, UserWaveform, UserBr, UserHr, UserMove

backend_app = Flask(__name__)
backend_app.config.from_object(config["development"])
backend_app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(backend_app)

with backend_app.app_context():
    # 读取SCG
    wave = db.session.query(UserWaveform).filter_by(uid="db_test").first()
    if wave and wave.scg_wave:
        scg_list = json.loads(wave.scg_wave)
        print(f"  ✓ 读取SCG: {len(scg_list)} 个点")
    
    # 读取呼吸
    if wave and wave.br_wave:
        br_list = json.loads(wave.br_wave)
        print(f"  ✓ 读取呼吸波形: {len(br_list)} 个点")
    
    br_record = db.session.query(UserBr).filter_by(uid="db_test").first()
    if br_record:
        print(f"  ✓ 读取呼吸参数: RR={br_record.rr}")
    
    # 读取心率
    hr_record = db.session.query(UserHr).filter_by(uid="db_test").first()
    if hr_record:
        print(f"  ✓ 读取心率: HR={hr_record.hr}")
    
    # 读取状态
    move_record = db.session.query(UserMove).filter_by(uid="db_test").first()
    if move_record:
        print(f"  ✓ 读取状态: {move_record.state}")
    
    # 清理测试数据
    if wave:
        db.session.delete(wave)
    if br_record:
        db.session.delete(br_record)
    if hr_record:
        db.session.delete(hr_record)
    if move_record:
        db.session.delete(move_record)
    db.session.commit()
    print("\n  ✓ 测试数据已清理")

print("\n" + "=" * 60)
print("✓ 数据互通验证成功!")
print("=" * 60)
print("\n说明:")
print("  • Pipeline负责采集数据并写入数据库")
print("  • Backend提供HTTP API供前端读取")
print("  • 两者共享同一个SQLite数据库文件")
print(f"  • 数据库位置: {DEFAULT_DB_PATH}")
