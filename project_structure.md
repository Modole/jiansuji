# 谐波减速机测试系统 - 重构项目结构

## 新项目结构
```
jiansuji/
├── app/                          # Flask应用主目录
│   ├── __init__.py              # 应用工厂
│   ├── config.py                # 配置管理
│   ├── models/                  # 数据模型
│   │   ├── __init__.py
│   │   ├── measurement.py       # 测量数据模型
│   │   └── hysteresis.py        # 滞回曲线模型
│   ├── api/                     # API蓝图
│   │   ├── __init__.py
│   │   ├── data.py              # 数据相关API
│   │   ├── command.py           # 命令相关API
│   │   └── export.py            # 导出相关API
│   ├── services/                # 业务逻辑层
│   │   ├── __init__.py
│   │   ├── data_service.py      # 数据处理服务
│   │   ├── node_red_service.py  # Node-RED代理服务
│   │   └── export_service.py    # 导出服务
│   ├── utils/                   # 工具函数
│   │   ├── __init__.py
│   │   ├── database.py          # 数据库工具
│   │   └── helpers.py           # 通用工具
│   └── static/                  # 静态文件
│       ├── js/
│       │   ├── app.js           # 主应用逻辑
│       │   ├── charts.js        # 图表功能
│       │   └── export.js        # 导出功能
│       ├── css/
│       │   └── styles.css
│       ├── config/
│       │   ├── commands-mapping.json
│       │   └── points-mapping.json
│       └── templates/
│           └── index.html
├── migrations/                   # 数据库迁移
│   └── init_db.sql
├── tests/                       # 测试用例
│   ├── __init__.py
│   ├── test_api.py
│   └── test_services.py
├── docs/                        # 项目文档
│   ├── api.md
│   ├── deployment.md
│   └── 命令接口说明.md
├── data/                        # 数据文件
│   ├── database/
│   └── exports/
├── requirements.txt             # Python依赖
├── .env.example                 # 环境变量示例
├── run.py                       # 应用启动入口
└── README.md                    # 项目说明
```

## 重构原则

1. **单一职责**：每个模块只负责一个功能领域
2. **分层架构**：API层 → 服务层 → 数据层
3. **配置外化**：使用环境变量和配置文件
4. **错误处理**：统一的异常处理和日志记录
5. **可测试性**：模块化设计便于单元测试
6. **可维护性**：清晰的目录结构和命名规范

## 模块职责划分

- **models/**: 数据模型和数据库操作
- **api/**: RESTful API接口定义
- **services/**: 业务逻辑和外部服务集成
- **utils/**: 通用工具和辅助函数
- **static/**: 前端资源文件
- **tests/**: 自动化测试用例