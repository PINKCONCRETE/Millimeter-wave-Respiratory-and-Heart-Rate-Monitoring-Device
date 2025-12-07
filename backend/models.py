from datetime import datetime

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class UserInfo(db.Model):
    """用户信息表."""

    __tablename__ = 'user_info'

    uid = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    age = db.Column(db.Integer)
    gender = db.Column(db.String(10))
    created_at = db.Column(db.DateTime, default=datetime.now)

class UserWaveform(db.Model):
    """用户波形数据表."""

    __tablename__ = 'user_waveform'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    uid = db.Column(db.Integer, db.ForeignKey('user_info.uid'), nullable=False)
    breath_waveform = db.Column(db.Text)  # JSON格式存储
    breath_ring_x = db.Column(db.Text)  # JSON格式存储
    breath_ring_y = db.Column(db.Text)  # JSON格式存储
    scg_waveform = db.Column(db.Text)  # JSON格式存储
    heart_waveform = db.Column(db.Text)  # JSON格式存储
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

class BreathData(db.Model):
    """呼吸数据表."""

    __tablename__ = 'breath_data'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    uid = db.Column(db.Integer, db.ForeignKey('user_info.uid'), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False)
    respiratory_rate = db.Column(db.Float)  # 呼吸率
    is_in_bed = db.Column(db.Boolean, default=True)
    warning_id = db.Column(db.Integer, default=0)  # 0:正常, 21:呼吸暂停, 22:COPD

class HeartData(db.Model):
    """心率数据表."""

    __tablename__ = 'heart_data'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    uid = db.Column(db.Integer, db.ForeignKey('user_info.uid'), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False)
    heart_rate = db.Column(db.Float)  # 心率
    is_in_bed = db.Column(db.Boolean, default=True)
    is_arrhythmia = db.Column(db.Integer, default=0)  # 0:正常, 1:心律失常

class HRVData(db.Model):
    """HRV数据表."""

    __tablename__ = 'hrv_data'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    uid = db.Column(db.Integer, db.ForeignKey('user_info.uid'), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False)
    hrv_value = db.Column(db.Float)  # HRV值
    time_stamps = db.Column(db.Text)  # JSON格式存储时间戳列表

class HeartStats(db.Model):
    """心率统计表."""

    __tablename__ = 'heart_stats'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    uid = db.Column(db.Integer, db.ForeignKey('user_info.uid'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    avg_heart_rate = db.Column(db.Float)
    max_heart_rate = db.Column(db.Float)
    min_heart_rate = db.Column(db.Float)

class ArrhythmiaCount(db.Model):
    """心律失常统计表."""

    __tablename__ = 'arrhythmia_count'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    uid = db.Column(db.Integer, db.ForeignKey('user_info.uid'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    count = db.Column(db.Integer, default=0)

class BreathIndex(db.Model):
    """呼吸指数表."""

    __tablename__ = 'breath_index'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    uid = db.Column(db.Integer, db.ForeignKey('user_info.uid'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    br_index = db.Column(db.Float)

class StressData(db.Model):
    """压力数据表."""

    __tablename__ = 'stress_data'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    uid = db.Column(db.Integer, db.ForeignKey('user_info.uid'), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False)
    stress_index = db.Column(db.Float)
    stress_level = db.Column(db.String(10))  # 低/中/高
