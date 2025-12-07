"""毫米波数据库写入模块 - 统一写入器版本."""
import json
import os
import sys
import threading
from datetime import datetime
from pathlib import Path
from queue import Empty, Queue

backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from flask import Flask
from backend.models import db, UserWaveform, HeartData


class UnifiedDatabaseWriter(threading.Thread):
    """统一数据库写入器 - 串行处理所有数据库写入."""
    
    def __init__(self, uid: int = 0, database_path: str | None = None):
        super().__init__(daemon=True)
        self._uid = uid
        self._queue = Queue(maxsize=2000)  # 统一写入队列
        self._running = False
        
        # SCG相关
        self._scg_buffer = []
        self._scg_waveform = [0.0] * 200
        self._scg_count = 0
        self._scg_writes = 0
        
        # 呼吸相关
        self._breath_waveform = [0.0] * 200
        self._breath_ring_x = [0.0] * 1000
        self._breath_ring_y = [0.0] * 1000
        self._breath_count = 0
        self._last_wave_frame = 0
        self._last_ring_frame = 0
        self._wave_writes = 0
        self._ring_writes = 0
        
        # 心率相关
        self._heart_waveform_buffer = []  # 缓冲200个心率值
        self._heart_timestamp_buffer = []  # 对应的时间戳
        self._heart_count = 0
        self._heart_writes = 0
        
        # 人体检测相关
        self._human_status = True
        self._human_check_count = 0
        
        # 初始化数据库
        self._app = Flask(__name__)
        if database_path is None:
            database_path = str(Path(__file__).parent.parent / 'database' / 'mmw_monitor.db')
        os.makedirs(os.path.dirname(database_path), exist_ok=True)
        self._app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{database_path}'
        self._app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        db.init_app(self._app)
        
        with self._app.app_context():
            db.create_all()
            if not UserWaveform.query.filter_by(uid=uid).first():
                waveform = UserWaveform(
                    uid=uid,
                    breath_waveform=json.dumps([0.0] * 200),
                    breath_ring_x=json.dumps([0.0] * 1000),
                    breath_ring_y=json.dumps([0.0] * 1000),
                    scg_waveform=json.dumps([0.0] * 200),
                    heart_waveform=json.dumps([0.0] * 200),
                )
                db.session.add(waveform)
                db.session.commit()
        print(f"✓ 统一数据库写入器启动 (UID: {uid})")
    
    def put_scg(self, value: float):
        """添加SCG数据."""
        try:
            self._queue.put_nowait({'type': 'scg', 'value': value})
        except:
            pass  # 队列满则丢弃
    
    def put_breath(self, data: dict):
        """添加呼吸数据."""
        try:
            self._queue.put_nowait({'type': 'breath', 'data': data})
        except:
            pass  # 队列满则丢弃
    
    def put_heart_rate(self, data: dict):
        """添加心率数据."""
        try:
            self._queue.put_nowait({'type': 'heart_rate', 'data': data})
        except:
            pass  # 队列满则丢弃
    
    def put_human_check(self, has_human: bool):
        """添加人体检测数据."""
        try:
            self._queue.put_nowait({'type': 'human_check', 'has_human': has_human})
        except:
            pass  # 队列满则丢弃
    
    def run(self):
        """主循环 - 串行处理所有写入."""
        self._running = True
        import numpy as np
        
        with self._app.app_context():
            while self._running:
                try:
                    item = self._queue.get(timeout=0.5)
                    
                    if item['type'] == 'scg':
                        self._handle_scg(item['value'])
                    elif item['type'] == 'breath':
                        self._handle_breath(item['data'], np)
                    elif item['type'] == 'heart_rate':
                        self._handle_heart_rate(item['data'])
                    elif item['type'] == 'human_check':
                        self._handle_human_check(item['has_human'])
                    
                except Empty:
                    continue
                except Exception as e:
                    print(f"[数据库] 处理错误: {e}")
                    db.session.rollback()
    
    def _handle_scg(self, value: float):
        """处理SCG数据."""
        self._scg_buffer.append(value)
        self._scg_count += 1
        
        # 每100个点写入一次
        if len(self._scg_buffer) >= 100:
            for v in self._scg_buffer:
                self._scg_waveform.pop(0)
                self._scg_waveform.append(v)
            
            waveform = UserWaveform.query.filter_by(uid=self._uid).first()
            if waveform:
                waveform.scg_waveform = json.dumps(self._scg_waveform)
                waveform.updated_at = datetime.now()
                db.session.commit()
                self._scg_writes += 1
                print(f"✓ [SCG] 写入100点 | 累计: {self._scg_count} | 写入: {self._scg_writes}")
            
            self._scg_buffer.clear()
    
    def _handle_breath(self, data: dict, np):
        """处理呼吸数据."""
        self._breath_count += 1
        
        rr_wave = data.get('rr_wave')
        displacement = data.get('displacement')
        flow_rate = data.get('flow_rate')
        frame_idx = data.get('frame_idx', 0)
        
        # 更新内存中的数据 - 添加None检查
        if rr_wave is not None and len(rr_wave) > 0:
            indices = np.linspace(0, len(rr_wave)-1, 200, dtype=int)
            self._breath_waveform = [float(rr_wave[i]) for i in indices]
        
        if (displacement is not None and flow_rate is not None and 
            len(displacement) > 0 and len(flow_rate) > 0):
            indices = np.linspace(0, len(displacement)-1, 1000, dtype=int)
            self._breath_ring_x = [float(displacement[i]) for i in indices]
            self._breath_ring_y = [float(flow_rate[i]) for i in indices]
        
        # 每100帧写入波形
        if frame_idx >= 100 and frame_idx % 100 == 0 and frame_idx != self._last_wave_frame:
            waveform = UserWaveform.query.filter_by(uid=self._uid).first()
            if waveform:
                waveform.breath_waveform = json.dumps(self._breath_waveform)
                waveform.updated_at = datetime.now()
                db.session.commit()
                self._wave_writes += 1
                self._last_wave_frame = frame_idx
                print(f"✓ [呼吸波形] 帧{frame_idx} | 写入: {self._wave_writes}")
        
        # 每2000帧写入环
        if frame_idx >= 2000 and frame_idx % 2000 == 0 and frame_idx != self._last_ring_frame:
            waveform = UserWaveform.query.filter_by(uid=self._uid).first()
            if waveform:
                waveform.breath_ring_x = json.dumps(self._breath_ring_x)
                waveform.breath_ring_y = json.dumps(self._breath_ring_y)
                waveform.updated_at = datetime.now()
                db.session.commit()
                self._ring_writes += 1
                self._last_ring_frame = frame_idx
                print(f"✓ [呼吸环] 帧{frame_idx} | 写入: {self._ring_writes}")
        
        # 调试
        if self._breath_count % 1000 == 0:
            print(f"[呼吸] 接收{self._breath_count}次 | 帧{frame_idx} | 波形:{self._wave_writes} | 环:{self._ring_writes}")
    
    def _handle_heart_rate(self, data: dict):
        """处理心率数据 - 添加到HeartData表并更新波形."""
        self._heart_count += 1
        
        heart_rate = data.get('heart_rate')
        if heart_rate is None or heart_rate <= 0:
            return
        
        timestamp = datetime.now()
        heart_rate_int = int(round(heart_rate))
        
        # 写入HeartData历史表
        heart_data = HeartData(
            uid=self._uid,
            timestamp=timestamp,
            heart_rate=float(heart_rate_int),
            is_in_bed=self._human_status,
            is_arrhythmia=0  # 待后续添加心律失常检测
        )
        db.session.add(heart_data)
        
        # 保持最近200个心率数据用于波形显示
        self._heart_waveform_buffer.append(heart_rate_int)
        self._heart_timestamp_buffer.append(timestamp.timestamp())
        if len(self._heart_waveform_buffer) > 200:
            self._heart_waveform_buffer.pop(0)
            self._heart_timestamp_buffer.pop(0)
        
        # 更新UserWaveform表的heart_waveform(在同一个事务中)
        waveform = UserWaveform.query.filter_by(uid=self._uid).first()
        if waveform:
            waveform.heart_waveform = json.dumps(self._heart_waveform_buffer)
            waveform.updated_at = timestamp
        
        # 一次性提交(包括HeartData和UserWaveform)
        db.session.commit()
        self._heart_writes += 1
        
        print(f"✓ [心率] 写入 | 心率:{heart_rate_int}bpm | 累计:{self._heart_writes}")
    
    def _handle_human_check(self, has_human: bool):
        """处理人体检测数据 - 更新is_in_bed状态."""
        self._human_check_count += 1
        self._human_status = has_human
        
        # 每100次检测打印一次
        if self._human_check_count % 100 == 0:
            status = "有人" if has_human else "无人"
            print(f"[人体检测] {status} | 检测次数:{self._human_check_count}")
    
    def stop(self):
        """停止并写入剩余数据."""
        self._running = False
        with self._app.app_context():
            waveform = UserWaveform.query.filter_by(uid=self._uid).first()
            if waveform:
                # 写入剩余SCG
                if self._scg_buffer:
                    for v in self._scg_buffer:
                        self._scg_waveform.pop(0)
                        self._scg_waveform.append(v)
                    waveform.scg_waveform = json.dumps(self._scg_waveform)
                
                # 写入最新呼吸数据
                waveform.breath_waveform = json.dumps(self._breath_waveform)
                waveform.breath_ring_x = json.dumps(self._breath_ring_x)
                waveform.breath_ring_y = json.dumps(self._breath_ring_y)
                waveform.updated_at = datetime.now()
                db.session.commit()
        
        print(f"✓ [数据库] 停止 | SCG:{self._scg_writes} | 呼吸波形:{self._wave_writes} | 呼吸环:{self._ring_writes} | 心率:{self._heart_writes} | 人体检测:{self._human_check_count}")
    
    def get_statistics(self):
        """获取统计."""
        return {
            "scg_count": self._scg_count,
            "scg_writes": self._scg_writes,
            "breath_count": self._breath_count,
            "wave_writes": self._wave_writes,
            "ring_writes": self._ring_writes,
            "heart_count": self._heart_count,
            "heart_writes": self._heart_writes,
            "human_check_count": self._human_check_count,
            "has_human": self._human_status,
            "queue_size": self._queue.qsize(),
        }


# 保留旧的接口以兼容
class SCGDatabaseWriter(threading.Thread):
    """SCG数据库写入器 - 适配器模式."""
    
    def __init__(self, input_queue: Queue, uid: int = 0, database_path: str | None = None):
        super().__init__(daemon=True)
        self._queue = input_queue
        self._writer = None
        self._running = False
    
    def set_unified_writer(self, writer: UnifiedDatabaseWriter):
        """设置统一写入器."""
        self._writer = writer
    
    def run(self):
        """转发数据到统一写入器 - 每次都转发,由UnifiedWriter批处理."""
        self._running = True
        while self._running:
            try:
                data = self._queue.get(timeout=0.5)
                value = data.get('scg_value', 0.0) if isinstance(data, dict) else float(data)
                if self._writer:
                    self._writer.put_scg(value)
            except Empty:
                continue
    
    def stop(self):
        """停止."""
        self._running = False


class BreathDatabaseWriter(threading.Thread):
    """呼吸数据库写入器 - 适配器模式."""
    
    def __init__(self, input_queue: Queue, uid: int = 0, database_path: str | None = None):
        super().__init__(daemon=True)
        self._queue = input_queue
        self._writer = None
        self._running = False
    
    def set_unified_writer(self, writer: UnifiedDatabaseWriter):
        """设置统一写入器."""
        self._writer = writer
    
    def run(self):
        """转发数据到统一写入器 - 每次都转发,由UnifiedWriter根据frame_idx判断."""
        self._running = True
        while self._running:
            try:
                data = self._queue.get(timeout=0.5)
                if isinstance(data, dict) and self._writer:
                    self._writer.put_breath(data)
            except Empty:
                continue
    
    def stop(self):
        """停止."""
        self._running = False


class HeartRateDatabaseWriter(threading.Thread):
    """心率数据库写入器 - 适配器模式."""
    
    def __init__(self, input_queue: Queue, uid: int = 0, database_path: str | None = None):
        super().__init__(daemon=True)
        self._queue = input_queue
        self._writer = None
        self._running = False
        # 心率已经是每1000帧产生一次,不需要额外过滤
    
    def set_unified_writer(self, writer: UnifiedDatabaseWriter):
        """设置统一写入器."""
        self._writer = writer
    
    def run(self):
        """转发数据到统一写入器 - 心率本身就是低频数据."""
        self._running = True
        while self._running:
            try:
                data = self._queue.get(timeout=0.5)
                if isinstance(data, dict) and self._writer:
                    self._writer.put_heart_rate(data)
            except Empty:
                continue
    
    def stop(self):
        """停止."""
        self._running = False


class HumanCheckDatabaseWriter(threading.Thread):
    """人体检测数据库写入器 - 适配器模式."""
    
    def __init__(self, input_queue: Queue, uid: int = 0, database_path: str | None = None):
        super().__init__(daemon=True)
        self._queue = input_queue
        self._writer = None
        self._running = False
        self._count = 0  # 检测计数器
        self._write_interval = 200  # 每200次写一次
    
    def set_unified_writer(self, writer: UnifiedDatabaseWriter):
        """设置统一写入器."""
        self._writer = writer
    
    def run(self):
        """转发数据到统一写入器 - 每200次写一次."""
        self._running = True
        while self._running:
            try:
                data = self._queue.get(timeout=0.5)
                # 从人体检测结果中提取has_human状态
                if isinstance(data, dict):
                    self._count += 1
                    # 每200次写一次
                    if self._count % self._write_interval == 0:
                        has_human = data.get('has_human', True)
                        if self._writer:
                            self._writer.put_human_check(has_human)
            except Empty:
                continue
    
    def stop(self):
        """停止."""
        self._running = False
