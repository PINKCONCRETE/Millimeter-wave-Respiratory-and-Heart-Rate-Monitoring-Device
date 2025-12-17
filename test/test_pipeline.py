"""测试数据流水线功能.

测试从雷达采集到数据库存储的完整数据流。
"""
import sys
import time
from pathlib import Path
from datetime import datetime, timedelta

# 添加src和backend到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root / "backend"))

from flask import Flask
from models import db, UserWaveform, UserBr, UserHr, UserMove
from config import config


def test_database_connection():
    """测试1: 数据库连接."""
    print("\n" + "=" * 60)
    print("测试1: 数据库连接")
    print("=" * 60)
    
    try:
        app = Flask(__name__)
        app.config.from_object(config["development"])
        app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
        db.init_app(app)
        
        with app.app_context():
            db.create_all()
            print("[OK] 数据库连接成功")
            print(f"[OK] 数据库路径: {app.config['SQLALCHEMY_DATABASE_URI']}")
            
            # 检查表是否存在
            inspector = db.inspect(db.engine)
            tables = inspector.get_table_names()
            print(f"[OK] 数据库表数量: {len(tables)}")
            print(f"  表列表: {', '.join(tables)}")
            
        return True
        
    except Exception as e:
        print(f"[FAIL] 数据库连接失败: {e}")
        return False


def test_database_write():
    """测试2: 数据库写入功能."""
    print("\n" + "=" * 60)
    print("测试2: 数据库写入功能")
    print("=" * 60)
    
    try:
        app = Flask(__name__)
        app.config.from_object(config["development"])
        app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
        db.init_app(app)
        
        test_uid = f"test_{int(time.time())}"
        
        with app.app_context():
            # 写入波形数据
            import json
            scg_data = [i * 0.1 for i in range(200)]
            user_wave = UserWaveform(
                uid=test_uid,
                scg_wave=json.dumps(scg_data)
            )
            db.session.add(user_wave)
            db.session.commit()
            print(f"[OK] 写入SCG波形数据 ({len(scg_data)}个点)")
            
            # 写入呼吸数据
            now = datetime.utcnow()
            user_br = UserBr(
                uid=test_uid,
                st_time=now,
                en_time=now,
                rr=16,
                duty_cycle=0.4,
                ti=1.5,
                te=2.5
            )
            db.session.add(user_br)
            db.session.commit()
            print("[OK] 写入呼吸参数数据")
            
            # 写入心率数据
            user_hr = UserHr(
                uid=test_uid,
                st_time=now,
                en_time=now,
                hr=72
            )
            db.session.add(user_hr)
            db.session.commit()
            print("[OK] 写入心率数据")
            
            # 写入人体状态
            user_move = UserMove(
                uid=test_uid,
                st_time=now,
                state=1
            )
            db.session.add(user_move)
            db.session.commit()
            print("[OK] 写入人体状态数据")
            
            # 验证读取
            wave_count = db.session.query(UserWaveform).filter_by(uid=test_uid).count()
            br_count = db.session.query(UserBr).filter_by(uid=test_uid).count()
            hr_count = db.session.query(UserHr).filter_by(uid=test_uid).count()
            move_count = db.session.query(UserMove).filter_by(uid=test_uid).count()
            
            print(f"\n数据验证:")
            print(f"  波形记录: {wave_count}")
            print(f"  呼吸记录: {br_count}")
            print(f"  心率记录: {hr_count}")
            print(f"  状态记录: {move_count}")
            
            # 清理测试数据
            db.session.query(UserWaveform).filter_by(uid=test_uid).delete()
            db.session.query(UserBr).filter_by(uid=test_uid).delete()
            db.session.query(UserHr).filter_by(uid=test_uid).delete()
            db.session.query(UserMove).filter_by(uid=test_uid).delete()
            db.session.commit()
            print("[OK] 测试数据已清理")
            
        return True
        
    except Exception as e:
        print(f"[FAIL] 数据库写入测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_database_writer():
    """测试3: DatabaseWriter类."""
    print("\n" + "=" * 60)
    print("测试3: DatabaseWriter类")
    print("=" * 60)
    
    try:
        from pipeline_connector import DatabaseWriter
        import numpy as np
        
        app = Flask(__name__)
        app.config.from_object(config["development"])
        app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
        db.init_app(app)
        
        test_uid = f"test_writer_{int(time.time())}"
        writer = DatabaseWriter(app, uid=test_uid)
        
        # 测试SCG写入
        scg_array = np.random.randn(200)
        writer.write_scg_waveform(scg_array, frame_idx=0)
        print("[OK] DatabaseWriter.write_scg_waveform() 执行成功")
        
        # 测试呼吸写入
        breath_dict = {
            "rr_wave": [0.1 * i for i in range(100)],
            "displacement": [0.05 * i for i in range(50)],
            "flow_rate": [0.02 * i for i in range(50)],
            "rr": 18,
            "duty_cycle": 0.45
        }
        writer.write_breath_data(breath_dict)
        print("[OK] DatabaseWriter.write_breath_data() 执行成功")
        
        # 测试心率写入
        hr_dict = {
            "heart_rate": 75,
            "ibi_data": "0.8,0.82,0.81",
            "num_RR_interval": 3,
            "mean_RR_interval": 0.81,
            "arr": 0
        }
        writer.write_heart_rate_data(hr_dict)
        print("[OK] DatabaseWriter.write_heart_rate_data() 执行成功")
        
        # 测试人体状态写入
        writer.write_human_status(1)
        print("[OK] DatabaseWriter.write_human_status() 执行成功")
        
        # 获取统计
        stats = writer.get_write_statistics()
        print(f"\n写入统计:")
        print(f"  SCG: {stats['scg']}")
        print(f"  呼吸: {stats['breath']}")
        print(f"  心率: {stats['heart_rate']}")
        print(f"  状态: {stats['human_status']}")
        
        # 清理测试数据
        with app.app_context():
            db.session.query(UserWaveform).filter_by(uid=test_uid).delete()
            db.session.query(UserBr).filter_by(uid=test_uid).delete()
            db.session.query(UserHr).filter_by(uid=test_uid).delete()
            db.session.query(UserMove).filter_by(uid=test_uid).delete()
            db.session.commit()
        print("[OK] 测试数据已清理")
        
        return True
        
    except Exception as e:
        print(f"[FAIL] DatabaseWriter测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_pipeline_initialization():
    """测试4: MMWPipeline初始化."""
    print("\n" + "=" * 60)
    print("测试4: MMWPipeline初始化")
    print("=" * 60)
    
    try:
        from pipeline_connector import MMWPipeline
        
        # 创建流水线实例(不启动)
        pipeline = MMWPipeline(
            serial_port="COM7",
            serial_baudrate=921600,
            uid="test_pipeline"
        )
        print("[OK] MMWPipeline对象创建成功")
        
        # 检查组件
        assert pipeline.app is not None, "Flask app未初始化"
        print("[OK] Flask应用已初始化")
        
        assert pipeline.db_writer is not None, "DatabaseWriter未初始化"
        print("[OK] DatabaseWriter已初始化")
        
        assert pipeline.radar_queue is not None, "雷达队列未初始化"
        print("[OK] 数据队列已初始化")
        
        print(f"  队列配置:")
        print(f"    radar_queue: maxsize={pipeline.radar_queue.maxsize}")
        print(f"    scg_queue: maxsize={pipeline.scg_queue.maxsize}")
        print(f"    breath_queue: maxsize={pipeline.breath_queue.maxsize}")
        print(f"    hr_queue: maxsize={pipeline.hr_queue.maxsize}")
        print(f"    human_queue: maxsize={pipeline.human_queue.maxsize}")
        
        return True
        
    except Exception as e:
        print(f"[FAIL] MMWPipeline初始化测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行所有测试."""
    print("\n" + "=" * 60)
    print("数据流水线测试套件")
    print("=" * 60)
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    tests = [
        ("数据库连接", test_database_connection),
        ("数据库写入", test_database_write),
        ("DatabaseWriter类", test_database_writer),
        ("MMWPipeline初始化", test_pipeline_initialization),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n测试 '{name}' 发生异常: {e}")
            results.append((name, False))
        
        time.sleep(0.5)  # 间隔
    
    # 输出总结
    print("\n" + "=" * 60)
    print("测试结果总结")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "[OK] 通过" if result else "[FAIL] 失败"
        print(f"{status}: {name}")
    
    print(f"\n总计: {passed}/{total} 测试通过")
    
    if passed == total:
        print("\n[SUCCESS] 所有测试通过!")
        return 0
    else:
        print(f"\n[WARNING] {total - passed} 个测试失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())
