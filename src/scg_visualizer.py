import serial
import struct
import time
import sys
import threading
import queue
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from collections import deque
import numpy as np

# Protocol Constants
HIF_PHY_MSG_MAGIC = 0xA5
HIF_SENSOR_RANGE_SPEC_ID = 0xC6

# SCG Parameters
SCG_PARAMS = {
    'TIME_STEP': 0.05, # Estimate, will be updated by measured FPS
    'DIFFERENTIAL_WEIGHT': 16.0
}

class RadarParser:
    def __init__(self):
        self.buffer = bytearray()
        
    def parse_chunk(self, chunk):
        self.buffer.extend(chunk)
        packets = []
        
        while len(self.buffer) >= 6: # Min header size
            # Search for Magic
            try:
                magic_idx = self.buffer.index(HIF_PHY_MSG_MAGIC)
                if magic_idx > 0:
                    del self.buffer[:magic_idx]
            except ValueError:
                del self.buffer[:]
                return packets
                
            if len(self.buffer) < 6:
                break
                
            msg_id = self.buffer[3]
            len_seq = struct.unpack('<H', self.buffer[4:6])[0]
            length = len_seq & 0xFFF
            
            flag = self.buffer[2]
            packet_len = 6 + length
            if flag & 0x04: # Checksum bit
                packet_len += 4
                
            if len(self.buffer) < packet_len:
                break # Wait for more data
                
            # Extract Packet
            packet_data = self.buffer[:packet_len]
            payload = packet_data[6:6+length]
            
            if msg_id == HIF_SENSOR_RANGE_SPEC_ID:
                data = self.parse_range_spec(payload)
                if data:
                    packets.append(data)
            
            # Remove from buffer
            del self.buffer[:packet_len]
            
        return packets

    def parse_range_spec(self, payload):
        try:
            # Header (5 bytes)
            if len(payload) < 5:
                return None
                
            dim, bitfield, dim_num = struct.unpack('<BHH', payload[:5])
            
            # Extract Name
            name_start = 5
            try:
                null_idx = payload.index(b'\x00', name_start)
                data_start = null_idx + 1
            except ValueError:
                return None
                
            # Parse Data
            expected_data_len = dim_num * 2
            if len(payload) < data_start + expected_data_len:
                return None
                
            values = []
            for i in range(dim_num):
                offset = data_start + i * 2
                val = struct.unpack_from('<h', payload, offset)[0]
                fixed_point = (bitfield >> 3) & 0x1F
                real_val = val / (2 ** fixed_point) if fixed_point > 0 else val
                values.append(real_val)
                
            return {
                'values': values
            }
            
        except Exception as e:
            print(f"Parse error: {e}")
            return None

def compute_derivative_waveform(data: np.ndarray, h=0.005) -> np.ndarray:
    """
    计算整个波形的7点加权二阶导数.
    参考 src/mmw_scg_grade.py
    """
    n = data.shape[0]
    h_squared = h ** 2

    # 初始化结果数组为0
    result = np.zeros_like(data)

    # 计算可以应用7点公式的范围（排除边界3个点）
    length = n - 6
    
    if length <= 0:
        return result

    # 使用向量化计算中间部分的二阶导数
    # 中心点从索引3到n-4
    # 公式: f''(x) ≈ [4f(x) + f(x+1) + f(x-1) - 2f(x+2) - 2f(x-2) - f(x+3) - f(x-3)] / (16h²)
    result[3:length+3] = (
        data[3:length+3] * 4.0 +
        (data[4:length+4] + data[2:length+2]) -
        2.0 * (data[5:length+5] + data[1:length+1]) -
        (data[6:length+6] + data[:length])
    ) / (SCG_PARAMS['DIFFERENTIAL_WEIGHT'] * h_squared)

    return result

# --- Visualization ---
data_queue = queue.Queue()
running = True

# Buffers
MAX_WINDOW_SEC = 5.0
time_buffer = deque()
value_buffer = deque()
start_time = time.time()

# Stats
fps_counter = 0
last_fps_time = time.time()
current_fps = 20.0 # Default guess

def serial_reader(port):
    global running
    try:
        ser = serial.Serial(port, 921600, timeout=0.1)
        print(f"Connected to {port}")
    except Exception as e:
        print(f"Failed to open {port}: {e}")
        running = False
        return

    parser = RadarParser()
    
    while running:
        try:
            if ser.in_waiting:
                chunk = ser.read(ser.in_waiting)
                packets = parser.parse_chunk(chunk)
                for p in packets:
                    data_queue.put(p)
            else:
                time.sleep(0.001)
        except Exception as e:
            print(f"Serial error: {e}")
            break
            
    ser.close()

def update_plot(frame, lines, ax, info_text):
    global fps_counter, last_fps_time, current_fps
    
    try:
        # 1. Ingest Data
        has_new_data = False
        while not data_queue.empty():
            latest_data = data_queue.get_nowait()
            values = latest_data['values']
            
            if len(values) > 0:
                val_bin0 = values[0]
                current_time = time.time() - start_time
                time_buffer.append(current_time)
                value_buffer.append(val_bin0)
                has_new_data = True
                
                # FPS Stats
                fps_counter += 1
                if current_time - (last_fps_time - start_time) >= 1.0:
                    current_fps = fps_counter
                    fps_counter = 0
                    last_fps_time = time.time()
        
        # 2. Prune Buffer (Keep 5s)
        if len(time_buffer) > 0:
            latest_time = time_buffer[-1]
            while len(time_buffer) > 0 and (latest_time - time_buffer[0] > MAX_WINDOW_SEC):
                time_buffer.popleft()
                value_buffer.popleft()
        
        # 3. Compute & Plot
        if len(value_buffer) > 10:
            # Convert to numpy for processing
            raw_data = np.array(value_buffer)
            
            # Apply 7-point 2nd derivative
            # Update h based on measured FPS to keep magnitude reasonable
            h = 1.0 / current_fps if current_fps > 0 else 0.05
            deriv_data = compute_derivative_waveform(raw_data, h=h)
            
            # The derivative has 0s at edges (3 points). 
            # We plot the whole thing to show the window.
            
            lines.set_data(list(time_buffer), deriv_data)
            
            # Update Info
            info_text.set_text(f"FPS: {current_fps:.1f} | Window: {MAX_WINDOW_SEC}s | h: {h:.4f}s")
            
            # Auto-scale
            ax.set_xlim(min(time_buffer), max(time_buffer) + 0.1)
            
            # Ignore the zero edges for y-scaling
            valid_data = deriv_data[3:-3] if len(deriv_data) > 6 else deriv_data
            if len(valid_data) > 0:
                y_min, y_max = np.min(valid_data), np.max(valid_data)
                margin = (y_max - y_min) * 0.1 if y_max != y_min else 1.0
                ax.set_ylim(y_min - margin, y_max + margin)
            
    except Exception as e:
        print(f"Plot Error: {e}")
        pass
    return lines, info_text

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', default='COM3', help='Serial port')
    args = parser.parse_args()
    
    # Setup Plot
    fig, ax = plt.subplots(figsize=(10, 6))
    lines, = ax.plot([], [], 'r-', linewidth=1.5, label='7-point 2nd Deriv')
    info_text = ax.text(0.02, 0.95, '', transform=ax.transAxes)
    
    ax.set_title("Real-time SCG (2nd Derivative of Bin 0 Amplitude)")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Amplitude (d2/dt2)")
    ax.grid(True)
    ax.legend(loc='upper right')
    
    # Start Serial Thread
    t = threading.Thread(target=serial_reader, args=(args.port,), daemon=True)
    t.start()
    
    # Start Animation
    ani = FuncAnimation(fig, update_plot, fargs=(lines, ax, info_text), interval=30, blit=False, cache_frame_data=False)
    
    plt.show()
    
    global running
    running = False
    t.join(timeout=1.0)

if __name__ == '__main__':
    main()
