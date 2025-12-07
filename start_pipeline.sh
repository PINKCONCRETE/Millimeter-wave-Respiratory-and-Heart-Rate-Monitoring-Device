#!/bin/bash
# 毫米波监测系统启动脚本 (Linux/macOS)

echo "========================================"
echo "毫米波监测系统启动脚本"
echo "========================================"
echo ""

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "[错误] 未找到Python，请先安装Python 3.8+"
    exit 1
fi

# 激活虚拟环境（如果有）
if [ -d "venv" ]; then
    echo "[提示] 激活虚拟环境"
    source venv/bin/activate
fi

# 设置参数（可根据需要修改）
UID=0
PORT="/dev/ttyUSB0"  # Linux下通常是 /dev/ttyUSB0 或 /dev/ttyACM0
BAUDRATE=921600

echo ""
echo "启动参数:"
echo "- 用户ID: $UID"
echo "- 串口: $PORT"
echo "- 波特率: $BAUDRATE"
echo ""
echo "按 Ctrl+C 停止系统"
echo "========================================"
echo ""

# 启动系统
python3 src/run_pipeline.py --uid $UID --port $PORT --baudrate $BAUDRATE
