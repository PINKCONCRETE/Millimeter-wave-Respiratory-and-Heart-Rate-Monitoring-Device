"""初始化数据库并插入示例数据."""
import json
import random
from datetime import datetime, timedelta

import numpy as np

from app import app, db
from models import (
    ArrhythmiaCount,
    BreathData,
    BreathIndex,
    HeartData,
    HeartStats,
    HRVData,
    StressData,
    UserInfo,
    UserWaveform,
)

def generate_waveform(length):
    """生成波形数据."""
    data = (
        np.sin(np.linspace(0, 4 * np.pi, length)) * 100
        + np.random.randn(length) * 10
    )
    return json.dumps(data.tolist())

def init_database():
    """初始化数据库."""
    with app.app_context():
        # 删除所有表并重新创建
        db.drop_all()
        db.create_all()
        
        print("创建数据库表完成...")
        
        # 创建示例用户
        user = UserInfo(
            uid=0,
            name='测试用户',
            age=25,
            gender='男'
        )
        db.session.add(user)
        db.session.commit()
        print("创建用户: uid=0")
        
        # 创建波形数据
        waveform = UserWaveform(
            uid=0,
            breath_waveform=generate_waveform(200),
            breath_ring_x=generate_waveform(1000),
            breath_ring_y=generate_waveform(1000),
            scg_waveform=generate_waveform(1000),
            heart_waveform=generate_waveform(200)
        )
        db.session.add(waveform)
        db.session.commit()
        print("创建波形数据完成")
        
        # 创建24小时的呼吸历史数据
        start_time = datetime.now() - timedelta(hours=24)
        breath_records = []
        for i in range(288):  # 24小时，每5分钟一条
            record = BreathData(
                uid=0,
                timestamp=start_time + timedelta(minutes=5*i),
                respiratory_rate=random.randint(12, 20),
                is_in_bed=True,
                warning_id=0
            )
            breath_records.append(record)
        db.session.bulk_save_objects(breath_records)
        db.session.commit()
        print(f"创建呼吸历史数据: {len(breath_records)}条")
        
        # 创建24小时的心率历史数据
        heart_records = []
        for i in range(288):
            record = HeartData(
                uid=0,
                timestamp=start_time + timedelta(minutes=5*i),
                heart_rate=random.randint(60, 100),
                is_in_bed=True,
                is_arrhythmia=random.choice([0, 0, 0, 1])  # 25%概率心律失常
            )
            heart_records.append(record)
        db.session.bulk_save_objects(heart_records)
        db.session.commit()
        print(f"创建心率历史数据: {len(heart_records)}条")
        
        # 创建HRV数据
        now = datetime.now()
        time_stamps_list = [
            (now - timedelta(seconds=5 * i)).timestamp()
            for i in range(100, 0, -1)
        ]
        hrv_records = []
        for i in range(10):  # 创建10条HRV记录
            record = HRVData(
                uid=0,
                timestamp=now - timedelta(hours=i),
                hrv_value=random.randint(20, 200),
                time_stamps=json.dumps(time_stamps_list)
            )
            hrv_records.append(record)
        db.session.bulk_save_objects(hrv_records)
        db.session.commit()
        print(f"创建HRV数据: {len(hrv_records)}条")
        
        # 创建心率统计数据（最近7天）
        stats_records = []
        for i in range(7):
            record = HeartStats(
                uid=0,
                date=(datetime.now() - timedelta(days=i)).date(),
                avg_heart_rate=random.randint(70, 80),
                max_heart_rate=random.randint(90, 110),
                min_heart_rate=random.randint(55, 65)
            )
            stats_records.append(record)
        db.session.bulk_save_objects(stats_records)
        db.session.commit()
        print(f"创建心率统计数据: {len(stats_records)}条")
        
        # 创建心律失常统计（最近7天）
        arr_records = []
        for i in range(7):
            record = ArrhythmiaCount(
                uid=0,
                date=(datetime.now() - timedelta(days=i)).date(),
                count=random.randint(0, 5)
            )
            arr_records.append(record)
        db.session.bulk_save_objects(arr_records)
        db.session.commit()
        print(f"创建心律失常统计: {len(arr_records)}条")
        
        # 创建呼吸指数（最近7天）
        br_index_records = []
        for i in range(7):
            record = BreathIndex(
                uid=0,
                date=(datetime.now() - timedelta(days=i)).date(),
                br_index=round(random.uniform(70, 100), 2)
            )
            br_index_records.append(record)
        db.session.bulk_save_objects(br_index_records)
        db.session.commit()
        print(f"创建呼吸指数数据: {len(br_index_records)}条")
        
        # 创建压力数据
        stress_records = []
        stress_levels = ['低', '中', '高']
        for i in range(24):  # 最近24小时
            record = StressData(
                uid=0,
                timestamp=now - timedelta(hours=i),
                stress_index=round(random.uniform(0, 100), 2),
                stress_level=random.choice(stress_levels)
            )
            stress_records.append(record)
        db.session.bulk_save_objects(stress_records)
        db.session.commit()
        print(f"创建压力数据: {len(stress_records)}条")
        
        print("\n数据库初始化完成！")
        print("数据库位置: database/mmw_monitor.db")

if __name__ == '__main__':
    init_database()
