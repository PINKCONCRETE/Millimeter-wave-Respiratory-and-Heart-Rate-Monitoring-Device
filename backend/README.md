# Backend API Server

这是一个基于Flask和SQLAlchemy的后端应用，用于响应前端的毫米波呼吸和心率监测请求。

## 环境要求

- Python 3.12+ (使用conda环境 `breath`)
- Flask 3.0.0
- Flask-CORS 4.0.0
- Flask-SQLAlchemy 3.1.1
- NumPy 1.26.0

## 安装依赖

在breath conda环境中运行：

```bash
conda activate breath
cd backend
pip install -r requirements.txt
```

## 初始化数据库

首次运行前需要初始化数据库并插入示例数据：

```bash
python init_db.py
```

这将在 `database/mmw_monitor.db` 创建SQLite数据库并插入测试数据。

## 运行服务器

```bash
conda activate breath
python app.py
```

服务器将在 `http://localhost:5000` 启动。

## API端点

### 呼吸相关
- `GET /br/getWaveform/uid/<uid>` - 获取呼吸波形数据（2000个点）
- `GET /br/getRing/uid/<uid>` - 获取呼吸环形图数据（2000个点）
- `GET /br/getWarning/uid/<uid>` - 获取呼吸警告信息

### 心率相关
- `GET /arr/getWaveform/uid/<uid>` - 获取心律波形数据（1000个点）
- `GET /hr/getWaveform/uid/<uid>` - 获取心率波形数据（1000个点）
- `GET /hr/getOneWave/uid/<uid>` - 获取最新心率数据
- `GET /hr/getStress/uid/<uid>` - 获取压力指数

### 历史数据
- `POST /history/br/getBrData` - 获取呼吸历史数据
- `POST /history/br/index` - 获取呼吸指数
- `POST /history/hr/getHeartData` - 获取心率历史数据
- `POST /history/hr/getHrvData` - 获取HRV数据
- `POST /history/hr/stat` - 获取心率统计
- `POST /history/arr/arr_count_list` - 获取心律失常统计

## 数据格式

所有波形数据直接以数值数组格式返回（简单的浮点数数组）。

数据存储在SQLite数据库中（`database/mmw_monitor.db`），使用SQLAlchemy ORM管理。

### 数据库表结构

- `user_info`: 用户信息
- `user_waveform`: 实时波形数据（呼吸、心律、心率波形）
- `breath_data`: 呼吸历史数据
- `heart_data`: 心率历史数据
- `hrv_data`: HRV数据
- `heart_stats`: 心率统计
- `arrhythmia_count`: 心律失常统计
- `breath_index`: 呼吸指数
- `stress_data`: 压力数据

默认创建uid=0的测试用户，包含24小时的历史数据和实时波形数据。
