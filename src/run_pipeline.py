"""毫米波监测系统运行管道 - MVP简化版."""
import signal
import sys
import threading
import time
from pathlib import Path
from queue import Queue

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.mmw_rader import MMWRadarThread
from src.mmw_processor import MMWProcessorThread
from src.mmw_breath import MMWBreathThread
from src.mmw_heart_rate import MMWHeartRateThread
from src.mmw_human_check import MMWHumanCheckThread
from src.mmw_database import (
    UnifiedDatabaseWriter,
    SCGDatabaseWriter,
    BreathDatabaseWriter,
    HeartRateDatabaseWriter,
    HumanCheckDatabaseWriter,
)


class RadarBroadcaster(threading.Thread):
    """雷达数据广播器 - 将数据复制到多个队列(带降采样)."""
    
    def __init__(self, input_queue: Queue, output_queues: list[Queue], downsample_ratios: list = None):
        super().__init__(daemon=True)
        self._input = input_queue
        self._outputs = output_queues
        self._downsample_ratios = downsample_ratios or [1] * len(output_queues)
        self._running = False
        self._count = 0
        self._counters = [0] * len(output_queues)  # 每个输出的计数器
    
    def run(self):
        """主循环 - 广播数据(支持降采样)."""
        self._running = True
        from queue import Empty
        while self._running:
            try:
                data = self._input.get(timeout=0.5)
                self._count += 1
                
                # 根据降采样比例发送到各个队列
                for i, (q, ratio) in enumerate(zip(self._outputs, self._downsample_ratios)):
                    self._counters[i] += 1
                    if self._counters[i] >= ratio:
                        try:
                            q.put_nowait(data)
                            self._counters[i] = 0
                        except:
                            pass  # 队列满则跳过
            except Empty:
                continue
    
    def stop(self):
        """停止广播."""
        self._running = False


class MMWPipeline:
    """毫米波流水线 - 雷达→SCG/呼吸处理→数据库."""
    
    def __init__(self, uid=0, serial_port="COM7", serial_baudrate=921600, database_path=None):
        self.uid = uid
        self.serial_port = serial_port
        self.serial_baudrate = serial_baudrate
        self.database_path = database_path
        
        # 分离队列：每个处理器独立队列
        self.radar_queue = Queue(maxsize=2000)  # 雷达原始数据
        self.radar_queue_scg = Queue(maxsize=1000)  # 雷达→SCG
        self.radar_queue_breath = Queue(maxsize=1000)  # 雷达→呼吸
        self.radar_queue_heart = Queue(maxsize=1000)  # 雷达→心率
        self.radar_queue_human = Queue(maxsize=1000)  # 雷达→人体检测
        self.scg_queue = Queue(maxsize=500)
        self.breath_queue = Queue(maxsize=500)
        self.heart_rate_queue = Queue(maxsize=500)
        self.human_check_queue = Queue(maxsize=500)
        
        # 线程
        self.radar_thread = None
        self.broadcaster = None
        self.scg_thread = None
        self.breath_thread = None
        self.heart_rate_thread = None
        self.human_check_thread = None
        self.unified_db_writer = None  # 统一数据库写入器
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
        print("=" * 60)
        print(f"启动流水线 | UID: {self.uid} | 串口: {self.serial_port}")
        print("=" * 60)
        
        # 1. 启动雷达采集
        self.radar_thread = MMWRadarThread(
            self.radar_queue, self.serial_port, self.serial_baudrate
        )
        self.radar_thread.start()
        time.sleep(1)
        
        # 2. 启动广播器(将雷达数据复制到4个队列,带降采样)
        # 降采样比例: [SCG:1, 呼吸:1, 心率:1, 人体检测:5]
        # 心率和人体检测不需要那么高帧率
        self.broadcaster = RadarBroadcaster(
            self.radar_queue, 
            [
                self.radar_queue_scg,
                self.radar_queue_breath,
                self.radar_queue_heart,
                self.radar_queue_human
            ],
            downsample_ratios=[1, 1, 1, 1]  # 人体检测降到41fps
        )
        self.broadcaster.start()
        
        # 3. 启动SCG处理
        self.scg_thread = MMWProcessorThread(self.radar_queue_scg, self.scg_queue)
        self.scg_thread.start()
        
        # 4. 启动呼吸处理
        self.breath_thread = MMWBreathThread(self.radar_queue_breath, self.breath_queue)
        self.breath_thread.start()
        
        # 5. 启动心率处理
        self.heart_rate_thread = MMWHeartRateThread(self.radar_queue_heart, self.heart_rate_queue)
        self.heart_rate_thread.start()
        
        # 6. 启动人体检测
        self.human_check_thread = MMWHumanCheckThread(self.radar_queue_human, self.human_check_queue)
        self.human_check_thread.start()
        
        # 7. 启动统一数据库写入器
        self.unified_db_writer = UnifiedDatabaseWriter(self.uid, self.database_path)
        self.unified_db_writer.start()
        
        # 8. 启动适配器转发线程
        self.scg_db_thread = SCGDatabaseWriter(
            self.scg_queue, self.uid, self.database_path
        )
        self.scg_db_thread.set_unified_writer(self.unified_db_writer)
        self.scg_db_thread.start()
        
        self.breath_db_thread = BreathDatabaseWriter(
            self.breath_queue, self.uid, self.database_path
        )
        self.breath_db_thread.set_unified_writer(self.unified_db_writer)
        self.breath_db_thread.start()
        
        self.heart_rate_db_thread = HeartRateDatabaseWriter(
            self.heart_rate_queue, self.uid, self.database_path
        )
        self.heart_rate_db_thread.set_unified_writer(self.unified_db_writer)
        self.heart_rate_db_thread.start()
        
        self.human_check_db_thread = HumanCheckDatabaseWriter(
            self.human_check_queue, self.uid, self.database_path
        )
        self.human_check_db_thread.set_unified_writer(self.unified_db_writer)
        self.human_check_db_thread.start()
        
        self.running = True
        print("✓ 所有线程已启动 (雷达 → 广播器 → SCG/呼吸/心率/人体 → 统一数据库)\n")
    
    def stop(self):
        """停止流水线."""
        if not self.running:
            return
        print("\n停止所有线程...")
        
        threads = [
            ('雷达', self.radar_thread),
            ('广播器', self.broadcaster),
            ('SCG', self.scg_thread),
            ('呼吸', self.breath_thread),
            ('心率', self.heart_rate_thread),
            ('人体检测', self.human_check_thread),
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
                print(f"✓ {name}已停止")
        
        self.running = False
    
    def run(self):
        """运行流水线."""
        self.start()
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()


def main():
    """主函数."""
    import argparse
    parser = argparse.ArgumentParser(description='毫米波监测系统')
    parser.add_argument('--uid', type=int, default=0, help='用户ID')
    parser.add_argument('--port', type=str, default='COM7', help='串口号')
    parser.add_argument('--baudrate', type=int, default=921600, help='波特率')
    parser.add_argument('--db', type=str, default=None, help='数据库路径')
    args = parser.parse_args()
    
    pipeline = MMWPipeline(args.uid, args.port, args.baudrate, args.db)
    pipeline.run()


if __name__ == '__main__':
    main()
