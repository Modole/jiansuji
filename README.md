# 谐波减速机测试系统

一个基于Flask和Node-RED的谐波减速机测试数据采集与分析系统。

## 项目结构

```
jiansuji/
├── app/                    # Flask应用主目录
│   ├── __init__.py        # 应用工厂
│   ├── config.py          # 配置管理
│   ├── api/               # API蓝图
│   │   ├── data.py        # 数据相关API
│   │   ├── command.py     # 命令相关API
│   │   └── export.py      # 导出相关API
│   ├── models/            # 数据模型
│   │   ├── measurement.py # 测量数据模型
│   │   └── hysteresis.py  # 磁滞回线模型
│   ├── services/          # 业务逻辑层
│   │   ├── data_service.py    # 数据服务
│   │   └── node_red_service.py # Node-RED服务
│   ├── utils/             # 工具函数
│   │   ├── database.py    # 数据库工具
│   │   └── helpers.py     # 辅助函数
│   └── static/            # 静态资源
│       ├── js/            # JavaScript文件
│       ├── css/           # CSS样式文件
│       ├── config/        # 前端配置文件
│       └── templates/     # HTML模板
├── data/                  # 数据目录
│   ├── database/          # 数据库文件
│   └── exports/           # 导出文件
├── tests/                 # 测试文件
├── migrations/            # 数据库迁移脚本
├── docs/                  # 文档
├── requirements.txt       # Python依赖
├── .env.example          # 环境变量示例
└── run.py                # 应用入口
```

## 功能特性

- **数据采集**: 通过Node-RED采集测试数据
- **实时监控**: 实时显示测试状态和数据
- **数据存储**: SQLite数据库存储测量数据和磁滞回线
- **数据导出**: 支持CSV、JSON格式数据导出
- **命令控制**: 向测试设备发送控制命令
- **磁滞回线**: 磁滞回线数据可视化
- **测试报告**: 生成完整的测试报告

## 快速开始

### 1. 环境准备

确保已安装Python 3.8+和Node-RED。

### 2. 安装依赖

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 3. 配置环境

```bash
# 复制环境变量文件
copy .env.example .env

# 编辑.env文件，配置相关参数
```

### 4. 初始化数据库

数据库会在首次运行时自动初始化。

### 5. 启动应用

```bash
python run.py
```

应用端口由 `FLASK_PORT` 控制，运行日志会显示服务地址。

## API接口

### 数据接口

- `GET /api/data/measurements` - 获取测量数据
- `POST /api/data/ingest` - 接收Node-RED数据
- `GET /api/data/hysteresis` - 获取磁滞回线数据
- `POST /api/data/hysteresis` - 保存磁滞回线数据
- `GET /api/data/stats` - 获取数据统计
- `GET /api/data/history/<key>` - 获取历史数据

### 命令接口

- `POST /api/command/set/data` - 发送命令
- `POST /api/command/batch` - 批量发送命令
- `GET /api/command/history` - 获取命令历史
- `GET /api/command/node-red/test` - 测试Node-RED连接

### 导出接口

- `GET /api/export/csv` - 导出CSV格式数据
- `GET /api/export/json` - 导出JSON格式数据
- `GET /api/export/report` - 导出完整测试报告

## 配置说明

主要配置项（在`.env`文件中设置）：

```bash
# Flask配置
FLASK_DEBUG=false
SECRET_KEY=your-secret-key

# 服务器配置
FLASK_HOST=0.0.0.0
FLASK_PORT=5000

# 数据库配置
DATABASE_PATH=data/database/measurements.db

# Node-RED配置
NODE_RED_BASE_URL=http://127.0.0.1:1880
NODE_RED_TIMEOUT=10

# 导出配置
EXPORT_DIR=data/exports
MAX_EXPORT_RECORDS=10000
```

## 测试

运行测试套件：

```bash
# 运行所有测试
pytest

# 运行特定测试文件
pytest tests/test_app.py

# 运行测试并生成覆盖率报告
pytest --cov=app tests/
```

## 开发

### 代码风格

项目使用以下工具保证代码质量：

```bash
# 代码格式化
black app/ tests/

# 代码检查
flake8 app/ tests/
```

### 添加新功能

1. 在相应的模块中添加功能代码
2. 在`tests/`目录中添加测试
3. 更新文档
4. 运行测试确保功能正常

## 部署

### 生产环境部署

1. 设置环境变量 `FLASK_ENV=production`
2. 使用WSGI服务器（如Gunicorn）运行应用
3. 配置反向代理（如Nginx）
4. 设置数据库备份策略

### Docker部署

```dockerfile
# Dockerfile示例
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 5000

CMD ["python", "run.py"]
```

## 故障排除

### 常见问题

1. **Node-RED连接失败**
   - 检查Node-RED是否运行在正确的端口
   - 验证网络连接和防火墙设置

2. **数据库错误**
   - 确保数据库目录存在且有写权限
   - 检查数据库文件是否损坏

3. **静态文件404**
   - 确保静态文件已正确复制到`app/static/`目录
   - 检查文件路径和权限

## 贡献

欢迎提交Issue和Pull Request来改进项目。

## 许可证

本项目采用MIT许可证。