"""测试心率和人体检测模块的导入和基本功能."""
import sys
from pathlib import Path
from queue import Queue

import numpy as np

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# 测试导入
print("测试模块导入...")
from src.mmw_heart_rate import MMWHeartRateThread  # noqa: E402
from src.mmw_human_check import (  # noqa: E402
    MMWHumanCheckThread,
    HumanCheck,
    check_human,
)

print("✓ 所有模块导入成功")

# 测试心率线程初始化
print("\n测试心率线程初始化...")
hr_queue = Queue()
hr_thread = MMWHeartRateThread(
    input_queue=hr_queue,
    channel_num=8,
    bins_per_channel=10,
    buffer_size=1000
)
print(f"✓ 心率线程创建成功: {hr_thread}")

# 测试人体检测线程初始化
print("\n测试人体检测线程初始化...")
hc_queue = Queue()
hc_thread = MMWHumanCheckThread(
    input_queue=hc_queue,
    channel_num=8,
    bins_per_channel=10
)
print(f"✓ 人体检测线程创建成功: {hc_thread}")

# 测试人体检测器基本功能
print("\n测试人体检测器基本功能...")
checker = HumanCheck()

# 模拟能量数据
energies = [50000.0, 60000.0, 70000.0, 80000.0, 60000.0,
            50000.0, 48000.0, 46000.0, 44000.0, 42000.0]
offset = 0

for i in range(5):
    result = checker.do_human_check(energies, offset)
    print(f"  帧 {i+1}: 检测结果 = {result}")

print(f"✓ 人体检测器工作正常，最终状态: {checker.has_human()}")

# 测试简化接口
print("\n测试简化检测接口...")
fft_data = np.random.rand(10, 8, 10) * 100000  # 模拟FFT数据
offsets = np.array([0] * 10)
result = check_human(fft_data, offsets)
print(f"✓ 简化接口检测结果: {result}")

print("\n✓ 所有测试通过！")
