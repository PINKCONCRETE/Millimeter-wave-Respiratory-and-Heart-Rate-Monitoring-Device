"""毫米波监测系统主进程 (多进程版).

将原有的多线程架构重构为多进程架构，以提升性能和隔离性。
"""
import multiprocessing
import signal
import sys
import time
from pathlib import Path
from queue import Empty, Full
from typing import Any

# 添加项目根目录到 sys.path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.mmw_rader import MMWRadarProcess
from src.mmw_scg_grade import SCGGradeProcess
from src.mmw_breath import MMWBreathProcess
from src.mmw_heart_rate import MMWHeartRateProcess
from src.mmw_human_check import MMWHumanCheckProcess
from src.mmw_database import (
    UnifiedDatabaseWriter,
    SCGDatabaseWriter,
    BreathDatabaseWriter,
    HeartRateDatabaseWriter,
    HumanCheckDatabaseWriter,
)
from src.ipc_worker import IPCWorkerProcess
from src.utils import BroadcastingQueue


class RadarBroadcaster(multiprocessing.Process):
    """雷达数据广播进程 - 将数据复制到多个队列(带降采样)."""
    
    def __init__(self, input_queue: multiprocessing.Queue, output_queues: list[multiprocessing.Queue], downsample_ratios: list = None):
        super().__init__()
        self.daemon = True
        self._input = input_queue
        self._outputs = output_queues
        self._downsample_ratios = downsample_ratios or [1] * len(output_queues)
        self._stop_event = multiprocessing.Event()
        self._counters = [0] * len(output_queues)
    
    def run(self):
        """主循环 - 广播数据."""
        print("雷达广播进程已启动...")
        while not self._stop_event.is_set():
            try:
                # 设置超时以便响应停止事件
                data = self._input.get(timeout=1.0)
                
                # 根据降采样比例发送到各个队列
                for i, (q, ratio) in enumerate(zip(self._outputs, self._downsample_ratios)):
                    self._counters[i] += 1
                    if self._counters[i] >= ratio:
                        try:
                            q.put_nowait(data)
                            self._counters[i] = 0
                        except Full:
                            pass  # 队列满则跳过，防止阻塞
                        except Exception:
                            pass
            except Empty:
                continue
            except Exception as e:
                print(f"广播进程异常: {e}")
                
        print("雷达广播进程已停止")
    
    def stop(self):
        """停止广播."""
        self._stop_event.set()


from src.config import SERIAL_PORT, SERIAL_BAUDRATE

class MMWProcessPipeline:
    """毫米波多进程流水线."""
    
    def __init__(self, uid=0, serial_port=SERIAL_PORT, serial_baudrate=SERIAL_BAUDRATE, database_path=None):
        self.uid = uid
        self.serial_port = serial_port
        self.serial_baudrate = serial_baudrate
        self.database_path = database_path
        
        # 创建进程间通信队列
        # 注意：multiprocessing.Queue 是进程安全的
        self.radar_queue = multiprocessing.Queue(maxsize=2000)
        self.radar_queue_scg = multiprocessing.Queue(maxsize=1000)
        self.radar_queue_breath = multiprocessing.Queue(maxsize=1000)
        self.radar_queue_heart = multiprocessing.Queue(maxsize=1000)
        self.radar_queue_human = multiprocessing.Queue(maxsize=1000)
        
        # 结果队列 - 数据库用
        self.scg_queue_db = multiprocessing.Queue(maxsize=500)
        self.breath_queue_db = multiprocessing.Queue(maxsize=500)
        self.heart_rate_queue_db = multiprocessing.Queue(maxsize=500)
        self.human_check_queue_db = multiprocessing.Queue(maxsize=500)
        
        # 结果队列 - IPC用
        self.scg_queue_ipc = multiprocessing.Queue(maxsize=500)
        self.breath_queue_ipc = multiprocessing.Queue(maxsize=500)
        self.heart_rate_queue_ipc = multiprocessing.Queue(maxsize=500)
        self.human_check_queue_ipc = multiprocessing.Queue(maxsize=500)
        
        # 进程实例
        self.radar_process = None
        self.broadcaster = None
        self.scg_process = None
        self.breath_process = None
        self.heart_rate_process = None
        self.human_check_process = None
        self.ipc_process = None
        
        # 数据库线程 (在主进程中运行)
        self.unified_db_writer = None
        self.scg_db_thread = None
        self.breath_db_thread = None
        self.heart_rate_db_thread = None
        self.human_check_db_thread = None
        
        self.running = False
        signal.signal(signal.SIGINT, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        print("\n\n收到停止信号...")
        self.stop()
        sys.exit(0)
    
    def start(self):
        """启动流水线."""
        print("="*50)
        print("Starting MMW Radar Monitoring System")
        print("Backend is running...")
        print("Please ensure the Electron Frontend is running:")
        print("  cd frontend")
        print("  npm run electron:dev")
        print("="*50)
        
        # 1. 启动雷达采集进程
        self.radar_process = MMWRadarProcess(
            self.radar_queue, self.serial_port, self.serial_baudrate
        )
        self.radar_process.start()
        time.sleep(1) # 等待串口初始化
        
        # 2. 启动广播进程
        self.broadcaster = RadarBroadcaster(
            self.radar_queue, 
            [
                self.radar_queue_scg,
                self.radar_queue_breath,
                self.radar_queue_heart,
                self.radar_queue_human
            ],
            downsample_ratios=[1, 1, 1, 1] # 人体检测可适当降采样，这里保持1
        )
        self.broadcaster.start()
        
        # 3. 启动各信号处理进程
        self.scg_process = SCGGradeProcess(
            self.radar_queue_scg, 
            BroadcastingQueue([self.scg_queue_db, self.scg_queue_ipc])
        )
        self.scg_process.start()
        
        self.breath_process = MMWBreathProcess(
            self.radar_queue_breath, 
            BroadcastingQueue([self.breath_queue_db, self.breath_queue_ipc])
        )
        self.breath_process.start()
        
        self.heart_rate_process = MMWHeartRateProcess(
            self.radar_queue_heart, 
            BroadcastingQueue([self.heart_rate_queue_db, self.heart_rate_queue_ipc])
        )
        self.heart_rate_process.start()
        
        self.human_check_process = MMWHumanCheckProcess(
            self.radar_queue_human, 
            BroadcastingQueue([self.human_check_queue_db, self.human_check_queue_ipc])
        )
        self.human_check_process.start()
        
        # 启动IPC发送进程
        ipc_queues = {
            'scg_data': self.scg_queue_ipc,
            'breath_data': self.breath_queue_ipc,
            'heart_rate_data': self.heart_rate_queue_ipc,
            'human_check_data': self.human_check_queue_ipc
        }
        self.ipc_process = IPCWorkerProcess(ipc_queues)
        self.ipc_process.start()
        
        # 4. 启动数据库写入线程 (主进程中)
        self.unified_db_writer = UnifiedDatabaseWriter(self.uid, self.database_path)
        self.unified_db_writer.start()
        
        self.scg_db_thread = SCGDatabaseWriter(
            self.scg_queue_db, self.uid, self.database_path
        )
        self.scg_db_thread.set_unified_writer(self.unified_db_writer)
        self.scg_db_thread.start()
        
        self.breath_db_thread = BreathDatabaseWriter(
            self.breath_queue_db, self.uid, self.database_path
        )
        self.breath_db_thread.set_unified_writer(self.unified_db_writer)
        self.breath_db_thread.start()
        
        self.heart_rate_db_thread = HeartRateDatabaseWriter(
            self.heart_rate_queue_db, self.uid, self.database_path
        )
        self.heart_rate_db_thread.set_unified_writer(self.unified_db_writer)
        self.heart_rate_db_thread.start()
        
        self.human_check_db_thread = HumanCheckDatabaseWriter(
            self.human_check_queue_db, self.uid, self.database_path
        )
        self.human_check_db_thread.set_unified_writer(self.unified_db_writer)
        self.human_check_db_thread.start()
        
        self.running = True
        print("✓ 所有进程和线程已启动\n")
        
        # 打印进程PID信息
        print(f"主进程 PID: {multiprocessing.current_process().pid}")
        if self.radar_process: print(f"雷达进程 PID: {self.radar_process.pid}")
        if self.broadcaster: print(f"广播进程 PID: {self.broadcaster.pid}")
        if self.scg_process: print(f"SCG进程 PID: {self.scg_process.pid}")
        if self.breath_process: print(f"呼吸进程 PID: {self.breath_process.pid}")
        if self.heart_rate_process: print(f"心率进程 PID: {self.heart_rate_process.pid}")
        if self.human_check_process: print(f"人体检测进程 PID: {self.human_check_process.pid}")
        print("-" * 60)
    
    def stop(self):
        """停止流水线."""
        if not self.running:
            return
        print("\n停止所有进程和线程...")
        
        # 1. 停止进程
        processes = [
            ('雷达', self.radar_process),
            ('广播器', self.broadcaster),
            ('SCG', self.scg_process),
            ('呼吸', self.breath_process),
            ('心率', self.heart_rate_process),
            ('人体检测', self.human_check_process),
            ('IPC服务', self.ipc_process),
        ]
        
        for name, proc in processes:
            if proc:
                if hasattr(proc, 'stop'):
                    proc.stop()
                elif hasattr(proc, 'terminate'): # Fallback
                    proc.terminate()
                proc.join(timeout=2)
                if proc.is_alive():
                    print(f"强制终止 {name} 进程...")
                    proc.terminate()
                print(f"✓ {name}进程已停止")
        
        # 2. 停止数据库线程
        threads = [
            ('统一数据库', self.unified_db_writer),
            ('SCG适配器', self.scg_db_thread),
            ('呼吸适配器', self.breath_db_thread),
            ('心率适配器', self.heart_rate_db_thread),
            ('人体适配器', self.human_check_db_thread)
        ]
        
        for name, thread in threads:
            if thread:
                if hasattr(thread, 'stop'):
                    thread.stop()
                thread.join(timeout=3)
                print(f"✓ {name}线程已停止")
        
        self.running = False
    
    def run(self):
        """运行流水线."""
        self.start()
        try:
            while self.running:
                time.sleep(1)
                # 可以在这里添加监控逻辑，例如检查子进程是否存活
                if self.radar_process and not self.radar_process.is_alive():
                    print("警告: 雷达进程已退出")
                    break
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()


def main():
    """主函数."""
    # Windows下使用multiprocessing必须调用
    multiprocessing.freeze_support()
    
    import argparse
    from src.config import SERIAL_PORT, SERIAL_BAUDRATE

    parser = argparse.ArgumentParser(description='毫米波监测系统 (多进程版)')
    parser.add_argument('--uid', type=int, default=0, help='用户ID')
    parser.add_argument('--port', type=str, default=SERIAL_PORT, help='串口号')
    parser.add_argument('--baudrate', type=int, default=SERIAL_BAUDRATE, help='波特率')
    parser.add_argument('--db', type=str, default=None, help='数据库路径')
    args = parser.parse_args()
    
    pipeline = MMWProcessPipeline(args.uid, args.port, args.baudrate, args.db)
    pipeline.run()


if __name__ == '__main__':
    main()
