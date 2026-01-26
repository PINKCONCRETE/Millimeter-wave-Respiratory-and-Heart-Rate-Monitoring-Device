import serial
import struct
import time
import sys
import threading
import queue
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from collections import deque

# Protocol Constants
HIF_PHY_MSG_MAGIC = 0xA5
HIF_SENSOR_RANGE_SPEC_ID = 0xC6

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

# --- Visualization ---
data_queue = queue.Queue()
running = True

# Buffer for plotting
MAX_POINTS = 500
time_buffer = deque(maxlen=MAX_POINTS)
value_buffer = deque(maxlen=MAX_POINTS)
start_time = time.time()

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
                time.sleep(0.005)
        except Exception as e:
            print(f"Serial error: {e}")
            break
            
    ser.close()

def update_plot(frame, lines, ax):
    try:
        # Process all available data
        while not data_queue.empty():
            latest_data = data_queue.get_nowait()
            values = latest_data['values']
            
            # Extract Bin 0 (first bin)
            if len(values) > 0:
                val_bin0 = values[0]
                
                # Update buffers
                current_time = time.time() - start_time
                time_buffer.append(current_time)
                value_buffer.append(val_bin0)
            
        # Update line
        if len(time_buffer) > 0:
            lines.set_data(list(time_buffer), list(value_buffer))
            
            # Auto-scale axes
            ax.set_xlim(min(time_buffer), max(time_buffer) + 0.1)
            
            y_min, y_max = min(value_buffer), max(value_buffer)
            margin = (y_max - y_min) * 0.1 if y_max != y_min else 1.0
            ax.set_ylim(y_min - margin, y_max + margin)
            
    except Exception as e:
        pass
    return lines,

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', default='COM3', help='Serial port')
    args = parser.parse_args()
    
    # Setup Plot
    fig, ax = plt.subplots(figsize=(10, 6))
    lines, = ax.plot([], [], 'g-', linewidth=1.5)
    
    ax.set_title("Radar Bin 0 Amplitude over Time")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Amplitude")
    ax.grid(True)
    
    # Start Serial Thread
    t = threading.Thread(target=serial_reader, args=(args.port,), daemon=True)
    t.start()
    
    # Start Animation
    # cache_frame_data=False to suppress warning
    ani = FuncAnimation(fig, update_plot, fargs=(lines, ax), interval=30, blit=False, cache_frame_data=False)
    
    plt.show()
    
    global running
    running = False
    t.join(timeout=1.0)

if __name__ == '__main__':
    main()
