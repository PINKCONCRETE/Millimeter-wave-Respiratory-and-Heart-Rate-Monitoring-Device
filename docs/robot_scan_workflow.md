# 机械臂毫米波扫描工作流

## 1. 目标拆解

你的最终目标可以拆成三步：

1. 机械臂沿人体纵向扫描，得到一组位置离散的毫米波原始字节数据。
2. 对每个位置解码出 `frame x channel x bin` 的复数数据，查看每个通道、每个 bin 的幅值和相位。
3. 在扫描结果中选择最适合的观测位置，再固定机械臂，做呼吸和 SCG 检测。

这一步已经通过脚本 `src/mmw_scan_analysis.py` 串起来了。

## 2. 数据处理链路

离线分析链路如下：

1. 读取原始采集文件 `timestamp, raw_bytes`
2. 用与 `src/mmw_radar.py` 相同的状态机协议解码串口字节
3. 组装完整 frame，得到形状为 `N x 8 x 10` 的复数立方体
4. 对每个 `channel/bin` 计算：
   - 幅值 `abs(I + jQ)`
   - 相位 `angle(I + jQ)`
   - 展开相位 `unwrap(angle(...))`
   - 呼吸分数
   - SCG 分数
5. 对每个扫描位置输出：
   - 全通道全 bin 的幅值/相位 CSV
   - 全通道全 bin 的统计摘要
   - 最优呼吸候选波形
   - 最优 SCG 候选波形
   - 位置级排名

## 3. 如何运行

在项目根目录执行：

```bash
python src/mmw_scan_analysis.py ^
  --input-dir data/wdh_4_21/wdh_4_21 ^
  --output-dir data/wdh_4_21/wdh_4_21/scan_analysis ^
  --position-step-cm 5 ^
  --position-start-cm 0
```

如果你当前数据的第 1 个文件不是“头部 0 cm”，只要改 `--position-start-cm` 即可。

## 4. 输出文件说明

脚本会在输出目录下生成：

- `position_XX/<源文件名>_complex_cube.npz`
  - 解码后的复数立方体，后续二次分析最方便。
- `position_XX/<源文件名>_amp_phase.csv`
  - 每一帧、每个通道、每个 bin 的幅值和相位。
- `position_XX/<源文件名>_channel_bin_summary.csv`
  - 每个通道/bin 的统计量、呼吸分数、SCG 分数。
- `position_XX/<源文件名>_best_resp_waveform.csv`
  - 该位置最优呼吸候选的原始相位、展开相位、处理后波形。
- `position_XX/<源文件名>_best_scg_waveform.csv`
  - 该位置最优 SCG 候选的原始相位、展开相位、处理后波形。
- `position_XX/<源文件名>_heatmaps.png`
  - 幅值均值、相位波动、呼吸分数、SCG 分数热力图。
- `summary/scan_summary.csv`
  - 每个机械臂位置的最佳呼吸/SCG 候选。
- `summary/scan_ranking.csv`
  - 按综合定位分数排序后的结果。
- `summary/scan_ranking.png`
  - 扫描位置级别的得分曲线。

## 5. 如何用这些结果做定位

建议按下面的两阶段方式做：

### 第一阶段：粗定位

让机械臂按 5 cm 步长扫完整个躯干区域。

看 `summary/scan_ranking.csv`：

- `best_resp_score` 高的位置，通常更接近胸腹呼吸主运动区。
- `best_scg_score` 高的位置，通常更接近心前区或胸骨附近。
- `combined_position_score` 高的位置，适合作为“同时兼顾呼吸和 SCG”的固定观测点。

### 第二阶段：精定位

选综合分数最高的前 2 到 3 个位置，再把机械臂在这些位置附近做更小步长扫描，比如 `1 cm` 或 `2 cm`。

精扫时仍然沿用同一套脚本，再从候选位置中选出最终固定点。

## 6. 呼吸和 SCG 的选点逻辑

### 呼吸

脚本对每个 `channel/bin` 的展开相位做：

1. 去趋势
2. `0.10 Hz - 0.60 Hz` 带通
3. 计算呼吸带内主峰能量与总体能量的比值

这个比值越高，说明该 `channel/bin` 更像呼吸观测点。

### SCG

脚本对每个 `channel/bin` 的展开相位做：

1. 七点二阶微分
2. `8 Hz - 35 Hz` 带通
3. 在 `40 - 150 bpm` 的自相关延迟区间内找最大周期性峰值

这个峰值越高，说明该 `channel/bin` 更像稳定的心机械振动观测点。

## 7. 建议的在线部署流程

当你后续把机械臂扫描和在线检测串起来时，建议流程是：

1. 机械臂执行粗扫描
2. 每个位置采集 8 到 12 秒数据
3. 用当前脚本离线或准实时打分
4. 选出最优位置
5. 机械臂回到最优位置并固定
6. 在线检测时优先使用：
   - 呼吸：该位置下 `best_resp_channel + best_resp_bin`
   - SCG：该位置下 `best_scg_channel + best_scg_bin`
7. 如果要进一步提稳，可以把相邻通道做相干叠加或加权融合

## 8. 当前假设

当前脚本默认：

- 文件顺序就是机械臂扫描顺序
- 第 1 个文件对应 `0 cm`
- 步长固定为 `5 cm`
- 采样率为 `200 Hz`
- 每帧为 `8` 通道、每通道 `10` 个 bin

如果你的实际采集条件不同，直接通过命令行参数改掉即可。
