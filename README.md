# 东方财富掘金量化（gm.api）策略项目骨架

## 安装依赖
1. 创建并激活虚拟环境（可选）。
2. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```

## 填写 token 与 strategy_id
1. 打开 `macd_strategy.py`。
2. 在文件顶部找到 `GM_TOKEN` 与 `STRATEGY_ID`，填写你的值。

## 回测模式运行（步骤说明）
1. 确认已安装依赖并完成 token/strategy_id 填写。
2. 按照掘金量化官方回测方式配置回测参数（例如起止时间、标的等）。
3. 使用掘金量化提供的回测入口运行该脚本。
