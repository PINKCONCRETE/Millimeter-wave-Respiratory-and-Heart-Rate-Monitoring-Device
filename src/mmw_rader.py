# pylint: disable=too-many-arguments,too-many-instance-attributes
"""毫米波雷达数据采集模块 (多进程版).

实现基于状态机的串口数据解码，支持多bin复数数据采集。
"""
import struct
import multiprocessing
import time
from queue import Empty
from typing import Any
import serial

from src.config import SERIAL_PORT, SERIAL_BAUDRATE

class MMWRadarProcess(multiprocessing.Process):
    """毫米波雷达数据采集进程（生产者）.

    通过串口连接毫米波雷达，接收并解码原始数据帧。
    实现基于状态机的帧解码，支持8个通道 × 每通道10个频率bin的数据采集。
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
        output_queue: multiprocessing.Queue,
        serial_port: str = SERIAL_PORT,
        serial_baudrate: int = SERIAL_BAUDRATE,
        channel_num: int = 8,
        bins_per_channel: int = 10,
    ) -> None:
        super().__init__()
        self.daemon = True
        
        self._output_queue = output_queue
        self._serial_port = serial_port
        self._serial_baudrate = serial_baudrate
        self._channel_num = channel_num
        self._bins_per_channel = bins_per_channel

        self._running = True
        self._serial = None # 在 run() 中初始化

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
        self._received_frames = 0
        self._last_received_frames = 0
        self._received_channels = 0
        self._last_received_channels = 0
        self._received_bytes = 0
        self._last_received_bytes = 0
        self._start_time = 0.0
        self._last_fps_time = 0.0

    def _init_serial(self) -> Any:
        """初始化串口连接"""
        if self._serial_port and self._serial_baudrate:
            try:
                return serial.Serial(self._serial_port, self._serial_baudrate)
            except serial.SerialException as e:
                print(f"串口初始化失败: {e}")
                return None
        return None

    def run(self) -> None:
        """进程主循环."""
        print(f"雷达采集进程已启动 (PID: {self.pid})，正在打开串口 {self._serial_port}...")
        
        self._serial = self._init_serial()
        if not self._serial:
            print("错误：串口初始化失败，进程退出")
            return

        self._running = True
        
        # 统计信息 (进程内局部变量)
        self._received_frames = 0
        self._last_received_frames = 0
        self._received_channels = 0
        self._last_received_channels = 0
        self._received_bytes = 0
        self._last_received_bytes = 0
        self._start_time = time.time()
        self._last_fps_time = time.time()

        try:
            while self._running:
                try:
                    waiting = self._serial.in_waiting
                    if waiting > 0:
                        byte_data = self._serial.read(waiting)
                        self._received_bytes += len(byte_data)
                        
                        for byte in byte_data:
                            self.decode(byte)
                            if not self._running:
                                break
                    else:
                        time.sleep(0.0001)
                except OSError as e:
                    print(f"串口读取错误: {e}")
                    break
        except KeyboardInterrupt:
            print("\n雷达进程接收到中断信号")
        finally:
            if self._serial and self._serial.is_open:
                self._serial.close()
            print("雷达进程已停止")

    def stop(self) -> None:
        self.terminate()

    def decode(self, byte_data: int) -> None:
        # 简化版状态机分发，减少函数调用开销
        if self.decode_status == self.STATE_WAITING_DLC_LOW:
            self._temp_bins_count = byte_data
            self.decode_status = self.STATE_WAITING_DLC_HIGH
            
        elif self.decode_status == self.STATE_WAITING_DLC_HIGH:
            self._temp_bins_count |= (byte_data << 8)
            if self._temp_bins_count == self._bins_per_channel:
                self.decode_status = self.STATE_WAITING_BIN_ID
            else:
                self.decode_status = self.STATE_WAITING_DLC_LOW
                
        elif self.decode_status == self.STATE_WAITING_BIN_ID:
            self._temp_channel_id = byte_data
            if self._temp_channel_id >= self._channel_num:
                self.decode_status = self.STATE_WAITING_DLC_LOW
                return

            if self._temp_channel_id == 0:
                self.decode_status = self.STATE_WAITING_OFFSET
            else:
                self.decode_status = self.STATE_CHECK_OFFSET
                
        elif self.decode_status == self.STATE_WAITING_OFFSET:
            self._temp_offset = byte_data
            self._complex_count = 0
            self._temp_complexes = []
            self.decode_status = self.STATE_GET_REAL_LOW
            
        elif self.decode_status == self.STATE_CHECK_OFFSET:
            if byte_data == 0:
                self._complex_count = 0
                self._temp_complexes = []
                self.decode_status = self.STATE_GET_REAL_LOW
            else:
                self.decode_status = self.STATE_WAITING_DLC_LOW
                
        elif self.decode_status == self.STATE_GET_REAL_LOW:
            self._temp_real = byte_data
            self.decode_status = self.STATE_GET_REAL_HIGH
            
        elif self.decode_status == self.STATE_GET_REAL_HIGH:
            self._temp_real |= (byte_data << 8)
            self._temp_real = self._to_signed_int16(self._temp_real)
            self.decode_status = self.STATE_GET_IMAG_LOW
            
        elif self.decode_status == self.STATE_GET_IMAG_LOW:
            self._temp_imag = byte_data
            self.decode_status = self.STATE_GET_IMAG_HIGH
            
        elif self.decode_status == self.STATE_GET_IMAG_HIGH:
            self._temp_imag |= (byte_data << 8)
            self._temp_imag = self._to_signed_int16(self._temp_imag)

            complex_num = complex(self._temp_real, self._temp_imag)
            self._temp_complexes.append(complex_num)
            self._complex_count += 1

            if self._complex_count < self._temp_bins_count:
                self.decode_status = self.STATE_GET_REAL_LOW
            else:
                self._finish_frame()

    @staticmethod
    def _to_signed_int16(value: int) -> int:
        return struct.unpack("<h", struct.pack("<H", value))[0]

    def _finish_frame(self) -> None:
        if self._start_time is None:
            self._start_time = time.time()

        # 发送数据到队列
        try:
            self._output_queue.put({
                "channel_id": self._temp_channel_id,
                "bins_count": self._temp_bins_count,
                "offset": self._temp_offset,
                "data": self._temp_complexes.copy() # copy list
            })
        except:
            pass # Queue full or closed

        self._received_channels += 1

        if self._temp_channel_id == self._channel_num - 1:
            self._received_frames += 1
            
            now = time.time()
            if now - self._last_fps_time >= 1.0:
                fps = (self._received_frames - self._last_received_frames) / (now - self._last_fps_time)
                print(f"[Radar] FPS: {fps:.1f}")
                
                self._last_received_frames = self._received_frames
                self._last_fps_time = now

        self.decode_status = self.STATE_WAITING_DLC_LOW
