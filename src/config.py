"""
Configuration Constants for the Millimeter Wave Monitoring System.
"""
import os

# Serial Port Configuration
# Default serial port for the millimeter wave radar
SERIAL_PORT = os.getenv('MMW_SERIAL_PORT', 'COM7')
SERIAL_BAUDRATE = int(os.getenv('MMW_SERIAL_BAUDRATE', 921600))

# IPC Configuration (Named Pipe for Electron)
# This name must match the one used in the Electron main process
PIPE_NAME = os.getenv('MMW_PIPE_NAME', r'\\.\pipe\mmw_monitor_pipe')

# Database Configuration
DATABASE_FILENAME = 'mmw_monitor.db'

# Signal Processing Constants
SAMPLING_RATE = 200  # Hz
CHANNEL_NUM = 8
BINS_PER_CHANNEL = 10

# Flask Server Configuration
FLASK_HOST = '0.0.0.0'
FLASK_PORT = 5000
