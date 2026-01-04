"""
Main Process Module
Orchestrates the multiprocess pipeline for Millimeter Wave Monitoring.
"""
import multiprocessing
import time
import sys
import os
import signal
from queue import Empty

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.mmw_rader import MMWRadarProcess
from src.mmw_scg import MMWSCGProcess
from src.ipc_client import ipc_client

# Placeholder for other modules if they are not yet converted to Process
# from src.mmw_breath import MMWBreathProcess
# from src.mmw_heart_rate import MMWHeartRateProcess
# from src.mmw_human_check import MMWHumanCheckProcess

def broadcaster_task(input_queue, output_queues):
    """
    Reads from input_queue and distributes to all output_queues.
    Runs as a separate process.
    """
    print(f"Broadcaster Process started (PID: {os.getpid()})")
    while True:
        try:
            data = input_queue.get(timeout=1.0)
            for q in output_queues:
                try:
                    q.put(data) # Blocks if full? default is block=True
                except Exception as e:
                    print(f"Broadcaster put error: {e}")
        except Empty:
            continue
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Broadcaster error: {e}")
            break

def data_collector_task(result_queues, ipc_pipe_name):
    """
    Collects results from all processing processes and sends to IPC.
    """
    print(f"Collector Process started (PID: {os.getpid()})")
    
    # Initialize IPC Client in this process
    from src.ipc_client import IPCClient
    client = IPCClient(ipc_pipe_name)
    
    while True:
        try:
            # Check each result queue
            for q in result_queues:
                try:
                    while not q.empty():
                        result = q.get_nowait()
                        # Send to IPC
                        # print(f"Sending: {result}")
                        client.send(result)
                except Empty:
                    pass
            
            time.sleep(0.01) # Yield
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Collector error: {e}")
            time.sleep(1)

def main():
    # Fix for Windows multiprocessing
    multiprocessing.freeze_support()
    
    print("=== Millimeter Wave Monitoring System (Multiprocess) ===")
    
    # 1. Create Queues
    radar_data_queue = multiprocessing.Queue(maxsize=100)
    
    # Queues for processors
    scg_input_queue = multiprocessing.Queue(maxsize=100)
    # breath_input_queue = multiprocessing.Queue(maxsize=100)
    # heart_input_queue = multiprocessing.Queue(maxsize=100)
    # human_input_queue = multiprocessing.Queue(maxsize=100)
    
    # Result Queue (Multiplexed or separate)
    # For simplicity, let's use one result queue or list of queues
    # Here each processor has its own output queue
    scg_output_queue = multiprocessing.Queue(maxsize=100)
    
    # 2. Start Processes
    
    # Radar
    radar_process = MMWRadarProcess(
        output_queue=radar_data_queue,
        serial_port="COM7" # Make configurable?
    )
    
    # Broadcaster
    # Currently only broadcasting to SCG. Add others to list when ready.
    broadcaster_process = multiprocessing.Process(
        target=broadcaster_task,
        args=(radar_data_queue, [scg_input_queue])
    )
    
    # SCG Processor
    scg_process = MMWSCGProcess(
        input_queue=scg_input_queue,
        output_queue=scg_output_queue
    )
    
    # Collector & IPC
    # We run collector as a process to decouple from Main
    collector_process = multiprocessing.Process(
        target=data_collector_task,
        args=([scg_output_queue], r'\\.\pipe\kalman_ipc')
    )
    
    processes = [
        radar_process,
        broadcaster_process,
        scg_process,
        collector_process
    ]
    
    for p in processes:
        p.start()
        
    print("All processes started.")
    
    try:
        while True:
            time.sleep(1)
            # Monitor processes?
            for p in processes:
                if not p.is_alive():
                    print(f"Process {p} died!")
                    # Handle restart or exit
                    
    except KeyboardInterrupt:
        print("\nStopping system...")
    finally:
        for p in processes:
            if p.is_alive():
                p.terminate()
                p.join()
        print("System stopped.")

if __name__ == '__main__':
    main()
