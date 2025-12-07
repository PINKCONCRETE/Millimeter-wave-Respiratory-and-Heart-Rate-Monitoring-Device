# 毫米波监测系统 - 流水线使用指南

## 系统架构

完整的数据处理流水线包含以下模块：

```
[毫米波雷达] → [人体检测] → [呼吸处理] → [数据库]
                ↓            ↓
            [心率处理] → [数据库]
                ↓
            [SCG处理] → [数据库]
```

## 快速启动

### Windows系统

1. 双击运行 `start_pipeline.bat`
2. 或在命令行中执行：
```bash
python src\run_pipeline.py --uid 0 --port COM7 --baudrate 921600
```

### Linux/macOS系统

1. 添加执行权限并运行：
```bash
chmod +x start_pipeline.sh
./start_pipeline.sh
```

2. 或直接使用Python：
```bash
python3 src/run_pipeline.py --uid 0 --port /dev/ttyUSB0 --baudrate 921600
```

## 命令行参数

```bash
python src/run_pipeline.py [选项]

选项:
  --uid UID              用户ID (默认: 0)
  --port PORT            串口号 (默认: COM7)
  --baudrate BAUDRATE    波特率 (默认: 921600)
  --db PATH              数据库路径 (默认: database/mmw_monitor.db)
  --no-human-check       禁用人体存在检测
  -h, --help             显示帮助信息

### 2. `src/run_pipeline.py`
Pipeline主程序，启动所有处理线程并将数据实时写入数据库。

## 使用方法

### 基本用法

```bash
# 使用默认参数运行
python src/run_pipeline.py

# 指定串口和波特率
python src/run_pipeline.py --port COM7 --baudrate 921600

# 指定用户ID
python src/run_pipeline.py --user 1
```

### 参数说明

- `--port`: 串口号 (默认: COM7)
- `--baudrate`: 波特率 (默认: 921600)
- `--user`: 用户ID (默认: 1)

### 运行流程

1. **初始化数据库更新器** - 创建DatabaseUpdater实例
2. **创建队列** - 用于线程间通信
3. **启动线程**:
   - `MMWRadarThread` - 雷达数据采集
   - `MMWProcessorThread` - SCG处理
   - `MMWBreathThread` - 呼吸分析
   - `MMWHeartRateThread` - 心率分析
   - `MMWHumanCheckThread` - 人体检测
4. **运行监控** - 每10秒打印统计信息
5. **优雅退出** - Ctrl+C停止所有线程

### 输出示例

```
============================================================
毫米波雷达数据采集Pipeline
============================================================
串口: COM7
波特率: 921600
用户ID: 1
============================================================

初始化数据库更新器...
创建雷达数据采集线程...
创建SCG处理线程...
创建呼吸分析线程...
创建心率分析线程...
创建人体检测线程...

启动所有处理线程...
  ✓ MMWRadarThread 已启动
  ✓ MMWProcessorThread 已启动
  ✓ MMWBreathThread 已启动
  ✓ MMWHeartRateThread 已启动
  ✓ MMWHumanCheckThread 已启动

============================================================
Pipeline运行中... (按Ctrl+C停止)
============================================================

[统计信息] 2025-12-08 10:30:00
  呼吸波形缓冲: 150/200
  呼吸环缓冲: 500/2000
  心率波形缓冲: 180/200
  SCG波形缓冲: 800/1000
  人体检测缓冲: 900/1000
  回调计数 - 呼吸:150 心率:5 SCG:800 人体:900

[BreathWaveform] 已更新200个点到数据库
[HeartWaveform] 已更新200个点到数据库
[SCGWaveform] 已更新1000个点到数据库
[HeartData] 已更新心率数据 HR=75.3 bpm
```

## 测试

### 测试数据库更新器

```bash
# 运行测试脚本（不需要硬件）
python test/test_run_pipeline.py
```

这将使用模拟数据测试所有回调功能。

## 注意事项

1. **确保数据库已初始化**
   ```bash
   python backend/init_db.py
   ```

2. **确保Flask应用配置正确**
   - 检查 `backend/app.py` 中的数据库路径
   - 默认使用SQLite: `database/mmw_monitor.db`

3. **串口权限**
   - Windows: 确保COM端口可访问
   - Linux: 可能需要添加用户到dialout组

4. **线程安全**
   - 所有数据库操作都在Flask应用上下文中执行
   - 使用deque作为线程安全的缓冲区

## 架构图

```
┌─────────────────┐
│  MMWRadarThread │ (串口读取)
└────────┬────────┘
         │ Queue
         ├────────────────────────────────┐
         │                                │
         ▼                                ▼
┌──────────────────┐            ┌──────────────────┐
│ MMWProcessorThread│            │ MMWBreathThread  │
└────────┬─────────┘            └────────┬─────────┘
         │                               │
         │ scg_callback                  │ breath_callback
         │                               │
         ▼                               ▼
    ┌────────────────────────────────────────┐
    │         DatabaseUpdater                │
    │  - SCG缓冲区 (1000点)                  │
    │  - 呼吸波形缓冲区 (200点)              │
    │  - 呼吸环缓冲区 (2000点)               │
    │  - 心率波形缓冲区 (200点)              │
    │  - 人体检测缓冲区 (1000点)             │
    └────────────────┬───────────────────────┘
                     │
                     ▼
              ┌─────────────┐
              │   数据库    │
              │ (SQLite)    │
              └─────────────┘
```

## 故障排查

### 问题：串口连接失败
**解决方案：** 检查串口号和波特率是否正确，确认设备已连接

### 问题：数据库更新失败
**解决方案：** 检查数据库文件权限，确认数据库已正确初始化

### 问题：线程意外停止
**解决方案：** 查看错误日志，检查是否有未捕获的异常

### 问题：数据更新频率不符合预期
**解决方案：** 检查缓冲区大小配置，查看统计信息确认回调频率
