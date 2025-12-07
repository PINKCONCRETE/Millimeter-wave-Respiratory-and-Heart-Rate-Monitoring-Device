@echo off
REM 毫米波监测系统启动脚本 (Windows)

echo ========================================
echo 毫米波监测系统启动脚本
echo ========================================
echo.

REM 检查Python环境
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到Python，请先安装Python 3.8+
    pause
    exit /b 1
)

REM 激活conda环境（如果有）
if exist "%USERPROFILE%\anaconda3\Scripts\activate.bat" (
    echo [提示] 激活conda环境: breath
    call "%USERPROFILE%\anaconda3\Scripts\activate.bat" breath
)

REM 设置参数（可根据需要修改）
set UID=0
set PORT=COM7
set BAUDRATE=921600

echo.
echo 启动参数:
echo - 用户ID: %UID%
echo - 串口: %PORT%
echo - 波特率: %BAUDRATE%
echo.
echo 按 Ctrl+C 停止系统
echo ========================================
echo.

REM 启动系统
python src\run_pipeline.py --uid %UID% --port %PORT% --baudrate %BAUDRATE% --duration 0

pause
