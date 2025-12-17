"""测试流水线基本功能 - 不连接真实硬件.

使用模拟数据验证流水线各模块能否正常启动和通信。
"""
import sys
import time
from pathlib import Path
from queue import Queue

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.mmw_database import MMWDatabaseWriter
import numpy as np


def test_database_writer():
    """测试数据库写入模块."""
    print("=" * 60)
    print("测试数据库写入模块")
    print("=" * 60)
    
    # 创建测试队列
    breath_queue = Queue()
    heart_queue = Queue()
    scg_queue = Queue()
    
    # 创建数据库写入器
    db_writer = MMWDatabaseWriter(
        breath_queue=breath_queue,
        heart_queue=heart_queue,
        scg_queue=scg_queue,
        uid=0,
    )
    
    # 启动线程
    db_writer.start()
    print("✓ 数据库写入线程已启动\n")
    
    # 发送测试数据
    print("发送测试数据...")
    
    # 1. 呼吸数据
    breath_data = {
        'breath_waveform': np.sin(np.linspace(0, 4*np.pi, 200)),
        'ring_x': np.sin(np.linspace(0, 10*np.pi, 1000)),
        'ring_y': np.cos(np.linspace(0, 10*np.pi, 1000)),
        'respiratory_rate': 16.5,
        'is_in_bed': True,
        'warning_id': 0,
    }
    breath_queue.put(breath_data)
    print("  ✓ 呼吸数据已发送")
    time.sleep(1)
    
    # 2. 心率数据
    heart_data = {
        'heart_waveform': np.sin(np.linspace(0, 4*np.pi, 200)),
        'heart_rate': 72.0,
        'is_in_bed': True,
        'is_arrhythmia': 0,
    }
    heart_queue.put(heart_data)
    print("  ✓ 心率数据已发送")
    time.sleep(1)
    
    # 3. SCG波形数据
    scg_data = {
        'scg_waveform': np.sin(np.linspace(0, 10*np.pi, 1000)),
    }
    scg_queue.put(scg_data)
    print("  ✓ SCG数据已发送")
    time.sleep(1)
    
    print("\n等待数据写入完成...")
    time.sleep(2)
    
    # 停止线程
    print("\n停止数据库写入线程...")
    db_writer.stop()
    db_writer.join(timeout=2)
    
    print("\n" + "=" * 60)
    print("✓ 测试完成")
    print("=" * 60)


def test_queue_communication():
    """测试队列通信."""
    print("\n" + "=" * 60)
    print("测试队列通信")
    print("=" * 60)
    
    test_queue = Queue(maxsize=10)
    
    # 测试写入
    print("\n写入测试数据...")
    for i in range(5):
        test_queue.put(f"数据 {i+1}")
        print(f"  ✓ 写入: 数据 {i+1}")
    
    # 测试读取
    print("\n读取测试数据...")
    while not test_queue.empty():
        data = test_queue.get(timeout=1)
        print(f"  ✓ 读取: {data}")
    
    print("\n✓ 队列通信正常")


def main():
    """主测试函数."""
    print("\n" + "=" * 60)
    print("流水线基础功能测试")
    print("=" * 60 + "\n")
    
    try:
        # 测试1: 队列通信
        test_queue_communication()
        
        # 测试2: 数据库写入
        test_database_writer()
        
        print("\n" + "=" * 60)
        print("所有测试通过 ✓")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
