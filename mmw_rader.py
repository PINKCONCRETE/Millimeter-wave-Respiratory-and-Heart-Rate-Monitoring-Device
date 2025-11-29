# pylint: disable=too-many-arguments
"""
Module for MMWRader class
"""
import threading
import queue
import struct
import serial


class MMWRaderThread(threading.Thread):

    """
    毫米波雷达管理类
    用于串口连接毫米波雷达后接收、解码、存储并管理毫米波雷达数据
    functions:
    Attributes:
    """
    def __init__(self,
                output_queue: queue.Queue = queue.Queue(),
                serial_port : str = "COM7",
                serial_baudrate : int = 921600,
                bin_num : int = 8,
                dlc : int = 10,
                ) -> None:
        threading.Thread.__init__(self)
        if(serial_port != "" and serial_baudrate != 0):
            self.__serial = serial.Serial(serial_port, serial_baudrate)
        else:
            self.__serial = None
        self.__bin_num = bin_num
        self.__data = [[] for _ in range(bin_num)]
        self.__dlc = dlc
        self.__output_queue = output_queue
        
        # 状态机状态
        self.decode_status = 0  # 0-3: SOF states (S0-S3), 4-7: DATA states (D0-D3)
        
        # 临时缓存变量
        self.__temp_dlc = 0  # 当前帧的数据长度
        self.__temp_bin_id = 0  # 当前帧的 bin 序号
        self.__temp_real = 0  # 当前复数的实部
        self.__temp_imag = 0  # 当前复数的虚部
        self.__complex_count = 0  # 当前帧已接收的复数个数
        self.__temp_complexes = []  # 当前帧的复数列表
    
    def decode(self, byte_data: int) -> None:
        """
        解码部分 - 根据状态机处理每个字节
        状态机：
        S0: 等待 dlc_low_byte
        S1: 等待 dlc_high_byte
        S2: 等待 bin_id_low_byte
        S3: 等待 bin_id_high_byte
        D0: 获取实部低字节
        D1: 获取实部高字节
        D2: 获取虚部低字节
        D3: 获取虚部高字节并输出复数
        """
        if self.decode_status == 0:  # S0: WAITING_DLC_LOW_BYTE
            self.__temp_dlc = byte_data
            self.decode_status = 1
            
        elif self.decode_status == 1:  # S1: WAITING_DLC_HIGH_BYTE
            self.__temp_dlc |= (byte_data << 8)
            # 验证 dlc 是否与预期一致
            if self.__temp_dlc == self.__dlc:
                self.decode_status = 2
            else:
                # 数据长度不匹配，回到初始状态
                self.decode_status = 0
            
        elif self.decode_status == 2:  # S2: WAITING_BIN_ID_LOW_BYTE
            self.__temp_bin_id = byte_data
            self.decode_status = 3
            
        elif self.decode_status == 3:  # S3: WAITING_BIN_ID_HIGH_BYTE
            self.__temp_bin_id |= (byte_data << 8)
            # 验证 bin_id 是否在有效范围内
            if self.__temp_bin_id < self.__bin_num:
                # 初始化 DATA 阶段，i = 0
                self.__complex_count = 0
                self.__temp_complexes = []
                self.decode_status = 4  # 进入 D0 状态
            else:
                # bin_id 超出范围，回到初始状态
                self.decode_status = 0
            
        elif self.decode_status == 4:  # D0: GET_REAL_LOW_BYTE
            self.__temp_real = byte_data
            self.decode_status = 5
            
        elif self.decode_status == 5:  # D1: GET_REAL_HIGH_BYTE
            self.__temp_real |= (byte_data << 8)
            # 转换为有符号 16 位整数
            self.__temp_real = struct.unpack('<h', struct.pack('<H', self.__temp_real))[0]
            self.decode_status = 6
            
        elif self.decode_status == 6:  # D2: GET_IMAGINARY_LOW_BYTE
            self.__temp_imag = byte_data
            self.decode_status = 7
            
        elif self.decode_status == 7:  # D3: GET_IMAGINARY_HIGH_BYTE
            self.__temp_imag |= (byte_data << 8)
            # 转换为有符号 16 位整数
            self.__temp_imag = struct.unpack('<h', struct.pack('<H', self.__temp_imag))[0]
            
            # 输出复数
            complex_num = complex(self.__temp_real, self.__temp_imag)
            self.__temp_complexes.append(complex_num)
            self.__complex_count += 1
            
            # 判断是否接收完所有复数 (i < dlc)
            if self.__complex_count < self.__temp_dlc:
                self.decode_status = 4  # 继续接收下一个复数 (i = i + 1)
            else:
                # 一帧数据接收完成 (i >= dlc)
                # 存储数据
                self.__data[self.__temp_bin_id] = self.__temp_complexes.copy()
                # 将结果放入输出队列
                self.__output_queue.put({
                    'bin_id': self.__temp_bin_id,
                    'dlc': self.__temp_dlc,
                    'data': self.__temp_complexes.copy()
                })
                # 回到初始状态等待下一帧
                self.decode_status = 0
    
    def run(self) -> None:
        """
        运行部分 - 线程主循环
        从串口读取数据并进行解码
        """
        if self.__serial is None:
            print("错误：串口未初始化")
            return
        
        print(f"开始从 {self.__serial.port} 读取数据...")
        
        try:
            while True:
                if self.__serial.in_waiting > 0:
                    byte_data = self.__serial.read(1)
                    if byte_data:
                        self.decode(byte_data[0])
        except KeyboardInterrupt:
            print("\n停止接收数据")
        except Exception as e:
            print(f"错误: {e}")
        finally:
            if self.__serial and self.__serial.is_open:
                self.__serial.close()
                print("串口已关闭")
    
    def get_data(self, bin_id: int | None = None):
        """
        获取存储的数据
        Args:
            bin_id: bin 序号，如果为 None 则返回所有 bin 的数据
        Returns:
            指定 bin 的数据列表或所有 bin 的数据
        """
        if bin_id is None:
            return self.__data
        if 0 <= bin_id < self.__bin_num:
            return self.__data[bin_id]
        return None

    def __repr__(self) -> str:
        return "MMWRaderHandler(" + \
            f"bin_num={self.__bin_num}," + \
            f"data={self.__data}," + \
            f"dlc={self.__dlc}," + \
            f"serial={self.__serial}" + \
            f"output_queue={self.__output_queue}" + \
        ")"
if __name__ == "__main__":
    radar = MMWRaderThread(serial_port="COM4")
    print(radar)
