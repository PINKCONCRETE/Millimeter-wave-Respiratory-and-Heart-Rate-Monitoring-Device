"""测试数据更新脚本 - 用于验证前端实时刷新功能."""
import json
import random
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.app import app, db  # noqa: E402
from backend.models import BreathData, HeartData, UserWaveform  # noqa: E402


def generate_waveform(length: int, phase: float = 0) -> str:
    """生成带相位偏移的波形数据."""
    x = np.linspace(phase, 4 * np.pi + phase, length)
    data = np.sin(x) * 100 + np.random.randn(length) * 10
    return json.dumps(data.tolist())


def update_breath_waveform(uid=0):
    """更新呼吸波形数据."""
    with app.app_context():
        waveform = UserWaveform.query.filter_by(uid=uid).first()
        if waveform:
            # 使用随机相位生成新波形
            phase = random.random() * 2 * np.pi
            waveform.breath_waveform = generate_waveform(200, phase)
            waveform.breath_ring_x = generate_waveform(1000, phase)
            waveform.breath_ring_y = generate_waveform(1000, phase + 1)
            waveform.updated_at = datetime.now()
            db.session.commit()
            
            # 打印更新的数据预览
            breath_data = json.loads(waveform.breath_waveform)[:5]
            ring_x_data = json.loads(waveform.breath_ring_x)[:5]
            ring_y_data = json.loads(waveform.breath_ring_y)[:5]
            
            print(f"✓ 更新呼吸波形数据 - {datetime.now().strftime('%H:%M:%S')}")
            print(f"  波形前5个点: {[round(x, 2) for x in breath_data]}")
            print(f"  环形X前5个点: {[round(x, 2) for x in ring_x_data]}")
            print(f"  环形Y前5个点: {[round(x, 2) for x in ring_y_data]}")
            return True
        print("✗ 未找到用户波形数据")
        return False


def update_heart_waveform(uid=0):
    """更新心率波形数据."""
    with app.app_context():
        waveform = UserWaveform.query.filter_by(uid=uid).first()
        if waveform:
            # 使用随机相位生成新波形
            phase = random.random() * 2 * np.pi
            waveform.heart_waveform = json.dumps([80] * 200)
            waveform.scg_waveform = generate_waveform(1000, phase)
            waveform.updated_at = datetime.now()
            db.session.commit()
            
            # 打印更新的数据预览
            heart_data = json.loads(waveform.heart_waveform)[:5]
            scg_data = json.loads(waveform.scg_waveform)[:5]
            
            print(f"✓ 更新心率波形数据 - {datetime.now().strftime('%H:%M:%S')}")
            print(f"  心率波形前5个点: {[round(x, 2) for x in heart_data]}")
            print(f"  SCG波形前5个点: {[round(x, 2) for x in scg_data]}")
            return True
        print("✗ 未找到用户波形数据")
        return False


def update_breath_records(uid=0, count=200):
    """批量更新呼吸历史记录."""
    with app.app_context():
        # 获取最新的200条记录并更新
        records = BreathData.query.filter_by(uid=uid).order_by(
            BreathData.timestamp.desc()
        ).limit(count).all()
        
        if not records:
            print("✗ 未找到呼吸历史记录")
            return False
        
        updated_count = 0
        rates = []
        warnings = []
        
        for record in records:
            record.respiratory_rate = random.randint(12, 20)
            record.warning_id = random.choice([0, 0, 0, 21, 22])
            record.timestamp = datetime.now()
            rates.append(record.respiratory_rate)
            warnings.append(record.warning_id)
            updated_count += 1
        
        db.session.commit()
        
        # 统计信息
        avg_rate = sum(rates) / len(rates)
        warning_count = sum(1 for w in warnings if w != 0)
        
        print(f"✓ 更新呼吸历史记录 - {updated_count}条")
        print(f"  平均呼吸率: {avg_rate:.1f}")
        print(f"  异常记录数: {warning_count}")
        print(f"  最新5条呼吸率: {rates[:5]}")
        return True


def update_heart_records(uid=0, count=200):
    """批量更新心率历史记录."""
    with app.app_context():
        # 获取最新的200条记录并更新
        records = HeartData.query.filter_by(uid=uid).order_by(
            HeartData.timestamp.desc()
        ).limit(count).all()
        
        if not records:
            print("✗ 未找到心率历史记录")
            return False
        
        updated_count = 0
        rates = []
        arrhythmias = []
        
        for record in records:
            record.heart_rate = random.randint(60, 100)
            record.is_arrhythmia = random.choice([0, 0, 0, 1])
            record.timestamp = datetime.now()
            rates.append(record.heart_rate)
            arrhythmias.append(record.is_arrhythmia)
            updated_count += 1
        
        db.session.commit()
        
        # 统计信息
        avg_rate = sum(rates) / len(rates)
        arrhythmia_count = sum(arrhythmias)
        
        print(f"✓ 更新心率历史记录 - {updated_count}条")
        print(f"  平均心率: {avg_rate:.1f}")
        print(f"  心律失常数: {arrhythmia_count}")
        print(f"  最新5条心率: {rates[:5]}")
        return True


def continuous_update(interval=2, duration=60):
    """持续更新数据用于测试.

    Args:
        interval: 更新间隔(秒)
        duration: 运行时长(秒)，0表示无限运行
    """
    print("\n开始持续更新数据...")
    print(f"更新间隔: {interval}秒")
    print(f"运行时长: {'无限' if duration == 0 else f'{duration}秒'}")
    print("按 Ctrl+C 停止\n")

    start_time = time.time()
    count = 0

    try:
        while True:
            count += 1
            print(f"\n第 {count} 次更新:")

            # 更新波形数据
            update_breath_waveform()
            update_heart_waveform()

            # 更新历史记录（每次200条）
            update_breath_records(count=200)
            update_heart_records(count=200)

            # 检查是否达到运行时长
            if duration > 0 and (time.time() - start_time) >= duration:
                print(f"\n✓ 达到运行时长 {duration}秒，停止更新")
                break

            # 等待下一次更新
            time.sleep(interval)

    except KeyboardInterrupt:
        print("\n\n✓ 用户中断，停止更新")
    finally:
        print(f"\n总共完成 {count} 次更新")


def quick_test():
    """快速测试 - 单次更新所有数据."""
    print("\n=== 快速测试 - 更新所有数据 ===\n")

    update_breath_waveform()
    print()
    update_heart_waveform()
    print()
    update_breath_records(count=200)
    print()
    update_heart_records(count=200)

    print("\n✓ 快速测试完成")


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='数据库测试更新工具')
    parser.add_argument(
        '--mode',
        choices=['quick', 'continuous'],
        default='quick',
        help='运行模式: quick(单次测试) 或 continuous(持续更新)'
    )
    parser.add_argument(
        '--interval',
        type=int,
        default=2,
        help='持续模式下的更新间隔(秒)，默认2秒'
    )
    parser.add_argument(
        '--duration',
        type=int,
        default=60,
        help='持续模式下的运行时长(秒)，0表示无限运行，默认60秒'
    )

    args = parser.parse_args()

    if args.mode == 'quick':
        quick_test()
    else:
        continuous_update(args.interval, args.duration)
