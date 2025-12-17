"""测试雷达解包速率.

测试MMWRaderThread的解包性能，统计每秒解包的帧数和bin包数。
"""
import sys
import time
from pathlib import Path
from queue import Queue

# 添加父目录到sys.path以支持导入src模块
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.mmw_rader import MMWRadarThread  # noqa: E402


def test_decode_rate(duration: int = 30) -> None:
    """测试雷达解包速率.

    Args:
        duration: 测试时长（秒）

    """
    print("=" * 60)
    print("雷达解包速率测试")
    print("=" * 60)
    print("\n配置信息:")
    print("  串口: COM7")
    print("  波特率: 921600")
    print("  通道数量: 8")
    print("  每通道bin数: 10")
    print(f"  测试时长: {duration} 秒")

    # 创建队列
    data_queue = Queue()

    # 创建雷达线程
    print("\n初始化雷达线程...")
    radar_thread = MMWRadarThread(
        output_queue=data_queue,
        serial_port="COM7",
        serial_baudrate=921600,
        channel_num=8,
        bins_per_channel=10,
    )

    # 统计变量
    received_channels = 0
    received_frames = 0
    start_time = time.time()
    last_print_time = start_time
    channels_in_last_second = 0
    frames_in_last_second = 0

    print("启动雷达线程...")
    radar_thread.start()
    print("\n开始监控解包速率...\n")

    try:
        while True:
            current_time = time.time()
            elapsed = current_time - start_time

            # 超过测试时长，退出
            if elapsed >= duration:
                break

            # 从队列获取数据
            if not data_queue.empty():
                frame_data = data_queue.get()
                channel_id = frame_data["channel_id"]
                
                received_channels += 1
                channels_in_last_second += 1

                # 检测完整帧（channel_id = 7表示8个通道都接收完）
                if channel_id == 7:
                    received_frames += 1
                    frames_in_last_second += 1

            # 每秒打印一次统计
            if current_time - last_print_time >= 1.0:
                average_channel_rate = received_channels / elapsed if elapsed > 0 else 0
                average_frame_rate = received_frames / elapsed if elapsed > 0 else 0

                print(
                    f"[{elapsed:.1f}s] "
                    f"当前: {channels_in_last_second} 通道包/s, "
                    f"{frames_in_last_second} 帧/s | "
                    f"平均: {average_channel_rate:.1f} 通道包/s, "
                    f"{average_frame_rate:.1f} 帧/s | "
                    f"总计: {received_channels} 通道包, {received_frames} 帧"
                )

                last_print_time = current_time
                channels_in_last_second = 0
                frames_in_last_second = 0

    except KeyboardInterrupt:
        print("\n\n测试被用户中断")
    finally:
        # 最终统计
        total_elapsed = time.time() - start_time
        average_channel_rate = received_channels / total_elapsed if total_elapsed > 0 else 0
        average_frame_rate = (
            received_frames / total_elapsed if total_elapsed > 0 else 0
        )

        print("\n" + "=" * 60)
        print("测试完成")
        print("=" * 60)
        print(f"总时长: {total_elapsed:.2f} 秒")
        print(f"总通道包数: {received_channels:,}")
        print(f"总完整帧数: {received_frames:,}")
        print(f"平均通道包率: {average_channel_rate:.1f} 包/秒")
        print(f"平均帧率: {average_frame_rate:.1f} 帧/秒")

        # 计算每通道包字节数：SOF(4字节) + DATA(10个bin×4字节) = 44字节
        bytes_per_channel = 4 + (10 * 4)  # SOF + 10个bin（每个bin 4字节）
        total_bytes = received_channels * bytes_per_channel
        byte_rate = total_bytes / total_elapsed if total_elapsed > 0 else 0

        print("\n数据量统计:")
        print(f"  每通道包字节数: {bytes_per_channel} Bytes")
        print(f"  总接收数据: {total_bytes:,} Bytes ({total_bytes / 1024:.2f} KB)")
        print(f"  数据速率: {byte_rate:,.1f} Bytes/s ({byte_rate / 1024:.2f} KB/s)")

        # 理论值对比
        theoretical_frame_rate = 200.0  # 理论200Hz
        theoretical_channel_rate = theoretical_frame_rate * 8
        print("\n理论值对比:")
        print(f"  理论帧率: {theoretical_frame_rate} fps")
        print(f"  理论通道包率: {theoretical_channel_rate} 包/秒")
        print(
            f"  实际帧率占比: {(average_frame_rate / theoretical_frame_rate) * 100:.1f}%"
        )

        print("=" * 60)

        # 清空队列剩余数据
        remaining = data_queue.qsize()
        if remaining > 0:
            print(f"\n注意: 队列中还有 {remaining} 个未处理的bin包")

        print("\n程序结束")


if __name__ == "__main__":
    # 默认测试30秒
    test_decode_rate(duration=30)
