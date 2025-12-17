"""测试人体状态写入修复."""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root / "backend"))

from pipeline_connector import MMWPipeline
from models import db, UserMove
import logging

# 禁用SQLAlchemy详细日志
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)

print("=" * 60)
print("测试人体状态写入修复")
print("=" * 60)

pipeline = MMWPipeline(serial_port="COM7", uid="test_fix")

# 测试写入不同状态值
try:
    print("\n[测试1] 写入状态=1 (有人)...")
    pipeline.db_writer.write_human_status(1)
    print("[OK] 成功")
    
    print("\n[测试2] 写入状态=0 (无人)...")
    pipeline.db_writer.write_human_status(0)
    print("[OK] 成功")
    
    print("\n[测试3] 验证数据库记录...")
    with pipeline.app.app_context():
        records = db.session.query(UserMove).filter_by(uid="test_fix").all()
        print(f"[OK] 找到 {len(records)} 条记录")
        for i, r in enumerate(records, 1):
            print(f"  记录{i}: uid={r.uid}, state={r.state}, time={r.st_time}")
        
        # 清理
        db.session.query(UserMove).filter_by(uid="test_fix").delete()
        db.session.commit()
        print("[OK] 测试数据已清理")
    
    stats = pipeline.db_writer.get_write_statistics()
    print(f"\n[统计] 人体状态写入: {stats['human_status']} 条")
    
    print("\n" + "=" * 60)
    print("[SUCCESS] 人体状态写入问题已修复!")
    print("=" * 60)
    
except Exception as e:
    print(f"\n[FAIL] 错误: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
