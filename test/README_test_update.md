# 数据库更新测试工具

用于测试前端实时刷新功能的数据更新脚本。

## 功能

- 更新呼吸波形数据
- 更新心率波形数据  
- 添加新的呼吸历史记录
- 添加新的心率历史记录

## 使用方法

### 快速测试（单次更新）

```bash
conda activate breath
cd test
python test_update_data.py --mode quick
```

这将执行一次性更新所有数据，用于快速验证前端是否能接收到更新。

### 持续更新模式

```bash
# 默认：每2秒更新一次，持续60秒
python test_update_data.py --mode continuous

# 自定义间隔和时长
python test_update_data.py --mode continuous --interval 5 --duration 120

# 无限运行（按Ctrl+C停止）
python test_update_data.py --mode continuous --interval 3 --duration 0
```

## 参数说明

- `--mode`: 运行模式
  - `quick`: 快速测试，单次更新所有数据
  - `continuous`: 持续更新模式

- `--interval`: 更新间隔（秒），默认2秒（仅continuous模式）

- `--duration`: 运行时长（秒），0表示无限运行，默认60秒（仅continuous模式）

## 测试建议

1. 启动Flask后端服务器：
   ```bash
   cd backend
   conda activate breath
   python app.py
   ```

2. 打开前端页面

3. 运行测试脚本：
   ```bash
   cd test
   python test_update_data.py --mode continuous --interval 2
   ```

4. 观察前端页面是否实时更新数据

## 更新内容

每次更新会修改：
- 呼吸波形（200个点）
- 呼吸环形图（X/Y各1000个点）
- 心率波形（200个点）
- SCG波形（1000个点）
- 添加新的呼吸记录（呼吸率12-20）
- 添加新的心率记录（心率60-100）
