"""快速验证流水线功能."""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root / "backend"))

print("=" * 60)
print("流水线快速验证")
print("=" * 60)

# 测试1: 导入模块
print("\n[测试1] 导入模块...")
try:
    from pipeline_connector import MMWPipeline, DatabaseWriter
    print("[OK] 成功导入 MMWPipeline 和 DatabaseWriter")
except Exception as e:
    print(f"[FAIL] 导入失败: {e}")
    sys.exit(1)

# 测试2: 创建流水线对象
print("\n[测试2] 创建流水线对象...")
try:
    pipeline = MMWPipeline(
        serial_port="COM7",
        serial_baudrate=921600,
        uid="test_user"
    )
    print("[OK] 流水线对象创建成功")
    print(f"  - Flask应用: {pipeline.app is not None}")
    print(f"  - 数据库写入器: {pipeline.db_writer is not None}")
    print(f"  - 雷达队列: {pipeline.radar_queue.maxsize}")
    print(f"  - SCG队列: {pipeline.scg_queue.maxsize}")
    print(f"  - 呼吸队列: {pipeline.breath_queue.maxsize}")
    print(f"  - 心率队列: {pipeline.hr_queue.maxsize}")
    print(f"  - 人体检测队列: {pipeline.human_queue.maxsize}")
except Exception as e:
    print(f"[FAIL] 创建失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 测试3: 验证数据库写入器
print("\n[测试3] 测试DatabaseWriter...")
try:
    import numpy as np
    import json
    from datetime import datetime
    
    # 写入SCG测试数据
    test_scg = np.random.randn(200)
    pipeline.db_writer.write_scg_waveform(test_scg, frame_idx=0)
    print("[OK] SCG波形写入成功")
    
    # 写入呼吸测试数据
    test_breath = {
        "rr_wave": [0.1 * i for i in range(100)],
        "displacement": [0.05 * i for i in range(50)],
        "flow_rate": [0.02 * i for i in range(50)],
        "rr": 16,
        "duty_cycle": 0.4
    }
    pipeline.db_writer.write_breath_data(test_breath)
    print("[OK] 呼吸数据写入成功")
    
    # 写入心率测试数据
    test_hr = {
        "heart_rate": 72,
        "ibi_data": "0.8,0.82,0.81",
        "arr": 0
    }
    pipeline.db_writer.write_heart_rate_data(test_hr)
    print("[OK] 心率数据写入成功")
    
    # 写入人体状态
    pipeline.db_writer.write_human_status(1)
    print("[OK] 人体状态写入成功")
    
    # 获取统计
    stats = pipeline.db_writer.get_write_statistics()
    print(f"[OK] 写入统计: SCG={stats['scg']}, 呼吸={stats['breath']}, 心率={stats['heart_rate']}, 状态={stats['human_status']}")
    
except Exception as e:
    print(f"[FAIL] DatabaseWriter测试失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 测试4: 验证数据是否真的写入了数据库
print("\n[测试4] 验证数据库记录...")
try:
    from models import db, UserWaveform, UserBr, UserHr, UserMove
    
    with pipeline.app.app_context():
        wave = db.session.query(UserWaveform).filter_by(uid="test_user").first()
        if wave:
            scg_data = json.loads(wave.scg_wave) if wave.scg_wave else []
            br_data = json.loads(wave.br_wave) if wave.br_wave else []
            print(f"[OK] 波形记录存在: SCG长度={len(scg_data)}, 呼吸长度={len(br_data)}")
        else:
            print("[WARN] 未找到波形记录")
        
        br_count = db.session.query(UserBr).filter_by(uid="test_user").count()
        hr_count = db.session.query(UserHr).filter_by(uid="test_user").count()
        move_count = db.session.query(UserMove).filter_by(uid="test_user").count()
        
        print(f"[OK] 数据库记录: 呼吸={br_count}, 心率={hr_count}, 状态={move_count}")
        
        # 清理测试数据
        db.session.query(UserWaveform).filter_by(uid="test_user").delete()
        db.session.query(UserBr).filter_by(uid="test_user").delete()
        db.session.query(UserHr).filter_by(uid="test_user").delete()
        db.session.query(UserMove).filter_by(uid="test_user").delete()
        db.session.commit()
        print("[OK] 测试数据已清理")
        
except Exception as e:
    print(f"[FAIL] 数据库验证失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 60)
print("[SUCCESS] 所有测试通过!")
print("=" * 60)
print("\n启动方式:")
print("  Windows: src\\start_pipeline.bat [COM口] [用户ID]")
print("  Linux:   ./src/start_pipeline.sh [设备] [用户ID]")
print("  Python:  python src/pipeline_connector.py --port COM7 --uid 0")
print("=" * 60)
