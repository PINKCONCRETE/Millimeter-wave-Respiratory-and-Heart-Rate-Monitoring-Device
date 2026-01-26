import multiprocessing
import serial
import struct
import time
import queue
from typing import Any, List, Optional, Dict

# Protocol Constants
HIF_PHY_MSG_MAGIC = 0xA5
HIF_SENSOR_RANGE_SPEC_ID = 0xC6

class RadarParser:
    def __init__(self):
        self.buffer = bytearray()
        
    def parse_chunk(self, chunk: bytes) -> List[Dict[str, Any]]:
        self.buffer.extend(chunk)
        packets = []
        
        while len(self.buffer) >= 6: # Min header size
            # Search for Magic
            try:
                magic_idx = self.buffer.index(HIF_PHY_MSG_MAGIC)
                if magic_idx > 0:
                    del self.buffer[:magic_idx]
            except ValueError:
                # No magic found, clear buffer except last few bytes
                del self.buffer[:]
                return packets
                
            if len(self.buffer) < 6:
                break
                
            # Parse Header
            # PHY (2) + MSG (4)
            # PHY: [Magic, Checksum]
            # MSG: [Flag, ID, Length(12)|Seq(4)]
            
            # flag = self.buffer[2]
            msg_id = self.buffer[3]
            len_seq = struct.unpack('<H', self.buffer[4:6])[0]
            length = len_seq & 0xFFF
            
            # Checksum bit check (flag & 0x04)
            # We need to know if checksum is present to calculate packet length
            flag = self.buffer[2]
            packet_len = 6 + length
            if flag & 0x04: # Checksum bit
                packet_len += 4
                
            if len(self.buffer) < packet_len:
                break # Wait for more data
                
            # Extract Packet
            # packet_data = self.buffer[:packet_len]
            # Payload starts at offset 6
            payload = self.buffer[6:6+length]
            
            if msg_id == HIF_SENSOR_RANGE_SPEC_ID:
                data = self.parse_range_spec(payload)
                if data:
                    packets.append(data)
            
            # Remove from buffer
            del self.buffer[:packet_len]
            
        return packets

    def parse_range_spec(self, payload: bytes) -> Optional[Dict[str, Any]]:
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
                # name_len = null_idx - name_start
                name = payload[name_start:null_idx].decode('utf-8', errors='ignore')
                data_start = null_idx + 1
            except ValueError:
                return None
                
            # Parse Data
            # Data is int16 sequence
            expected_data_len = dim_num * 2
            if len(payload) < data_start + expected_data_len:
                return None
                
            values = []
            for i in range(dim_num):
                offset = data_start + i * 2
                val = struct.unpack_from('<h', payload, offset)[0]
                
                # Fixed point Q6
                # fixed_point = (bitfield >> 3) & 0x1F
                # bitfield structure: width:2, sign:1, fixed:5, align:1...
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

class MMWRadar24GProcess(multiprocessing.Process):
    """24G Millimeter Wave Radar Data Acquisition Process.
    
    Adapts the 24G radar's Micro Spectrum output (HIF protocol) to the 
    pipeline's expected format (8 channels x 10 bins).
    """
    
    def __init__(
        self,
        output_queue: multiprocessing.Queue,
        serial_port: str,
        serial_baudrate: int,
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
        self._parser = RadarParser()
        
        # Statistics
        self._received_frames = 0
        self._last_received_frames = 0
        self._last_fps_time = 0.0

    def run(self) -> None:
        print(f"24G Radar Process Started (PID: {self.pid}) on {self._serial_port}...")
        
        try:
            ser = serial.Serial(self._serial_port, self._serial_baudrate, timeout=0.1)
        except Exception as e:
            print(f"Failed to open serial port {self._serial_port}: {e}")
            return

        self._start_time = time.time()
        self._last_fps_time = time.time()
        
        try:
            while self._running:
                try:
                    if ser.in_waiting:
                        chunk = ser.read(ser.in_waiting)
                        packets = self._parser.parse_chunk(chunk)
                        
                        for packet in packets:
                            self._process_packet(packet)
                    else:
                        time.sleep(0.001)
                except Exception as e:
                    print(f"Serial read error: {e}")
                    break
        except KeyboardInterrupt:
            print("Radar process interrupted")
        finally:
            if ser.is_open:
                ser.close()
            print("Radar process stopped")

    def _process_packet(self, packet: Dict[str, Any]) -> None:
        """Process a parsed packet and push to queue in the expected format."""
        raw_values = packet['values']
        
        # 1. Crop/Pad to bins_per_channel
        if len(raw_values) >= self._bins_per_channel:
            cropped_values = raw_values[:self._bins_per_channel]
        else:
            # Pad with zeros
            cropped_values = raw_values + [0.0] * (self._bins_per_channel - len(raw_values))
            
        # 2. Convert to Complex (Real part = value, Imag = 0)
        complex_data = [complex(v, 0.0) for v in cropped_values]
        
        # 3. Replicate for all channels (0 to channel_num - 1)
        # The pipeline expects data for each channel sequentially to build a frame.
        for ch_id in range(self._channel_num):
            try:
                self._output_queue.put({
                    "channel_id": ch_id,
                    "bins_count": self._bins_per_channel,
                    "offset": 0,
                    "data": complex_data[:] # Send a copy
                })
            except queue.Full:
                pass # Skip if queue is full
                
        # Update stats
        self._received_frames += 1
        now = time.time()
        if now - self._last_fps_time >= 1.0:
            fps = (self._received_frames - self._last_received_frames) / (now - self._last_fps_time)
            # print(f"[Radar24G] FPS: {fps:.1f}")
            self._last_received_frames = self._received_frames
            self._last_fps_time = now

    def stop(self) -> None:
        self.terminate()
