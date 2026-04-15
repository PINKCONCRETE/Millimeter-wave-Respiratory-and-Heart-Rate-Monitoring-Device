import serial
import struct
import time
import sys
import threading
import queue
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from collections import deque
from scipy import signal

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
                
            # Parse Data (assuming complex I/Q data: 2 values per bin)
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
phase_buffer = deque(maxlen=MAX_POINTS)
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

def update_plot(frame, lines, ax, lines2, ax2):
    try:
        # Process all available data
        while not data_queue.empty():
            latest_data = data_queue.get_nowait()
            values = latest_data['values']
            
            # Extract Bin 0 I/Q components
            # Assuming values are arranged as [I0, Q0, I1, Q1, I2, Q2, ...]
            # or [bin0_val, bin1_val, ...] if already processed
            
            if len(values) >= 2:
                # Method 1: If values are I/Q interleaved (I0, Q0, I1, Q1, ...)
                I_bin0 = values[0]
                Q_bin0 = values[1]
                
                # Calculate complex number
                complex_val = I_bin0 + 1j * Q_bin0
                
                # Calculate phase
                phase = np.angle(complex_val)
                
                # Update buffers
                current_time = time.time() - start_time
                time_buffer.append(current_time)
                phase_buffer.append(phase)
            elif len(values) >= 1:
                # Method 2: If only one value per bin (magnitude only)
                # We can't compute phase from magnitude alone
                # This is a fallback - phase will be 0
                print("Warning: Only single value detected, cannot compute phase from magnitude alone")
                current_time = time.time() - start_time
                time_buffer.append(current_time)
                phase_buffer.append(0)
            
        # Update line with unwrapped phase and filtered signals
        if len(phase_buffer) > 100:  # Need enough samples for filtering
            # Convert to numpy array and unwrap
            phases_array = np.array(phase_buffer)
            unwrapped_phase = np.unwrap(phases_array)
            time_array = np.array(time_buffer)
            
            # Calculate sampling rate
            if len(time_array) > 1:
                dt = np.mean(np.diff(time_array))
                fs = 1.0 / dt if dt > 0 else 30.0  # Default to 30 Hz
            else:
                fs = 30.0
            
            # Design filters
            # Lowpass filter: 0-0.8 Hz
            nyquist = fs / 2
            lowcut = 0.8 / nyquist
            if lowcut < 1.0:
                b_low, a_low = signal.butter(4, lowcut, btype='low')
                lowpass_signal = signal.filtfilt(b_low, a_low, unwrapped_phase)
            else:
                lowpass_signal = unwrapped_phase
            
            # Bandpass filter: 0.5-5 Hz
            low_freq = 0.5 / nyquist
            high_freq = 5.0 / nyquist
            if low_freq < 1.0 and high_freq < 1.0 and low_freq < high_freq:
                b_band, a_band = signal.butter(4, [low_freq, high_freq], btype='band')
                bandpass_signal = signal.filtfilt(b_band, a_band, unwrapped_phase)
            else:
                bandpass_signal = unwrapped_phase
            
            # Update lowpass plot
            lines.set_data(time_array, lowpass_signal)
            ax.set_xlim(min(time_buffer), max(time_buffer) + 0.1)
            y_min, y_max = np.min(lowpass_signal), np.max(lowpass_signal)
            margin = (y_max - y_min) * 0.1 if y_max != y_min else 1.0
            ax.set_ylim(y_min - margin, y_max + margin)
            
            # Update bandpass plot
            lines2.set_data(time_array, bandpass_signal)
            ax2.set_xlim(min(time_buffer), max(time_buffer) + 0.1)
            y_min2, y_max2 = np.min(bandpass_signal), np.max(bandpass_signal)
            margin2 = (y_max2 - y_min2) * 0.1 if y_max2 != y_min2 else 1.0
            ax2.set_ylim(y_min2 - margin2, y_max2 + margin2)
            
    except Exception as e:
        print(f"Update error: {e}")
    return lines, lines2

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', default='COM3', help='Serial port')
    args = parser.parse_args()
    
    # Setup Plot with 2 subplots
    fig, (ax, ax2) = plt.subplots(2, 1, figsize=(12, 10))
    lines, = ax.plot([], [], 'b-', linewidth=1.5)
    lines2, = ax2.plot([], [], 'r-', linewidth=1.5)
    
    # Lowpass filter plot (0-0.8 Hz)
    ax.set_title("Lowpass Filtered (0-0.8 Hz) - Breathing", fontsize=14, fontweight='bold')
    ax.set_xlabel("Time (s)", fontsize=12)
    ax.set_ylabel("Phase (rad)", fontsize=12)
    ax.grid(True, alpha=0.3)
    
    # Bandpass filter plot (0.5-5 Hz)
    ax2.set_title("Bandpass Filtered (0.5-5 Hz) - Heart Rate", fontsize=14, fontweight='bold')
    ax2.set_xlabel("Time (s)", fontsize=12)
    ax2.set_ylabel("Phase (rad)", fontsize=12)
    ax2.grid(True, alpha=0.3)
    
    # Add text for info
    info_text = ax.text(0.02, 0.98, '', transform=ax.transAxes, 
                       verticalalignment='top', fontsize=10,
                       bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    def update_with_info(frame):
        result = update_plot(frame, lines, ax, lines2, ax2)
        # Update info text
        if len(phase_buffer) > 0:
            current_phase = phase_buffer[-1]
            info_text.set_text(f'Data points: {len(phase_buffer)}\nCurrent phase: {current_phase:.3f} rad')
        return result
    
    # Start Serial Thread
    t = threading.Thread(target=serial_reader, args=(args.port,), daemon=True)
    t.start()
    
    # Start Animation
    ani = FuncAnimation(fig, update_with_info, interval=30, blit=False, cache_frame_data=False)
    
    plt.tight_layout()
    plt.show()
    
    global running
    running = False
    t.join(timeout=1.0)

if __name__ == '__main__':
    main()
