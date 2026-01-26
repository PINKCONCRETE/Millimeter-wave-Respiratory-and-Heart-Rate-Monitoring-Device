"""
Configuration Constants for the Millimeter Wave Monitoring System.
"""
import os
import platform

# Serial Port Configuration
if platform.system() == 'Windows':
    # Default serial port for the millimeter wave radar
    SERIAL_PORT = os.getenv('MMW_SERIAL_PORT', 'COM3')
    # IPC Configuration (Named Pipe for Electron)
    PIPE_NAME = os.getenv('MMW_PIPE_NAME', r'\\.\pipe\mmw_monitor_pipe')
else:
    # Linux/Mac defaults
    SERIAL_PORT = os.getenv('MMW_SERIAL_PORT', '/dev/ttyACM1')
    # Unix Domain Socket for IPC
    PIPE_NAME = os.getenv('MMW_PIPE_NAME', '/tmp/mmw_monitor.sock')

SERIAL_BAUDRATE = int(os.getenv('MMW_SERIAL_BAUDRATE', 921600))

# Database Configuration
DATABASE_FILENAME = 'mmw_monitor.db'

# Signal Processing Constants
SAMPLING_RATE = 200  # Hz
CHANNEL_NUM = 8
BINS_PER_CHANNEL = 10

# Flask Server Configuration
FLASK_HOST = '0.0.0.0'
FLASK_PORT = 5000
