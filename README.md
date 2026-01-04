# 毫米波呼吸与心率监测装置

这是一个基于毫米波雷达的非接触式生命体征监测系统，用于实时监测呼吸、心率和HRV（心率变异性）数据。系统包括后端数据处理（Python）和前端可视化（Vue/Electron）。

## 功能特性

*   **SCG (Seismocardiogram) 监测**: 实时显示心震图波形。
*   **呼吸监测**: 实时显示呼吸波形和呼吸率。
*   **心率监测**: 实时显示心率变化趋势。
*   **HRV 分析**: 实时计算并显示 SDNN 等 HRV 指标。
*   **状态检测**: 自动检测人体是否在监测范围内（状态：正常/离开）。
*   **可视化界面**: 
    *   支持网格布局 (2x2 Grid) 和聚焦模式 (1+3 Focus)。
    *   支持卡片拖拽排序。
    *   图表支持缩放、Y轴自动/手动调整。
    *   SCG 图表支持阈值限制和过滤。

## 系统架构

*   **后端**: Python
    *   负责读取毫米波雷达数据（或模拟数据）。
    *   进行信号处理（呼吸提取、心率计算、HRV分析）。
    *   通过 WebSocket/IPC 发送数据到前端。
*   **前端**: Vue 3 + TypeScript + Element Plus + ECharts
    *   实时数据可视化。
    *   用户交互界面。
    *   Electron 容器（可选，用于桌面应用封装）。

## 快速开始

### 1. 环境准备

*   Python 3.8+
*   Node.js 16+
*   npm 或 yarn

### 2. 启动后端

进入项目根目录（或后端源码目录）：

```bash
# 安装依赖 (如果尚未安装)
pip install -r requirements.txt

# 启动后端服务
python src/main.py
```

### 3. 启动前端

进入前端目录：

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

## 使用说明

1.  **布局切换**: 点击顶部的 "2x2 Grid" 或 "1+3 Focus" 按钮切换布局模式。
2.  **卡片排序**: 拖拽卡片头部可以调整卡片位置。点击卡片可将其设为焦点（在 Focus 模式下）。
3.  **图表控制**:
    *   **窗口大小**: 在 SCG 和呼吸卡片中，可以调整显示的时间窗口大小（秒）。
    *   **Y轴控制**: 可以开启 "Auto" 自动缩放，或手动设置 Y 轴的最小值和最大值。
    *   **SCG 限制**: 在 SCG 卡片中，开启 "Limit" 开关可以设置波形幅值的过滤范围。
4.  **状态指示**: 每个卡片右上角显示当前状态（正常/离开）和帧率 (FPS)。

## 目录结构

*   `src/`: 后端源代码
    *   `mmw_breath.py`: 呼吸信号处理
    *   `mmw_heart_rate.py`: 心率和 HRV 计算
    *   `mmw_scg_grade.py`: SCG 信号处理
    *   `heart_rate_processor.py`: 心率处理核心逻辑
*   `frontend/`: 前端源代码
    *   `src/components/`: Vue 组件 (SCGCard, BreathCard, HeartRateCard, HRVCard)
    *   `src/utils/ipc.ts`: 前后端通信接口定义
    *   `src/App.vue`: 主应用布局

## 注意事项

*   确保后端服务已启动并正确连接到雷达设备（或使用模拟数据模式）。
*   前端默认连接本地后端服务。
