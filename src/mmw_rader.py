# pylint: disable=too-many-arguments,too-many-instance-attributes
"""毫米波雷达数据采集模块.

实现基于状态机的串口数据解码，支持多bin复数数据采集。
"""
import struct
import threading
import time
from queue import Queue

import serial


class MMWRaderThread(threading.Thread):
    """毫米波雷达数据采集线程（生产者）.

    通过串口连接毫米波雷达，接收并解码原始数据帧。
    实现基于状态机的帧解码，支持8个通道 × 每通道10个频率bin的数据采集。

    Attributes:
        channel_num: 通道数量（默认8）
        bins_per_channel: 每个通道的频率bin数量（默认10）
        decode_status: 当前解码状态机状态

    """

    # 状态机状态常量
    STATE_WAITING_DLC_LOW = 0
    STATE_WAITING_DLC_HIGH = 1
    STATE_WAITING_BIN_ID = 2
    STATE_WAITING_OFFSET = 3
    STATE_CHECK_OFFSET = 4
    STATE_GET_REAL_LOW = 5
    STATE_GET_REAL_HIGH = 6
    STATE_GET_IMAG_LOW = 7
    STATE_GET_IMAG_HIGH = 8

    def __init__(
        self,
        output_queue: Queue | None = None,
        serial_port: str = "COM7",
        serial_baudrate: int = 921600,
        channel_num: int = 8,
        bins_per_channel: int = 10,
    ) -> None:
        """
        初始化毫米波雷达线程
        
        Args:
            output_queue: 输出队列，用于存放解码后的数据
            serial_port: 串口号
            serial_baudrate: 波特率
            channel_num: 通道数量
            bins_per_channel: 每个通道的频率bin数量
        """
        super().__init__()

        self._serial = MMWRaderThread._init_serial(serial_port, serial_baudrate)
        self._channel_num = channel_num
        self._bins_per_channel = bins_per_channel
        self._output_queue = output_queue or Queue()
        self._data: list[list[complex]] = [[] for _ in range(channel_num)]

        # 状态机状态
        self.decode_status = self.STATE_WAITING_DLC_LOW

        # 临时缓存变量
        self._temp_bins_count = 0
        self._temp_channel_id = 0
        self._temp_offset = 0
        self._temp_real = 0
        self._temp_imag = 0
        self._complex_count = 0
        self._temp_complexes: list[complex] = []

        # 统计信息
        self._received_frames = 0  # 接收的完整帧数（通道 0-7全部接收）
        self._received_channels = 0  # 接收的通道包数
        self._received_bytes = 0  # 接收的字节数
        self._start_time = None
        
        # 线程控制
        self._running = False

    @staticmethod
    def _init_serial(port: str, baudrate: int) -> serial.Serial | None:
        """初始化串口连接"""
        if port and baudrate:
            try:
                return serial.Serial(port, baudrate)
            except serial.SerialException as e:
                print(f"串口初始化失败: {e}")
                return None
        return None

    def decode(self, byte_data: int) -> None:
        """
        解码部分 - 根据状态机处理每个字节
        
        状态机说明:
            S0-S3: SOF帧头解析（数据长度和bin序号）
            D0-D3: DATA字段解析（10个复数）
        
        Args:
            byte_data: 接收到的字节数据
        """
        state_handlers = {
            self.STATE_WAITING_DLC_LOW: self._handle_dlc_low,
            self.STATE_WAITING_DLC_HIGH: self._handle_dlc_high,
            self.STATE_WAITING_BIN_ID: self._handle_bin_id,
            self.STATE_WAITING_OFFSET: self._handle_offset,
            self.STATE_CHECK_OFFSET: self._handle_check_offset,
            self.STATE_GET_REAL_LOW: self._handle_real_low,
            self.STATE_GET_REAL_HIGH: self._handle_real_high,
            self.STATE_GET_IMAG_LOW: self._handle_imag_low,
            self.STATE_GET_IMAG_HIGH: self._handle_imag_high,
        }

        handler = state_handlers.get(self.decode_status)
        if handler:
            handler(byte_data)

    def _handle_dlc_low(self, byte_data: int) -> None:
        """处理数据长度低字节"""
        self._temp_bins_count = byte_data
        self.decode_status = self.STATE_WAITING_DLC_HIGH

    def _handle_dlc_high(self, byte_data: int) -> None:
        """处理数据长度高字节并验证"""
        self._temp_bins_count |= (byte_data << 8)
        if self._temp_bins_count == self._bins_per_channel:
            self.decode_status = self.STATE_WAITING_BIN_ID
        else:
            self.decode_status = self.STATE_WAITING_DLC_LOW

    def _handle_bin_id(self, byte_data: int) -> None:
        """处理通道序号"""
        self._temp_channel_id = byte_data

        # 验证 channel_id 是否在有效范围内
        if self._temp_channel_id >= self._channel_num:
            # channel_id 无效，回到初始状态
            self.decode_status = self.STATE_WAITING_DLC_LOW
            return

        if self._temp_channel_id == 0:
            # channel_id = 0，需要读取 offset
            self.decode_status = self.STATE_WAITING_OFFSET
        else:
            # channel_id != 0，跳转到 check_offset 状态
            self.decode_status = self.STATE_CHECK_OFFSET

    def _handle_offset(self, byte_data: int) -> None:
        """处理 offset 字节（仅当 channel_id=0 时）"""
        self._temp_offset = byte_data
        # 初始化 DATA 阶段，i = 0
        self._complex_count = 0
        self._temp_complexes = []
        self.decode_status = self.STATE_GET_REAL_LOW

    def _handle_check_offset(self, byte_data: int) -> None:
        """检查 offset 是否为 0（当 channel_id != 0 时）"""
        if byte_data == 0:
            # offset = 0，初始化 DATA 阶段，i = 0
            self._complex_count = 0
            self._temp_complexes = []
            self.decode_status = self.STATE_GET_REAL_LOW
        else:
            # offset != 0，回到初始状态
            self.decode_status = self.STATE_WAITING_DLC_LOW

    def _handle_real_low(self, byte_data: int) -> None:
        """处理实部低字节"""
        self._temp_real = byte_data
        self.decode_status = self.STATE_GET_REAL_HIGH

    def _handle_real_high(self, byte_data: int) -> None:
        """处理实部高字节并转换为有符号整数"""
        self._temp_real |= (byte_data << 8)
        self._temp_real = self._to_signed_int16(self._temp_real)
        self.decode_status = self.STATE_GET_IMAG_LOW

    def _handle_imag_low(self, byte_data: int) -> None:
        """处理虚部低字节"""
        self._temp_imag = byte_data
        self.decode_status = self.STATE_GET_IMAG_HIGH

    def _handle_imag_high(self, byte_data: int) -> None:
        """处理虚部高字节并输出复数"""
        self._temp_imag |= (byte_data << 8)
        self._temp_imag = self._to_signed_int16(self._temp_imag)

        # 构建并保存复数
        complex_num = complex(self._temp_real, self._temp_imag)
        self._temp_complexes.append(complex_num)
        self._complex_count += 1

        # 判断是否接收完所有复数
        if self._complex_count < self._temp_bins_count:
            self.decode_status = self.STATE_GET_REAL_LOW
        else:
            self._finish_frame()

    @staticmethod
    def _to_signed_int16(value: int) -> int:
        """将无符号16位整数转换为有符号整数"""
        return struct.unpack("<h", struct.pack("<H", value))[0]

    def _finish_frame(self) -> None:
        """完成一帧数据的接收"""
        if self._start_time is None:
            self._start_time = time.time()

        self._data[self._temp_channel_id] = self._temp_complexes.copy()
        self._output_queue.put({
            "channel_id": self._temp_channel_id,
            "bins_count": self._temp_bins_count,
            "data": self._temp_complexes.copy()
        })
        self._received_channels += 1

        # 当channel_id为7时，表示一个完整帧接收完毕
        if self._temp_channel_id == self._channel_num - 1:
            self._received_frames += 1

            # 每100帧打印一次统计
            if self._received_frames % 100 == 0:
                elapsed = time.time() - self._start_time
                frame_rate = self._received_frames / elapsed if elapsed > 0 else 0
                channel_rate = self._received_channels / elapsed if elapsed > 0 else 0
                byte_rate = self._received_bytes / elapsed if elapsed > 0 else 0
                print(f"[雷达] 已接收 {self._received_frames} 帧 | "
                      f"帧率: {frame_rate:.1f} fps | "
                      f"通道包率: {channel_rate:.1f} 包/秒 | "
                      f"吞吐量: {byte_rate:,.0f} Bytes/s ({byte_rate / 1024:.2f} KB/s)")

        self.decode_status = self.STATE_WAITING_DLC_LOW

    def run(self) -> None:
        """线程主循环 - 从串口读取数据并进行解码"""
        if not self._serial:
            print("错误：串口未初始化")
            return

        self._running = True
        print(f"开始从 {self._serial.port} 读取数据...")

        try:
            while self._running:
                # 批量读取可用数据，提高效率
                waiting = self._serial.in_waiting
                if waiting > 0:
                    # 一次性读取所有可用字节
                    byte_data = self._serial.read(waiting)
                    self._received_bytes += len(byte_data)
                    # 逐字节解码
                    for byte in byte_data:
                        self.decode(byte)
                        if not self._running:  # 支持在解码过程中中断
                            break
                else:
                    # 没有数据时短暂休眠，避免CPU空转
                    time.sleep(0.0001)  # 0.1ms
        except KeyboardInterrupt:
            print("\n接收到中断信号，停止接收数据...")
            self.stop()
        finally:
            self._close_serial()

    def stop(self) -> None:
        """停止线程运行"""
        print("正在停止雷达线程...")
        self._running = False
    
    def _close_serial(self) -> None:
        """关闭串口连接"""
        if self._serial and self._serial.is_open:
            self._serial.close()
            print("串口已关闭")

    def get_data(
        self, channel_id: int | None = None
    ) -> list[list[complex]] | list[complex] | None:
        """获取存储的数据.

        Args:
            channel_id: 通道序号，如果为None则返回所有通道的数据

        Returns:
            指定通道的数据列表或所有通道的数据，无效时返回None

        """
        if channel_id is None:
            return self._data
        if 0 <= channel_id < self._channel_num:
            return self._data[channel_id]
        return None

    def __repr__(self) -> str:
        """返回对象的字符串表示"""
        return (
            f"MMWRaderThread("
            f"channel_num={self._channel_num}, "
            f"bins_per_channel={self._bins_per_channel}, "
            f"serial={self._serial.port if self._serial else 'None'}, "
            f"data_available={any(self._data)})"
        )


if __name__ == "__main__":
    # 示例用法
    radar = MMWRaderThread(serial_port="COM7")
    print(radar)
    # radar.start()  # 取消注释以启动数据采集
