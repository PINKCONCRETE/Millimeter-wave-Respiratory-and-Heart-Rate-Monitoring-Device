"""测试处理器吞吐量.

测试MMWProcessorThread的处理性能，统计输入输出速率。
"""
import sys
import time
from pathlib import Path
from queue import Queue

# 添加父目录到sys.path以支持导入src模块
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.mmw_processor import MMWProcessorThread  # noqa: E402
from src.mmw_rader import MMWRadarThread  # noqa: E402


def test_processor_throughput(duration: int = 30) -> None:
    """测试处理器吞吐量.

    Args:
        duration: 测试时长（秒）

    """
    print("=" * 60)
    print("处理器吞吐量测试")
    print("=" * 60)
    print("\n配置信息:")
    print("  串口: COM7")
    print("  波特率: 921600")
    print("  通道数量: 8")
    print("  每通道bin数: 10")
    print("  滑动窗口: 1000帧")
    print(f"  测试时长: {duration} 秒")

    # 创建队列
    input_queue = Queue()
    output_queue = Queue()

    # 创建雷达线程
    print("\n初始化雷达线程...")
    radar_thread = MMWRadarThread(
        output_queue=input_queue,
        serial_port="COM7",
        serial_baudrate=921600,
        channel_num=8,
        bins_per_channel=10,
    )

    # 创建处理器线程
    print("初始化处理器线程...")
    processor_thread = MMWProcessorThread(
        input_queue=input_queue,
        output_queue=output_queue,
        channel_num=8,
        bins_per_channel=10,
        buffer_size=1000,
    )

    # 统计变量
    output_scg_points = 0
    start_time = time.time()
    last_print_time = start_time
    scg_points_in_last_second = 0

    print("\n启动线程...")
    radar_thread.start()
    processor_thread.start()
    print("\n开始监控处理器吞吐量...\n")

    try:
        while True:
            current_time = time.time()
            elapsed = current_time - start_time

            # 超过测试时长，退出
            if elapsed >= duration:
                break

            # 从输出队列获取处理后的数据
            if not output_queue.empty():
                _ = output_queue.get_nowait()  # 消费队列数据
                output_scg_points += 1
                scg_points_in_last_second += 1

            # 每秒打印一次统计
            if current_time - last_print_time >= 1.0:
                # 获取处理器统计信息
                stats = processor_thread.get_statistics()
                
                average_output_rate = (
                    output_scg_points / elapsed if elapsed > 0 else 0
                )

                print(
                    f"[{elapsed:.1f}s] "
                    f"输出: {scg_points_in_last_second} SCG点/s | "
                    f"平均: {average_output_rate:.1f} 点/s | "
                    f"总输出: {output_scg_points} 点 | "
                    f"接收帧: {stats['completed_frames']} | "
                    f"输入队列: {stats['input_queue_size']} | "
                    f"输出队列: {stats['output_queue_size']}"
                )

                last_print_time = current_time
                scg_points_in_last_second = 0

            # 短暂休眠
            time.sleep(0.01)

    except KeyboardInterrupt:
        print("\n\n测试被用户中断")
    finally:
        # 停止线程
        processor_thread.stop()

        # 最终统计
        total_elapsed = time.time() - start_time
        stats = processor_thread.get_statistics()

        average_output_rate = (
            output_scg_points / total_elapsed if total_elapsed > 0 else 0
        )

        print("\n" + "=" * 60)
        print("测试完成")
        print("=" * 60)
        print(f"总时长: {total_elapsed:.2f} 秒")
        
        print("\n雷达统计:")
        print(f"  接收完整帧数: {stats['completed_frames']:,}")
        print(f"  接收通道包数: {stats['received_channels']:,}")
        print(f"  平均帧率: {stats['frame_rate']:.1f} fps")
        
        print("\n处理器统计:")
        print(f"  生成SCG点数: {stats['generated_scg_points']:,}")
        print(f"  输出SCG点数: {output_scg_points:,}")
        print(f"  平均输出速率: {average_output_rate:.1f} 点/秒")
        
        print("\n队列状态:")
        print(f"  输入队列剩余: {stats['input_queue_size']}")
        print(f"  输出队列剩余: {stats['output_queue_size']}")
        print(f"  缓冲区大小: {stats['buffer_size']}/{stats['max_buffer_size']}")
        
        # 计算处理延迟
        if stats['completed_frames'] > 1000:
            processing_lag = stats['completed_frames'] - stats['generated_scg_points']
            print(f"\n处理延迟: {processing_lag} 帧")
            if processing_lag > 100:
                print("  ⚠️  警告: 处理速度跟不上接收速度")
            else:
                print("  ✓ 处理速度正常")
        
        # 理论值对比
        theoretical_rate = 200.0  # 理论200Hz
        print("\n理论值对比:")
        print(f"  理论输出速率: {theoretical_rate} 点/秒")
        if average_output_rate > 0:
            print(
                f"  实际占比: {(average_output_rate / theoretical_rate) * 100:.1f}%"
            )

        print("=" * 60)
        print("\n程序结束")


if __name__ == "__main__":
    # 默认测试30秒
    test_processor_throughput(duration=30)
