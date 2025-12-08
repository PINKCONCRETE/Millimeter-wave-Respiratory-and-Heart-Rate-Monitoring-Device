# 毫米波无感健康检测系统 (MMW-SYS-MOBILE)
基于毫米波技术的无接触式健康监测系统移动端应用，实时监测心率、呼吸、心律失常和心率变异性等生理指标。

## 🏥 项目简介

本项目是一个基于Vue 3 + TypeScript + Vite的现代化健康监测前端应用，通过毫米波传感器技术实现无接触式生理指标监测。系统提供实时数据可视化、多种显示模式和智能预警功能。

## ✨ 主要功能

- **心律失常监测** - 实时心电波形显示和异常检测
- **心率监测** - 连续心率数据采集和趋势分析
- **呼吸监测** - 呼吸波形、频率和模式分析
- **心率变异性(HRV)** - 自主神经功能评估
- **智能预警** - 异常状态实时提醒
- **多种显示模式** - 2x2网格模式和1+3主从模式
- **在床检测** - 自动识别用户是否在监测范围内

## 🛠️ 技术栈
- **Vue 3.5.17** - 渐进式JavaScript框架
- **TypeScript** - 类型安全的JavaScript超集
- **Vite 7.0** - 快速的前端构建工具

## 📁 项目结构

```
mmw-sys-mobile/
├── public/                 # 静态资源
│   ├── bg.jpg             # 背景图片
│   ├── arr_images/        # 箭头图标
│   └── breath_imgs/       # 呼吸相关图标
├── src/
│   ├── api/               # API接口
│   │   ├── breath.ts      # 呼吸监测API
│   │   ├── heart.ts       # 心率监测API
│   │   └── history.ts     # 历史数据API
│   ├── components/        # 组件
│   │   ├── BreathMonitor.vue      # 呼吸监测组件
│   │   ├── HeartbeatMonitor.vue   # 心律监测组件
│   │   ├── HeartrateMonitor.vue   # 心率监测组件
│   │   └── HRVMonitor.vue         # 心率变异性组件
│   ├── router/            # 路由配置
│   ├── store/             # 状态管理
│   ├── utils/             # 工具函数
│   │   ├── auth.ts        # 认证工具
│   │   ├── echarts.ts     # 图表工具
│   │   ├── request.ts     # 请求封装
│   │   └── mocks/         # Mock数据
│   └── views/             # 页面
│       ├── Monitor.vue    # 主监测页面
│       └── 404.vue        # 404页面
├── eslint.config.ts       # ESLint配置
├── vite.config.ts         # Vite配置
└── package.json           # 项目依赖
```