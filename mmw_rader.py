# pylint: disable=too-many-arguments,too-many-instance-attributes
"""
Module for MMWRader class
"""
import struct
import threading
from queue import Queue
from typing import Optional, List

import serial


class MMWRaderThread(threading.Thread):
    """
    毫米波雷达管理类
    
    用于串口连接毫米波雷达后接收、解码、存储并管理毫米波雷达数据。
    实现了基于状态机的帧解码，支持多bin复数数据采集。
    
    Attributes:
        bin_num: bin的数量
        dlc: 每帧的复数数量
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
        output_queue: Optional[Queue] = None,
        serial_port: str = "COM7",
        serial_baudrate: int = 921600,
        bin_num: int = 8,
        dlc: int = 10,
    ) -> None:
        """
        初始化毫米波雷达线程
        
        Args:
            output_queue: 输出队列，用于存放解码后的数据
            serial_port: 串口号
            serial_baudrate: 波特率
            bin_num: bin的数量
            dlc: 每帧的复数数量
        """
        super().__init__()
        
        self._serial = self._init_serial(serial_port, serial_baudrate)
        self._bin_num = bin_num
        self._dlc = dlc
        self._output_queue = output_queue or Queue()
        self._data: List[List[complex]] = [[] for _ in range(bin_num)]
        
        # 状态机状态
        self.decode_status = self.STATE_WAITING_DLC_LOW
        
        # 临时缓存变量
        self._temp_dlc = 0
        self._temp_bin_id = 0
        self._temp_offset = 0
        self._temp_real = 0
        self._temp_imag = 0
        self._complex_count = 0
        self._temp_complexes: List[complex] = []
    
    @staticmethod
    def _init_serial(port: str, baudrate: int) -> Optional[serial.Serial]:
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
        self._temp_dlc = byte_data
        self.decode_status = self.STATE_WAITING_DLC_HIGH
    
    def _handle_dlc_high(self, byte_data: int) -> None:
        """处理数据长度高字节并验证"""
        self._temp_dlc |= (byte_data << 8)
        if self._temp_dlc == self._dlc:
            self.decode_status = self.STATE_WAITING_BIN_ID
        else:
            self.decode_status = self.STATE_WAITING_DLC_LOW
    
    def _handle_bin_id(self, byte_data: int) -> None:
        """处理bin序号"""
        self._temp_bin_id = byte_data
        if self._temp_bin_id == 0:
            # bin_id = 0，需要读取 offset
            self.decode_status = self.STATE_WAITING_OFFSET
        else:
            # bin_id != 0，跳转到 check_offset 状态
            self.decode_status = self.STATE_CHECK_OFFSET
    
    def _handle_offset(self, byte_data: int) -> None:
        """处理 offset 字节（仅当 bin_id=0 时）"""
        self._temp_offset = byte_data
        # 初始化 DATA 阶段，i = 0
        self._complex_count = 0
        self._temp_complexes = []
        self.decode_status = self.STATE_GET_REAL_LOW
    
    def _handle_check_offset(self, byte_data: int) -> None:
        """检查 offset 是否为 0（当 bin_id != 0 时）"""
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
        if self._complex_count < self._temp_dlc:
            self.decode_status = self.STATE_GET_REAL_LOW
        else:
            self._finish_frame()
    
    @staticmethod
    def _to_signed_int16(value: int) -> int:
        """将无符号16位整数转换为有符号整数"""
        return struct.unpack('<h', struct.pack('<H', value))[0]
    
    def _finish_frame(self) -> None:
        """完成一帧数据的接收"""
        self._data[self._temp_bin_id] = self._temp_complexes.copy()
        self._output_queue.put({
            'bin_id': self._temp_bin_id,
            'dlc': self._temp_dlc,
            'data': self._temp_complexes.copy()
        })
        self.decode_status = self.STATE_WAITING_DLC_LOW
    
    def run(self) -> None:
        """线程主循环 - 从串口读取数据并进行解码"""
        if not self._serial:
            print("错误：串口未初始化")
            return
        
        print(f"开始从 {self._serial.port} 读取数据...")
        
        try:
            while True:
                if self._serial.in_waiting > 0:
                    byte_data = self._serial.read(1)
                    if byte_data:
                        self.decode(byte_data[0])
        except KeyboardInterrupt:
            print("\n停止接收数据")
        finally:
            self._close_serial()
    
    def _close_serial(self) -> None:
        """关闭串口连接"""
        if self._serial and self._serial.is_open:
            self._serial.close()
            print("串口已关闭")
    
    def get_data(self, bin_id: Optional[int] = None) -> Optional[List[List[complex]] | List[complex]]:
        """
        获取存储的数据
        
        Args:
            bin_id: bin序号，如果为None则返回所有bin的数据
            
        Returns:
            指定bin的数据列表或所有bin的数据
        """
        if bin_id is None:
            return self._data
        if 0 <= bin_id < self._bin_num:
            return self._data[bin_id]
        return None

    def __repr__(self) -> str:
        """返回对象的字符串表示"""
        return (
            f"MMWRaderThread("
            f"bin_num={self._bin_num}, "
            f"dlc={self._dlc}, "
            f"serial={self._serial.port if self._serial else 'None'}, "
            f"data_available={any(self._data)})"
        )


if __name__ == "__main__":
    # 示例用法
    radar = MMWRaderThread(serial_port="COM7")
    print(radar)
    # radar.start()  # 取消注释以启动数据采集
