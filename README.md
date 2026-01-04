<div align="center">
  <h1>Millimeter-wave Respiratory and Heart Rate Monitoring Device</h1>
  <h1>毫米波非接触式生命体征监测系统</h1>

  <p>
    <a href="#-功能特性">功能特性</a> •
    <a href="#-系统架构">系统架构</a> •
    <a href="#-快速开始">快速开始</a> •
    <a href="#-使用指南">使用指南</a> •
    <a href="#-开源协议">开源协议</a>
  </p>

  <p>
    <img src="https://img.shields.io/badge/python-3.8+-blue.svg?style=flat-square&logo=python&logoColor=white" alt="Python" />
    <img src="https://img.shields.io/badge/vue-3.x-4FC08D.svg?style=flat-square&logo=vue.js&logoColor=white" alt="Vue" />
    <img src="https://img.shields.io/badge/electron-28.x-47848F.svg?style=flat-square&logo=electron&logoColor=white" alt="Electron" />
    <img src="https://img.shields.io/badge/license-MIT-green.svg?style=flat-square" alt="License" />
    <img src="https://img.shields.io/badge/platform-win-lightgrey.svg?style=flat-square" alt="Platform" />
  </p>
</div>

---

## 📖 简介

**毫米波生命体征监测系统 (Millimeter-wave Monitoring Device)** 是一个新一代的非接触式生理信号监测平台。它利用调频连续波 (FMCW) 雷达技术，通过捕捉人体胸壁微米级的微小位移，实现无感知的 **心震图 (SCG)**、**呼吸波形** 以及 **心率** 监测。

本项目采用前后端分离架构，集成了 **Python 后端** 用于复杂的数字信号处理（卡尔曼滤波、FFT、峰值检测），以及现代化的 **Vue 3 + Electron 前端** 用于医疗级的实时数据可视化。该系统非常适合应用于智慧养老、睡眠监测以及临床科研等场景。

## ✨ 功能特性

- **📡 非接触式感知**: 基于毫米波雷达技术，在 0.5m - 2m 范围内无需佩戴任何设备即可监测。
- **💓 SCG 心震图分析**: 实时提取并可视化心震图波形，提供更丰富的心脏机械活动信息。
- **🫁 呼吸追踪**: 实时监测呼吸波形、呼吸率，并支持呼吸暂停事件检测。
- **📊 高精度心率**: 采用 **卡尔曼滤波 (Kalman Filter)** 算法平滑心率数据，并支持 HRV (SDNN) 分析。
- **🛡️ 智能状态检测**:
  - **在床/离床检测**: 自动识别用户是否在监测范围内。
  - **异常报警**: 实时检测并标记异常的生命体征数据。
- **🖥️ 交互式仪表盘**:
  - **灵活布局**: 支持 `2x2 网格` 和 `1+3 聚焦` 两种视图模式，适应不同监控需求。
  - **拖拽交互**: 支持卡片拖拽排序，自定义个性化界面。
  - **深度分析**: 支持波形 Y 轴自动/手动缩放，以及 SCG 信号质量阈值过滤。

## 🏗 系统架构

本系统采用高性能的模块化架构设计：

```mermaid
graph TD
    A[TI AWR1843 雷达] -->|UART 串口| B(Python 后端)
    subgraph Backend [后端服务]
        B --> C{数据处理管线}
        C -->|FFT/峰值检测| D[呼吸 & 心率算法]
        C -->|信号质量评估| E[SCG 分析模块]
        D --> F[SQLite 数据库]
        E --> F
    end
    B -->|IPC (Named Pipes)| G(Electron 前端)
    subgraph Frontend [可视化界面]
        G --> H[Vue 3 组件库]
        H --> I[ECharts 实时渲染]
        H --> J[状态管理]
    end
```

## 🚀 快速开始

### 环境要求

- **硬件**: 毫米波雷达开发板。
- **操作系统**: Windows 10/11 (TI 驱动程序兼容性要求)。
- **运行环境**:
  - Python 3.8+
  - Node.js 16+

### 安装步骤

1.  **克隆项目代码**
    ```bash
    git clone https://github.com/yourusername/mmw-monitoring-device.git
    cd mmw-monitoring-device
    ```

2.  **后端环境配置**
    ```bash
    # 安装 Python 依赖
    pip install -r requirements.txt
    ```

3.  **前端环境配置**
    ```bash
    cd frontend
    # 安装 Node.js 依赖
    npm install
    ```

## 🖥 使用指南

### 1. 启动后端服务
后端服务负责与雷达通信并进行数据处理。
```bash
# 在项目根目录下运行
python src/main_process.py
```

### 2. 启动前端应用
前端提供实时数据可视化界面。
*   确保后端服务已启动并正确连接到雷达设备。
*   前端默认连接本地后端服务。
```bash
cd frontend
# 开发模式运行 (浏览器访问)
npm run dev

# 或者：作为桌面应用运行
npm run electron:dev
```

### 3. 仪表盘操作
- **布局切换**: 点击右上角的按钮在 **Grid (网格)** 和 **Focus (聚焦)** 视图之间切换。
- **聚焦模式**: 点击任意卡片（如 SCG、呼吸、心率），将其放大至主视图区域。
- **Y轴控制**: 点击卡片上的 `Auto` 按钮开启自动缩放，或手动输入 `Min/Max` 值以固定坐标轴范围，便于稳定观察。

## 📂 项目结构

```text
.
├── firmware/           # 雷达固件镜像 (AWR1843)
├── frontend/           # Vue 3 + Electron 前端应用
│   ├── electron/       # Electron 主进程与预加载脚本
│   │   ├── main.js     # Electron 入口
│   │   └── preload.js  # 预加载脚本 (IPC 安全桥接)
│   └── src/
│       ├── components/ # 可视化组件 (SCGCard, BreathCard 等)
│       ├── utils/      # 前端工具库 (IPC 通信封装)
│       ├── App.vue     # 应用根组件
│       └── main.ts     # Vue 入口文件
├── hardware/           # 外壳 3D 打印模型与 CAD 文件
├── src/                # Python 后端源代码
│   ├── main_process.py # 程序入口 (多进程管理)
│   ├── config.py       # 系统配置文件
│   ├── mmw_radar.py    # 雷达串口通信接口
│   ├── mmw_breath.py   # 呼吸信号处理算法
│   ├── mmw_heart_rate.py # 心率与 HRV 计算
│   ├── mmw_human_check.py # 人体存在与体动检测
│   ├── mmw_scg_grade.py# SCG 信号评分与分析
│   ├── mmw_database.py # 数据库读写操作封装
│   ├── models.py       # SQLite 数据库模型定义
│   ├── ipc_worker.py   # 进程间通信 (IPC) 核心逻辑
│   └── utils.py        # 通用工具函数
└── requirements.txt    # Python 依赖列表
```

## 🤝 参与贡献

欢迎提交 Issue 或 Pull Request 来改进本项目！

## 📄 开源协议

本项目采用 MIT 协议开源。详情请参阅 [LICENSE](LICENSE) 文件。
