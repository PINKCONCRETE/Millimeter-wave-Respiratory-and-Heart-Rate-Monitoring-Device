"""测试SCG数据库写入功能.

模拟SCG处理器产生数据，验证批量写入功能。
"""
import sys
import time
from pathlib import Path
from queue import Queue

import numpy as np

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.mmw_database import SCGDatabaseWriter


def simulate_scg_data_generator(output_queue: Queue, total_points: int = 500):
    """模拟SCG处理器产生数据.
    
    Args:
        output_queue: 输出队列
        total_points: 总共产生的数据点数
    """
    print(f"\n[模拟器] 开始产生 {total_points} 个SCG数据点...")
    
    for i in range(total_points):
        # 模拟SCG数据：正弦波 + 噪声
        scg_value = np.sin(i * 0.1) * 100 + np.random.randn() * 10
        
        # 构造数据格式（与MMWProcessorThread输出一致）
        scg_data = {
            "frame_idx": i,
            "scg_value": float(scg_value),
            "timestamp": i * 0.005  # 5ms间隔
        }
        
        output_queue.put(scg_data)
        
        # 每产生50个点打印一次进度
        if (i + 1) % 50 == 0:
            print(f"[模拟器] 已产生 {i + 1} 个数据点")
        
        # 模拟真实采集速率（5ms/点 = 200Hz）
        time.sleep(0.005)
    
    print(f"[模拟器] 完成，共产生 {total_points} 个数据点\n")


def test_scg_database_writer():
    """测试SCG数据库写入器."""
    print("=" * 70)
    print("测试SCG数据库写入器 - 200点批量写入")
    print("=" * 70)
    
    # 创建队列
    scg_queue = Queue()
    
    # 创建SCG数据库写入器
    print("\n[测试] 创建SCG数据库写入器...")
    db_writer = SCGDatabaseWriter(
        input_queue=scg_queue,
        uid=0,
        callback=lambda buffer, total: print(
            f"[回调] 写入完成 - 本批: {len(buffer)}点, 累计: {total}点"
        )
    )
    
    # 启动写入线程
    db_writer.start()
    time.sleep(1)  # 等待线程启动
    
    # 模拟产生500个SCG数据点
    # 预期: 500点 / 200点每批 = 2次完整写入 + 100点剩余
    simulate_scg_data_generator(scg_queue, total_points=500)
    
    # 等待队列处理完成
    print("\n[测试] 等待队列处理完成...")
    while not scg_queue.empty():
        time.sleep(0.5)
        print(f"[测试] 队列剩余: {scg_queue.qsize()} 个数据点")
    
    time.sleep(2)  # 等待最后一批写入
    
    # 打印统计信息
    stats = db_writer.get_statistics()
    print("\n" + "=" * 70)
    print("统计信息:")
    print(f"  总接收点数: {stats['total_points_received']}")
    print(f"  总写入次数: {stats['total_writes']}")
    print(f"  缓冲区剩余: {stats['buffer_size']}/{stats['buffer_capacity']}")
    print(f"  队列剩余: {stats['queue_size']}")
    print(f"  运行时间: {stats['elapsed_time']:.2f}秒")
    print(f"  处理速率: {stats['points_per_second']:.1f} 点/秒")
    print("=" * 70)
    
    # 停止写入器（会自动写入剩余数据）
    print("\n[测试] 停止写入器...")
    db_writer.stop()
    db_writer.join(timeout=3)
    
    # 验证结果
    print("\n" + "=" * 70)
    if stats['total_points_received'] == 500:
        print("✓ 测试通过：成功接收全部500个数据点")
        print(f"✓ 预期写入次数: 2次完整写入（200×2）+ 停止时写入剩余100点")
        print(f"✓ 实际写入次数: {stats['total_writes']} 次")
    else:
        print(f"✗ 测试失败：预期500点，实际接收{stats['total_points_received']}点")
    print("=" * 70)


def test_continuous_update(duration: int = 10):
    """测试持续更新模式.
    
    Args:
        duration: 测试时长（秒）
    """
    print("\n" + "=" * 70)
    print(f"测试持续更新模式 - 运行 {duration} 秒")
    print("=" * 70)
    
    scg_queue = Queue()
    db_writer = SCGDatabaseWriter(input_queue=scg_queue, uid=0)
    db_writer.start()
    
    start_time = time.time()
    point_count = 0
    
    print("\n[测试] 开始持续产生数据...")
    print("按 Ctrl+C 提前停止\n")
    
    try:
        while (time.time() - start_time) < duration:
            # 产生数据（200Hz = 每秒200个点）
            scg_value = np.sin(point_count * 0.1) * 100
            scg_queue.put({
                "frame_idx": point_count,
                "scg_value": float(scg_value),
                "timestamp": point_count * 0.005
            })
            point_count += 1
            time.sleep(0.005)  # 5ms间隔
            
    except KeyboardInterrupt:
        print("\n[测试] 用户中断")
    
    print(f"\n[测试] 完成，共产生 {point_count} 个数据点")
    
    # 等待处理完成
    time.sleep(2)
    
    # 停止并显示统计
    stats = db_writer.get_statistics()
    print("\n统计信息:")
    print(f"  总接收: {stats['total_points_received']} 点")
    print(f"  写入次数: {stats['total_writes']} 次")
    print(f"  处理速率: {stats['points_per_second']:.1f} 点/秒")
    
    db_writer.stop()
    db_writer.join(timeout=3)


def main():
    """主测试函数."""
    import argparse
    
    parser = argparse.ArgumentParser(description='SCG数据库写入测试')
    parser.add_argument(
        '--mode',
        choices=['batch', 'continuous'],
        default='batch',
        help='测试模式: batch(批量测试) 或 continuous(持续测试)'
    )
    parser.add_argument(
        '--duration',
        type=int,
        default=10,
        help='持续模式运行时长（秒），默认10秒'
    )
    
    args = parser.parse_args()
    
    try:
        if args.mode == 'batch':
            test_scg_database_writer()
        else:
            test_continuous_update(args.duration)
        
        print("\n" + "=" * 70)
        print("✓ 所有测试完成")
        print("=" * 70)
        return 0
        
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
