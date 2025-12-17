"""测试呼吸数据库写入器."""
import sys
import time
from pathlib import Path
from queue import Queue

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.mmw_database import BreathDatabaseWriter
import numpy as np


def test_breath_writer():
    """测试呼吸写入器批量写入."""
    print("=" * 60)
    print("测试呼吸数据库写入器")
    print("=" * 60)
    
    # 创建队列和写入器
    breath_queue = Queue()
    test_db = project_root / 'database' / 'test_breath.db'
    writer = BreathDatabaseWriter(breath_queue, uid=1, database_path=str(test_db))
    writer.start()
    
    # 模拟5次呼吸数据（每次200个波形点 + 1000个环点）
    print("\n发送5次呼吸数据:")
    for i in range(5):
        # 生成模拟数据
        rr_wave = np.sin(np.linspace(0, 4*np.pi, 1000)) + np.random.normal(0, 0.1, 1000)
        displacement = np.sin(np.linspace(0, 2*np.pi, 1000))
        flow_rate = np.cos(np.linspace(0, 2*np.pi, 1000))
        
        breath_data = {
            'rr_wave': rr_wave.tolist(),
            'displacement': displacement.tolist(),
            'flow_rate': flow_rate.tolist(),
            'target_bin': 10,
            'frame_idx': i,
        }
        
        breath_queue.put(breath_data)
        print(f"  [{i+1}] 发送呼吸数据 (波形: 1000点, 环: 1000点)")
        time.sleep(0.5)
    
    # 等待处理完成
    print("\n等待写入器处理...")
    time.sleep(3)
    
    # 停止写入器
    print("\n停止写入器")
    writer.stop()
    writer.join(timeout=5)
    
    # 统计
    stats = writer.get_statistics()
    print("\n" + "=" * 60)
    print("统计结果:")
    print(f"  接收数据次数: {stats['total_data_received']}")
    print(f"  数据库写入次数: {stats['total_writes']}")
    print(f"  缓冲区剩余: {stats['buffer_size']}")
    print("=" * 60)
    
    # 验证结果
    expected_writes = 5  # 每次都写入（因为每次都>=200点）
    if stats['total_writes'] == expected_writes:
        print(f"\n✓ 测试通过！预期 {expected_writes} 次写入，实际 {stats['total_writes']} 次")
    else:
        print(f"\n✗ 测试失败！预期 {expected_writes} 次写入，实际 {stats['total_writes']} 次")


if __name__ == "__main__":
    test_breath_writer()
