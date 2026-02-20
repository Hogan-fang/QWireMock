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

先激活虚拟环境：

```bash
source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

以模块方式运行（默认同时启动 callback + order 两个服务）：

```bash
python -m qwire_mock
```

按服务单独启动：

```bash
# 仅启动 callback（默认端口 8000）
python -m qwire_mock --service callback

# 仅启动 order（默认端口 9000）
python -m qwire_mock --service order

# 同时启动 callback + order（默认）
python -m qwire_mock --service all
```

指定监听地址：

```bash
python -m qwire_mock --host 127.0.0.1 --service order
```

默认地址与端口：

- callback: `http://0.0.0.0:8000`
- order: `http://0.0.0.0:9000`

日志文件：

- `callback.log`：callback 服务日志
- `order.log`：order 服务日志（含请求/响应报文与 callback 通知日志）

停止服务：

- 在终端按 `Ctrl+C` 退出；退出码 `130` 属于手动中断，属于正常现象。

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

## 备注（Comments）

- 本项目用于 Mock 联调与测试，默认日志会记录完整请求/响应报文。
- 订单查询异常统一返回业务结构（`status` + `fail_reason`），不使用 FastAPI 默认 `detail` 结构。
- 手动停止服务（`Ctrl+C`）时退出码为 `130`，属于正常现象。

---

## Order 服务功能说明

本文档为 `order_server.yaml` 接口说明的补充，说明 Order 服务的行为细节、各类返回 status、UUID 校验与错误情况。

### 1. 服务概述

Order 服务提供：**创建订单**（POST /order）与**按 reference 查询订单**（GET /order）。订单数据持久化到 MySQL；订单与子表 order_products 存在状态与定时更新（如 30s/60s 产品状态推进）。

### 2. 状态模型说明

#### 2.1 订单状态

- 接口返回的订单 `status` 均为**大写**。
- 取值含义：
  - **PROCESSING**：订单处理中（新建或进行中）。
  - **FAIL**：订单失败（如无效卡、业务拒绝等）。
  - **COMPLETE**：订单及下属产品均已完成。
- 成功创建订单时返回 `status = PROCESSING`；卡号以 4 开头等无效卡返回 400 且 body 中 `status = FAIL`；重复 reference 返回 400 时，body 中的 `status` 保持已存在订单的真实状态（不改为 FAIL）。

#### 2.2 产品状态

- 产品行 `status` 也为**大写**，由定时任务或业务逻辑更新。
- 常见取值：**PENDING**（待处理）→ **SHIPPED**（已发货）→ **COMPLETE**（已完成）；具体以 order_db 的定时逻辑为准（如创建后约 30s 变为 shipped，约 60s 变为 complete）。

### 3. 回调（callback）说明

创建订单时请求体中需提供 `callback`，为回调地址（URI）。  
本 Mock 的 Order 服务**仅存储该地址，不会主动向 callback 发起 HTTP 请求**。具体何时、由谁向该地址发起回调，由实际部署或上游系统决定；若与项目中的 Callback 服务配合，通常由外部或集成层在订单/产品状态变化时向 Callback 服务 POST 推送订单数据。

### 4. 返回中的 fail_reason

Order 响应（OrderResponse）中的 `fail_reason` 仅在订单状态为 **FAIL** 时才有意义；成功或处理中的订单不应暴露失败原因。

- **POST /order 成功（201）**：响应中**不包含** `fail_reason` 字段。
- **GET /order**：仅当该订单的 `status` 为 FAIL 时，响应中才包含 `fail_reason`；当 `fail_reason` 为空时，响应中会去掉该字段，不返回 `"fail_reason": null`。  
因此：只有查询到的是**失败订单**时，响应里才会出现 `fail_reason`；其他情况响应中不出现该字段。

### 5. 各场景下的 status 取值（补充）

- **POST /order 成功**：订单 `status = PROCESSING`，产品行 `status = PENDING`。
- **POST /order 无效卡**：400，body 中 `status = FAIL`，`fail_reason = "Invalid card"`。
- **POST /order 订单已存在**：400，`status = FAIL`，`fail_reason = "Order already exists"`，body 中其余为已存在订单信息。
- **GET /order 查到订单**：200，body 中 `status` 为库中订单状态的大写（PROCESSING / FAIL / COMPLETE 等）。

### 6. UUID 校验与无效 reference

GET /order 的查询参数 **reference 必须是合法 UUID 字符串**；服务会用 `UUID(reference)` 做校验。

- **reference 不是合法 UUID**（格式错误、非 UUID 字符串）：返回 **400**，body 为  
  `{"reference": "<原始入参>", "status": "FAIL", "fail_reason": "invalid UUID string"}`；不返回 FastAPI 校验产生的 `detail` 等嵌套结构。
- **reference 为合法 UUID 但订单不存在**：返回 **400**，body 为 `{"reference": "<原始入参>", "status": "FAIL", "fail_reason": "Order not found"}`。

### 7. 错误与 400 情况汇总

| 情况 | HTTP | 说明 |
|------|------|------|
| 无效卡（卡号以 4 开头） | 400 | `status=FAIL`，`fail_reason="Invalid card"` |
| 订单已存在（重复 reference） | 400 | `status=FAIL`，`fail_reason="Order already exists"`，其余为已存在订单信息 |
| GET reference 非合法 UUID | 400 | `reference=<原始入参>`，`status=FAIL`，`fail_reason="invalid UUID string"` |
| GET reference 合法但订单不存在 | 400 | `reference=<原始入参>`，`status=FAIL`，`fail_reason="Order not found"` |

以上 400 响应统一为同一结构：仅包含 `status` 与 `fail_reason`，无 `detail` 或嵌套对象。

### 8. 其他说明

- 响应中的卡号为**掩码**：仅保留前 6 位与后 4 位，中间用 `*` 代替；不返回 CVV、expiry。
- 订单 ID（`orderId`）格式为 **PX + 数据库自增 id**，由服务生成并返回。
