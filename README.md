# Price Monitor

基于 Python 的价格监控与邮件告警工具，用于定时拉取上游和站点的价格数据，自动对比差异，并在发现站点价格低于上游时发送邮件通知。

## 功能

- 定时监控上游价格接口，按固定周期检查价格变动
- 拉取站点价格并与上游价格进行对比
- 检测模型价格、分组倍率、可用分组等关键字段是否异常
- 支持 `billing_expr` 表达式对比，判断站点定价是否低于上游
- 将价格快照保存到本地 JSON 文件，便于后续比对
- 通过 SMTP 发送邮件告警
- 生成 HTML 格式的变动报告，便于直接阅读

## 项目结构

```text
main.py                 # 程序入口，启动定时任务
src/config.py           # 环境变量与配置
src/monitor/            # 价格拉取与对比逻辑
src/store/json.py       # 本地 JSON 存储
src/remind/sender.py    # 邮件发送
```

## 依赖环境

- Python 3.12+
- 可访问的上游价格接口和站点价格接口
- SMTP 邮箱服务，用于发送告警邮件

## 配置说明

项目通过环境变量进行配置，建议在项目根目录创建 `.env` 文件。

### 必填配置

```env
UPSTREAM_URL=https://example.com
UPSTREAM_TOKEN=your_upstream_token
STATION_URL=https://example.com
STATION_TOKEN=your_station_token
SMTP_HOST=smtp.qq.com
SMTP_PORT=465
SMTP_USER=your_email@example.com
SMTP_PASSWORD=your_smtp_password
```

### 可选配置

```env
SMTP_FROM=your_email@example.com
WARNING_EMAIL=a@example.com,b@example.com
PERIOD=86400
```

### 配置项说明

- `UPSTREAM_URL`：上游接口地址
- `UPSTREAM_TOKEN`：上游接口访问令牌
- `STATION_URL`：站点接口地址
- `STATION_TOKEN`：站点接口访问令牌
- `SMTP_HOST`：SMTP 服务器地址
- `SMTP_PORT`：SMTP 端口，默认 `465`
- `SMTP_USER`：SMTP 用户名
- `SMTP_PASSWORD`：SMTP 密码或授权码
- `SMTP_FROM`：发件人地址，不填则默认使用 `SMTP_USER`
- `WARNING_EMAIL`：告警接收邮箱，多个地址用英文逗号或分号分隔
- `PERIOD`：监控周期，单位为秒，默认 `86400`（1 天）

## 安装

建议使用虚拟环境安装依赖：

```bash
python -m venv .venv
source .venv/bin/activate  # Windows 下使用 .venv\Scripts\activate
pip install -r requirements.txt
```

## 运行方式

配置好 `.env` 后，直接启动主程序：

```bash
python main.py
```

程序启动后会：

1. 初始化本地数据目录和日志目录
2. 按 `PERIOD` 设定的周期定时执行监控任务
3. 获取上游价格并保存快照
4. 与站点价格进行对比
5. 如发现异常则发送邮件提醒

## 数据与日志

- 价格快照默认保存到 `data/`
- 日志默认保存到 `logs/app.log`

## 部署建议

### 本地/服务器直接部署

1. 拉取代码并创建虚拟环境
2. 安装依赖
3. 配置 `.env`
4. 执行 `python main.py`
5. 使用 `systemd`、任务计划程序或守护进程工具保持进程常驻

### Docker 部署

如果你希望容器化部署，可以将项目打包为 Docker 镜像后运行。容器启动时需要注入上述环境变量，并挂载 `data/` 与 `logs/` 目录以持久化数据和日志。

## 注意事项

- 站点与上游接口必须可正常访问
- `SMTP_PASSWORD` 通常需要使用邮箱授权码，而不是登录密码
- 如果未配置 `WARNING_EMAIL`，程序仍会运行，但不会发送邮件

## 许可证

[Apache License
Version 2.0](./LICENSE)