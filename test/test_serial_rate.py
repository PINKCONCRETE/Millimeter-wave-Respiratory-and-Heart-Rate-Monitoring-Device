"""测试串口数据接收速率.

监控串口数据流量，统计每秒接收的字节数。
"""
import time
import serial


def test_serial_rate(
    port: str = "COM7", baudrate: int = 921600, duration: int = 10
) -> None:
    """测试串口接收速率.

    Args:
        port: 串口号
        baudrate: 波特率
        duration: 测试时长（秒）

    """
    print("=" * 60)
    print("串口数据接收速率测试")
    print("=" * 60)
    print("\n配置信息:")
    print(f"  串口: {port}")
    print(f"  波特率: {baudrate}")
    print(f"  测试时长: {duration} 秒")
    print("\n正在连接串口...")

    try:
        ser = serial.Serial(port, baudrate, timeout=1)
        print(f"串口连接成功: {ser.port}")
        print("\n开始监控数据流量...\n")

        # 统计变量
        total_bytes = 0
        start_time = time.time()
        last_print_time = start_time
        bytes_in_last_second = 0

        while True:
            current_time = time.time()
            elapsed = current_time - start_time

            # 超过测试时长，退出
            if elapsed >= duration:
                break

            # 读取可用数据
            if ser.in_waiting > 0:
                data = ser.read(ser.in_waiting)
                data_len = len(data)
                total_bytes += data_len
                bytes_in_last_second += data_len

            # 每秒打印一次统计
            if current_time - last_print_time >= 1.0:
                average_rate = total_bytes / elapsed if elapsed > 0 else 0
                print(f"[{elapsed:.1f}s] "
                      f"当前速率: {bytes_in_last_second:,} Bytes/s | "
                      f"平均速率: {average_rate:,.1f} Bytes/s | "
                      f"总接收: {total_bytes:,} Bytes")
                
                last_print_time = current_time
                bytes_in_last_second = 0

        # 最终统计
        total_elapsed = time.time() - start_time
        average_rate = total_bytes / total_elapsed if total_elapsed > 0 else 0

        print("\n" + "=" * 60)
        print("测试完成")
        print("=" * 60)
        print(f"总时长: {total_elapsed:.2f} 秒")
        print(f"总接收: {total_bytes:,} Bytes ({total_bytes / 1024:.2f} KB)")
        print(f"平均速率: {average_rate:,.1f} Bytes/s ({average_rate / 1024:.2f} KB/s)")
        print(f"理论波特率: {baudrate / 10:,.1f} Bytes/s ({baudrate / 10 / 1024:.2f} KB/s)")
        print(f"利用率: {(average_rate / (baudrate / 10)) * 100:.1f}%")
        print("=" * 60)

    except serial.SerialException as e:
        print(f"\n错误: 无法打开串口 - {e}")
    except KeyboardInterrupt:
        print("\n\n测试被用户中断")
        if 'total_bytes' in locals() and 'start_time' in locals():
            total_elapsed = time.time() - start_time
            average_rate = total_bytes / total_elapsed if total_elapsed > 0 else 0
            print(f"\n已接收: {total_bytes:,} Bytes")
            print(f"平均速率: {average_rate:,.1f} Bytes/s")
    finally:
        if 'ser' in locals() and ser.is_open:
            ser.close()
            print("\n串口已关闭")


if __name__ == "__main__":
    # 默认配置
    test_serial_rate(
        port="COM7",
        baudrate=921600,
        duration=10  # 测试10秒
    )
