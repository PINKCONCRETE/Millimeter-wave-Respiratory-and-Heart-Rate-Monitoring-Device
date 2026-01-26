import serial
import struct
import time
import sys
import threading
import queue
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import re

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
                # No magic found, clear buffer except last few bytes (to handle split magic)
                del self.buffer[:]
                return packets
                
            if len(self.buffer) < 6:
                break
                
            # Parse Header
            # PHY (2) + MSG (4)
            # PHY: [Magic, Checksum]
            # MSG: [Flag, ID, Length(12)|Seq(4)]
            
            flag = self.buffer[2]
            msg_id = self.buffer[3]
            len_seq = struct.unpack('<H', self.buffer[4:6])[0]
            length = len_seq & 0xFFF
            
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
            # dim(1), bitfield(2), dim_num(2)
            if len(payload) < 5:
                return None
                
            dim, bitfield, dim_num = struct.unpack('<BHH', payload[:5])
            
            # Extract Name
            # Find null terminator after header
            name_start = 5
            try:
                null_idx = payload.index(b'\x00', name_start)
                name_len = null_idx - name_start
                name = payload[name_start:null_idx].decode('utf-8', errors='ignore')
                data_start = null_idx + 1
            except ValueError:
                return None
                
            # Parse Data
            # Data is int16 sequence
            # Size check
            expected_data_len = dim_num * 2
            if len(payload) < data_start + expected_data_len:
                return None
                
            values = []
            for i in range(dim_num):
                offset = data_start + i * 2
                val = struct.unpack_from('<h', payload, offset)[0]
                # Fixed point Q6?
                # fiexed_point is 5 bits in bitfield
                # bitfield structure: width:2, sign:1, fixed:5, align:1...
                # 0x35 = 0011 0101
                # bits 0-1: 01 (width=1)
                # bit 2: 1 (sign=1)
                # bits 3-7: 00110 (fixed=6)
                
                # Let's extract fixed point from bitfield
                # width = bitfield & 0x3
                # sign = (bitfield >> 2) & 0x1
                fixed_point = (bitfield >> 3) & 0x1F
                
                real_val = val / (2 ** fixed_point) if fixed_point > 0 else val
                values.append(real_val)
                
            return {
                'name': name,
                'values': values
            }
            
        except Exception as e:
            print(f"Parse error: {e}")
            return None

# --- Visualization ---
data_queue = queue.Queue()
running = True

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
                time.sleep(0.01)
        except Exception as e:
            print(f"Serial error: {e}")
            break
            
    ser.close()

def update_plot(frame, lines, ax):
    try:
        # Process all available data
        latest_data = None
        while not data_queue.empty():
            latest_data = data_queue.get_nowait()
            
        if latest_data:
            values = latest_data['values']
            name = latest_data['name']
            
            # Update title/legend
            ax.set_title(f"Radar Spectrum: {name}")
            
            # Update line
            x = range(len(values))
            lines.set_data(x, values)
            
            # Auto-scale y axis if needed
            ax.relim()
            ax.autoscale_view()
            
    except Exception as e:
        pass
    return lines,

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', default='COM3', help='Serial port')
    parser.add_argument('--mock', action='store_true', help='Use mock data')
    args = parser.parse_args()
    
    # Setup Plot
    fig, ax = plt.subplots()
    lines, = ax.plot([], [], 'b-', marker='o', markersize=3)
    ax.set_xlim(0, 40)
    ax.set_ylim(-100, 100) # Initial guess
    ax.grid(True)
    ax.set_xlabel('Bin Index')
    ax.set_ylabel('Amplitude (Q6)')
    
    if args.mock:
        print("Using Mock Data based on user hex dump...")
        # Mock thread
        def mock_feeder():
            # Example payload from user
            hex_str = "01 35 00 28 00 6D 69 63 6F 5F 73 70 65 63 74 72 75 6D 00 CD 04 6D 06 69 06 32 06 BF 05 FF 04 E7 03 7F 02 4C 01 13 01 24 01 7F 01 19 02 94 02 B8 02 82 02 1A 02 9B 01 36 01 F6 00 ED 00 30 01 5C 01 6F 01 7D 01 79 01 4F 01 32 01 2C 01 F8 00 D1 00 B5 00 DB 00 CE 00 C2 00 B2 00 A0 00 A6 00 AD 00 A6 00"
            payload = bytes.fromhex(hex_str)
            parser = RadarParser()
            while running:
                data = parser.parse_range_spec(payload)
                if data:
                    data_queue.put(data)
                time.sleep(0.1)
        
        t = threading.Thread(target=mock_feeder)
        t.daemon = True
        t.start()
        
    else:
        # Serial Thread
        t = threading.Thread(target=serial_reader, args=(args.port,))
        t.daemon = True
        t.start()
    
    ani = FuncAnimation(fig, update_plot, fargs=(lines, ax), interval=50, blit=False)
    plt.show()
    
    global running
    running = False
    t.join()

if __name__ == '__main__':
    main()
