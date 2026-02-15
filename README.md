# QWire Mock

Python 项目，基于 PyPI 标准布局。

## 环境要求

- Python 3.9+

## 安装

在项目根目录下创建虚拟环境并安装（可编辑模式）：

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
```

安装开发依赖（测试、代码检查等）：

```bash
pip install -e ".[dev]"
```

## 使用

以模块方式运行：

```bash
python -m qwire_mock
```

或在代码中导入：

```python
from qwire_mock import __version__
```

## 项目结构

```
QWireMock/
├── pyproject.toml      # 项目配置与依赖
├── requirements.txt    # 生产依赖列表（可选）
├── README.md
├── src/
│   └── qwire_mock/     # 主包
│       ├── __init__.py
│       └── __main__.py
└── tests/              # 测试（可后续添加）
```

## 开发

- 运行测试：`pytest`
- 代码检查：`ruff check src tests`
