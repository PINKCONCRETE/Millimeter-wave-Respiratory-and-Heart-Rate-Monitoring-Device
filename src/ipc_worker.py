import multiprocessing
import queue
import time
from src.ipc_client import IPCClient

class IPCWorkerProcess(multiprocessing.Process):
    """
    Process that collects data from various queues and sends it to the Electron frontend via IPC.
    """
    def __init__(self, queues: dict):
        """
        Args:
            queues: Dictionary mapping data types to multiprocessing.Queue instances.
                   e.g., {'breath': breath_queue, 'heart': heart_queue}
        """
        super().__init__(name="IPCWorkerProcess")
        self.queues = queues
        self.daemon = True
        self.running = True
        self.ipc = IPCClient()

    def run(self):
        print("IPC Worker Process started...")
        while self.running:
            # Try to connect if not connected
            if not self.ipc.connected:
                if not self.ipc.connect():
                    time.sleep(1) # Wait before retrying
                    continue

            # Check each queue for data
            data_sent = False
            for data_type, q in self.queues.items():
                try:
                    # Non-blocking get
                    while True:
                        data = q.get_nowait()
                        # Enforce type field if missing, or wrap it
                        if isinstance(data, dict):
                            if 'type' not in data:
                                data['type'] = data_type
                            
                            # Send via IPC
                            self.ipc.send(data)
                            data_sent = True
                        
                        # Limit throughput per loop to avoid starving other queues?
                        # For now, drain the queue or process a few items
                except queue.Empty:
                    pass
                except Exception as e:
                    print(f"Error processing queue {data_type}: {e}")

            # Avoid tight loop if no data
            if not data_sent:
                time.sleep(0.01) 

    def stop(self):
        self.running = False
        self.ipc.close()
