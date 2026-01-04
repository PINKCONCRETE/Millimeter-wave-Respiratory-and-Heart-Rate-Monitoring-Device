"""
IPC Client Module (Named Pipe)
Handles communication with Electron Frontend via Named Pipe.
"""
import time
import json
import os
import sys

from src.config import PIPE_NAME

class IPCClient:
    def __init__(self, pipe_name=PIPE_NAME):
        self.pipe_name = pipe_name
        self.pipe = None
        self.connected = False

    def connect(self):
        """Try to connect to the named pipe."""
        try:
            self.pipe = open(self.pipe_name, 'wb', buffering=0)
            self.connected = True
            print(f"[IPC] Connected to {self.pipe_name}")
            return True
        except FileNotFoundError:
            # print(f"[IPC] Pipe {self.pipe_name} not found (Electron not running?)")
            return False
        except Exception as e:
            print(f"[IPC] Connection error: {e}")
            return False

    def send(self, data: dict):
        """Send a dictionary as a JSON line."""
        if not self.connected:
            if not self.connect():
                return

        try:
            json_str = json.dumps(data) + '\n'
            self.pipe.write(json_str.encode('utf-8'))
            self.pipe.flush()
        except (OSError, BrokenPipeError):
            print("[IPC] Pipe broken, disconnecting...")
            self.connected = False
            self.close()
        except Exception as e:
            print(f"[IPC] Send error: {e}")

    def close(self):
        if self.pipe:
            try:
                self.pipe.close()
            except:
                pass
        self.pipe = None
        self.connected = False

# Global instance for easy access if needed, but preferred to instantiate in Main Process
ipc_client = IPCClient()
