from flask import Flask, jsonify, request
from flask_cors import CORS
import numpy as np
from datetime import datetime, timedelta
import random
import json
import os

from pathlib import Path
import sys
# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.models import (db, UserInfo, UserWaveform, BreathData, HeartData,
                   HRVData, HeartStats, ArrhythmiaCount, BreathIndex, StressData)

app = Flask(__name__)
CORS(app)  # 允许跨域请求

# 配置数据库
basedir = os.path.abspath(os.path.dirname(__file__))
database_path = os.path.join(os.path.dirname(basedir), 'database', 'mmw_monitor.db')
os.makedirs(os.path.dirname(database_path), exist_ok=True)

app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{database_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)


# ==================== 呼吸相关API ====================

@app.route('/api/br/getWaveform/uid/<int:uid>', methods=['GET'])
def get_breath_waveform(uid):
    """获取呼吸波形数据"""
    waveform = UserWaveform.query.filter_by(uid=uid).first()
    breath_data = BreathData.query.filter_by(uid=uid).order_by(BreathData.timestamp.desc()).first()
    
    if waveform:
        return jsonify({
            'code': 20000,
            'message': 'success',
            'data': {
                'uid': str(uid),
                'breath_waveform': json.loads(waveform.breath_waveform)[-200:],
                'is_in_bed': breath_data.is_in_bed if breath_data else True,
                'timestamp': waveform.timestamp.timestamp() if waveform.timestamp else datetime.now().timestamp()
            }
        })
    else:
        return jsonify({'code': 40000, 'message': '用户不存在'}), 404


@app.route('/api/br/getRing/uid/<int:uid>', methods=['GET'])
def get_breath_ring(uid):
    """获取呼吸环形图数据"""
    waveform = UserWaveform.query.filter_by(uid=uid).first()
    
    if waveform:
        return jsonify({
            'code': 20000,
            'message': 'success',
            'data': {
                'uid': str(uid),
                'breath_ring_x': json.loads(waveform.breath_ring_x)[-200:],
                'breath_ring_y': json.loads(waveform.breath_ring_y)[-200:]
            }
        })
    else:
        return jsonify({'code': 40000, 'message': '用户不存在'}), 404


@app.route('/api/br/getWarning/uid/<int:uid>', methods=['GET'])
def get_breath_warning(uid):
    """获取呼吸警告信息"""
    breath_data = BreathData.query.filter_by(uid=uid).order_by(BreathData.timestamp.desc()).first()
    
    if breath_data:
        return jsonify({
            'code': 20000,
            'message': 'success',
            'data': {
                'uid': str(uid),
                'breath_warning_id': breath_data.warning_id
            }
        })
    else:
        return jsonify({'code': 40000, 'message': '用户不存在'}), 404


# ==================== 心率相关API ====================

@app.route('/api/arr/getWaveform/uid/<int:uid>', methods=['GET'])
def get_scg_waveform(uid):
    """获取心律波形数据(SCG)"""
    waveform = UserWaveform.query.filter_by(uid=uid).first()
    heart_data = HeartData.query.filter_by(uid=uid).order_by(HeartData.timestamp.desc()).first()
    
    if waveform:
        return jsonify({
            'code': 20000,
            'message': 'success',
            'data': {
                'uid': str(uid),
                'scg_waveform': json.loads(waveform.scg_waveform)[-200:],
                'isArrhythmia': heart_data.is_arrhythmia if heart_data else 0,
                'is_in_bed': heart_data.is_in_bed if heart_data else True
            }
        })
    else:
        return jsonify({'code': 40000, 'message': '用户不存在'}), 404


@app.route('/api/hr/getWaveform/uid/<int:uid>', methods=['GET'])
def get_heart_waveform(uid):
    """获取心率波形数据 - 使用真实历史数据的时间戳"""
    # 获取最近200条心率记录
    heart_records = HeartData.query.filter_by(uid=uid).order_by(
        HeartData.timestamp.desc()
    ).limit(200).all()
    
    if heart_records:
        # 反转使时间升序
        heart_records.reverse()
        
        heart_waveform = [r.heart_rate for r in heart_records]
        time_stamps = [r.timestamp.timestamp() for r in heart_records]
        is_in_bed = heart_records[-1].is_in_bed if heart_records else True
        
        return jsonify({
            'code': 20000,
            'message': 'success',
            'data': {
                'uid': str(uid),
                'heart_waveform': heart_waveform,
                'is_in_bed': is_in_bed,
                'time_stamp': time_stamps
            }
        })
    else:
        # 如果没有历史数据,返回空数组
        return jsonify({
            'code': 20000,
            'message': 'success',
            'data': {
                'uid': str(uid),
                'heart_waveform': [],
                'is_in_bed': True,
                'time_stamp': []
            }
        })


@app.route('/api/hr/getStress/uid/<int:uid>', methods=['GET'])
def get_stress(uid):
    """获取压力指数数据"""
    stress_data = StressData.query.filter_by(uid=uid).order_by(StressData.timestamp.desc()).first()
    
    if stress_data:
        return jsonify({
            'code': 20000,
            'message': 'success',
            'data': {
                'uid': str(uid),
                'timestamp': stress_data.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                'stress_index': stress_data.stress_index,
                'stress_level': stress_data.stress_level
            }
        })
    else:
        return jsonify({'code': 40000, 'message': '用户不存在'}), 404


# ==================== 历史数据API ====================

@app.route('/api/history/br/getBrData', methods=['POST'])
def get_br_history():
    """获取呼吸历史数据"""
    params = request.get_json()
    uid = int(params.get('uid', 0))
    start_time = params.get('start_time')
    end_time = params.get('end_time')
    
    # 解析时间
    if start_time and end_time:
        start_dt = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
        end_dt = datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S')
        records = BreathData.query.filter(
            BreathData.uid == uid,
            BreathData.timestamp.between(start_dt, end_dt)
        ).order_by(BreathData.timestamp).all()
    else:
        # 默认返回24小时数据
        start_dt = datetime.now() - timedelta(hours=24)
        records = BreathData.query.filter(
            BreathData.uid == uid,
            BreathData.timestamp >= start_dt
        ).order_by(BreathData.timestamp).all()
    
    data = [{
        'timestamp': r.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
        'respiratory_rate': r.respiratory_rate
    } for r in records]
    
    return jsonify({
        'code': 20000,
        'message': 'success',
        'data': {
            'uid': str(uid),
            'data': data
        }
    })


@app.route('/api/history/br/index', methods=['POST'])
def get_br_index():
    """获取呼吸指数"""
    params = request.get_json()
    uid = int(params.get('uid', 0))
    
    # 获取今天的呼吸指数
    today = datetime.now().date()
    br_index = BreathIndex.query.filter_by(uid=uid, date=today).first()
    
    if br_index:
        return jsonify({
            'code': 20000,
            'message': 'success',
            'data': {
                'uid': str(uid),
                'br_index': br_index.br_index,
                'date': br_index.date.strftime('%Y-%m-%d')
            }
        })
    else:
        return jsonify({'code': 40000, 'message': '数据不存在'}), 404


@app.route('/api/history/hr/getHeartData', methods=['POST'])
def get_heart_history():
    """获取心率历史数据"""
    params = request.get_json()
    uid = int(params.get('uid', 0))
    start_time = params.get('start_time')
    end_time = params.get('end_time')
    
    # 解析时间
    if start_time and end_time:
        start_dt = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
        end_dt = datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S')
        records = HeartData.query.filter(
            HeartData.uid == uid,
            HeartData.timestamp.between(start_dt, end_dt)
        ).order_by(HeartData.timestamp).all()
    else:
        # 默认返回24小时数据
        start_dt = datetime.now() - timedelta(hours=24)
        records = HeartData.query.filter(
            HeartData.uid == uid,
            HeartData.timestamp >= start_dt
        ).order_by(HeartData.timestamp).all()
    
    data = [{
        'timestamp': r.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
        'heart_rate': r.heart_rate
    } for r in records]
    
    return jsonify({
        'code': 20000,
        'message': 'success',
        'data': {
            'uid': str(uid),
            'data': data
        }
    })


@app.route('/api/history/hr/getHrvData', methods=['POST'])
def get_hrv_data():
    """获取HRV数据 - 返回最近200条HRV记录的SDNN值"""
    params = request.get_json()
    uid = int(params.get('uid', 0))
    
    # 获取最近200条HRV记录
    hrv_records = HRVData.query.filter_by(uid=uid).order_by(
        HRVData.timestamp.desc()
    ).limit(200).all()
    
    if hrv_records:
        # 反转使时间升序
        hrv_records.reverse()
        
        # 提取SDNN值和时间戳
        hrv_data = [r.hrv_value for r in hrv_records]
        time_stamps = [r.timestamp.timestamp() for r in hrv_records]
        is_in_bed = True  # 可以从最新的heart_data获取
        
        return jsonify({
            'code': 20000,
            'message': 'success',
            'data': {
                'uid': str(uid),
                'is_in_bed': is_in_bed,
                'time_stamp': time_stamps,
                'hrv_data': hrv_data
            }
        })
    else:
        # 如果没有HRV数据，返回空数组
        return jsonify({
            'code': 20000,
            'message': 'success',
            'data': {
                'uid': str(uid),
                'is_in_bed': True,
                'time_stamp': [],
                'hrv_data': []
            }
        })


@app.route('/api/history/hr/stat', methods=['POST'])
def get_heart_stat():
    """获取心率统计数据"""
    params = request.get_json()
    uid = int(params.get('uid', 0))
    
    # 获取今天的心率统计
    today = datetime.now().date()
    stat = HeartStats.query.filter_by(uid=uid, date=today).first()
    
    if stat:
        return jsonify({
            'code': 20000,
            'message': 'success',
            'data': {
                'uid': str(uid),
                'avg_heart_rate': stat.avg_heart_rate,
                'max_heart_rate': stat.max_heart_rate,
                'min_heart_rate': stat.min_heart_rate,
                'date': stat.date.strftime('%Y-%m-%d')
            }
        })
    else:
        return jsonify({'code': 40000, 'message': '数据不存在'}), 404


@app.route('/api/history/arr/arr_count_list', methods=['POST'])
def get_arr_count_list():
    """获取心律失常统计列表"""
    params = request.get_json()
    uid = int(params.get('uid', 0))
    
    # 获取最近7天的心律失常统计
    start_date = datetime.now().date() - timedelta(days=7)
    records = ArrhythmiaCount.query.filter(
        ArrhythmiaCount.uid == uid,
        ArrhythmiaCount.date >= start_date
    ).order_by(ArrhythmiaCount.date).all()
    
    arr_counts = [{
        'date': r.date.strftime('%Y-%m-%d'),
        'count': r.count
    } for r in records]
    
    total = sum(r.count for r in records)
    
    return jsonify({
        'code': 20000,
        'message': 'success',
        'data': {
            'uid': str(uid),
            'arr_counts': arr_counts,
            'total_count': total
        }
    })


# ==================== 健康检查 ====================

@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查接口"""
    return jsonify({
        'code': 20000,
        'message': 'OK',
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
