"""测试呼吸处理器吞吐量.

测试MMWBreathThread的处理性能，统计输入输出速率。
"""
import sys
import time
from pathlib import Path
from queue import Queue

# 添加父目录到sys.path以支持导入src模块
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.mmw_breath import MMWBreathThread  # noqa: E402
from src.mmw_rader import MMWRadarThread  # noqa: E402


def test_breath_throughput(duration: int = 30) -> None:
    """测试呼吸处理器吞吐量.

    Args:
        duration: 测试时长（秒）

    """
    print("=" * 60)
    print("呼吸处理器吞吐量测试")
    print("=" * 60)
    print("\n配置信息:")
    print("  串口: COM7")
    print("  波特率: 921600")
    print("  通道数量: 8")
    print("  每通道bin数: 10")
    print("  滑动窗口: 1000帧 (5秒)")
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

    # 创建呼吸处理器线程
    print("初始化呼吸处理器线程...")
    breath_thread = MMWBreathThread(
        input_queue=input_queue,
        output_queue=output_queue,
        channel_num=8,
        bins_per_channel=10,
        buffer_size=1000,
    )

    # 统计变量
    output_breath_results = 0
    valid_breath_cycles = 0
    start_time = time.time()
    last_print_time = start_time
    results_in_last_second = 0

    print("\n启动线程...")
    radar_thread.start()
    breath_thread.start()
    print("\n开始监控呼吸处理器吞吐量...\n")

    try:
        while True:
            current_time = time.time()
            elapsed = current_time - start_time

            # 超过测试时长，退出
            if elapsed >= duration:
                break

            # 从输出队列获取处理后的数据
            if not output_queue.empty():
                breath_dict = output_queue.get_nowait()
                output_breath_results += 1
                results_in_last_second += 1

                # 检查是否包含有效的呼吸周期
                if (
                    breath_dict["displacement"] is not None
                    and breath_dict["flow_rate"] is not None
                ):
                    valid_breath_cycles += 1

            # 每秒打印一次统计
            if current_time - last_print_time >= 1.0:
                # 获取处理器统计信息
                stats = breath_thread.get_statistics()

                average_output_rate = (
                    output_breath_results / elapsed if elapsed > 0 else 0
                )

                print(
                    f"[{elapsed:.1f}s] "
                    f"输出: {results_in_last_second} 结果/s | "
                    f"平均: {average_output_rate:.2f} 结果/s | "
                    f"总输出: {output_breath_results} | "
                    f"有效周期: {valid_breath_cycles} | "
                    f"接收帧: {stats['completed_frames']} | "
                    f"目标bin: {stats['current_target_bin']} | "
                    f"输入队列: {stats['input_queue_size']} | "
                    f"输出队列: {stats['output_queue_size']}"
                )

                last_print_time = current_time
                results_in_last_second = 0

    except KeyboardInterrupt:
        print("\n\n测试被用户中断")
    finally:
        # 停止线程
        breath_thread.stop()

        # 最终统计
        total_elapsed = time.time() - start_time
        average_output_rate = (
            output_breath_results / total_elapsed if total_elapsed > 0 else 0
        )

        stats = breath_thread.get_statistics()

        print("\n" + "=" * 60)
        print("测试完成")
        print("=" * 60)
        print(f"总时长: {total_elapsed:.2f} 秒")
        print(f"总输出结果数: {output_breath_results:,}")
        print(f"有效呼吸周期数: {valid_breath_cycles:,}")
        print(f"平均输出率: {average_output_rate:.2f} 结果/秒")
        print(f"接收完整帧数: {stats['completed_frames']:,}")
        print(f"平均帧率: {stats['frame_rate']:.2f} fps")

        # 理论值对比
        theoretical_frame_rate = 200.0  # 理论200Hz
        theoretical_output_rate = theoretical_frame_rate / 1000.0  # 每1000帧输出一次
        print("\n理论值对比:")
        print(f"  理论帧率: {theoretical_frame_rate} fps")
        print(
            f"  理论输出率: {theoretical_output_rate:.2f} 结果/秒 (每1000帧输出一次)"
        )
        print(f"  实际帧率占比: {(stats['frame_rate'] / theoretical_frame_rate) * 100:.1f}%")

        print("=" * 60)

        # 清空队列剩余数据
        remaining = output_queue.qsize()
        if remaining > 0:
            print(f"\n注意: 队列中还有 {remaining} 个未处理的结果")

        print("\n程序结束")


if __name__ == "__main__":
    # 默认测试30秒
    test_breath_throughput(duration=30)
