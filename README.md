
# Bookstore API with RBAC

一个基于 **FastAPI** 的在线书店 API，实现了用户认证（JWT + Refresh Token）、基于角色的权限控制（RBAC）、作者与图书管理、用户管理（管理员）以及审计日志功能。

## 功能概要

- 用户注册、登录、Token 刷新、修改密码、忘记/重置密码
- 用户角色：`user`（默认）、`admin`
- 管理员可以管理所有用户（查看列表、启用/禁用、分配角色）
- 作者与图书的 CRUD，支持按作者过滤图书
- 普通用户只能修改/删除自己创建的资源，管理员可操作任意资源
- 删除有关联图书的作者时拒绝操作（409 Conflict）
- 所有写操作自动生成审计日志，管理员可查询筛选
- 完整的自动化测试（内存数据库隔离，一键运行）

## 技术栈

- **Python 3.11+**
- **FastAPI** (异步 Web 框架)
- **SQLAlchemy 2.0** (异步 ORM) + SQLite / aiosqlite
- **Pydantic v2** (数据验证与序列化)
- **JWT** (python-jose) + bcrypt (passlib)
- **Alembic** (数据库迁移)
- **pytest + httpx** (自动化测试)

## 端点清单与权限矩阵

| 方法 | 端点 | 描述 | 未登录 | user | admin |
|------|------|------|--------|------|-------|
| POST | `/auth/register` | 注册新用户 | ✅ | ✅ | ✅ |
| POST | `/auth/login` | 登录 | ✅ | ✅ | ✅ |
| POST | `/auth/refresh` | 刷新 Token | ✅ | ✅ | ✅ |
| POST | `/auth/forgot-password` | 忘记密码 | ✅ | ✅ | ✅ |
| POST | `/auth/reset-password` | 重置密码 | ✅ | ✅ | ✅ |
| GET | `/users/me` | 获取当前用户信息 | ❌ | ✅ | ✅ |
| POST | `/users/me/change-password` | 修改密码 | ❌ | ✅ | ✅ |
| GET | `/authors` | 获取所有作者 | ✅ | ✅ | ✅ |
| GET | `/authors/{id}` | 获取单个作者 | ✅ | ✅ | ✅ |
| POST | `/authors` | 创建作者 | ❌ | ✅ | ✅ |
| PUT | `/authors/{id}` | 更新作者 | ❌ | 仅自己 | ✅ |
| DELETE | `/authors/{id}` | 删除作者 | ❌ | 仅自己 | ✅ |
| GET | `/books` | 获取所有图书 | ✅ | ✅ | ✅ |
| GET | `/books/{id}` | 获取单本图书 | ✅ | ✅ | ✅ |
| POST | `/books` | 创建图书 | ❌ | ✅ | ✅ |
| PUT | `/books/{id}` | 更新图书 | ❌ | 仅自己 | ✅ |
| DELETE | `/books/{id}` | 删除图书 | ❌ | 仅自己 | ✅ |
| GET | `/admin/users` | 查看所有用户 | ❌ | ❌ | ✅ |
| PATCH | `/admin/users/{id}/status` | 启用/禁用用户 | ❌ | ❌ | ✅ |
| PATCH | `/admin/users/{id}/role` | 修改用户角色 | ❌ | ❌ | ✅ |
| GET | `/admin/audit-logs` | 查看审计日志 | ❌ | ❌ | ✅ |

> 管理员不能禁用自己或修改自己的角色（返回 403）。

## 认证流程

1. **注册/登录** 返回 `access_token`（15分钟）和 `refresh_token`（7天）。
2. 访问受保护端点时在 `Authorization: Bearer <access_token>` 头中提供。
3. Access Token 过期后，调用 `/auth/refresh` 提交 `refresh_token` 获取新 Token 对，旧的 Refresh Token 立即失效。
4. 密码重置通过 `/auth/forgot-password` 请求，开发环境会将重置 Token 打印在控制台，调用 `/auth/reset-password` 完成重置。Token 一次性使用，15 分钟过期。

## 审计日志

- 自动记录所有写操作：创建/更新/删除作者/图书、用户修改密码、管理员变更状态/角色。
- 日志字段：操作者 ID、操作类型、资源类型和 ID、时间戳、简要描述。
- 仅管理员可访问 `/admin/audit-logs`，支持按 `user_id`、`action`、`start_time`、`end_time` 过滤。
- 日志写入使用 `BackgroundTasks`，不阻塞业务请求。

## 快速开始

### 1. 克隆项目

```bash
git clone <your-repo-url>
cd Bookstore_API_with_RBAC
```

### 2. 创建虚拟环境并安装依赖

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

pip install -r requirements.txt
```

### 3. 配置环境变量

复制示例文件并修改（可选，默认使用 SQLite）：

```bash
cp .env.example .env
```

`.env` 文件示例：

```
DATABASE_URL=sqlite+aiosqlite:///./bookstore.db
SECRET_KEY=change-me-to-a-random-secret
DEBUG=true
```

### 4. 数据库迁移

```bash
alembic upgrade head
```

### 5. 启动应用

```bash
uvicorn app.main:app --reload
```

API 文档自动生成：
- Swagger UI：http://127.0.0.1:8000/docs
- ReDoc：http://127.0.0.1:8000/redoc

### 6. 运行测试

```bash
chmod +x run_tests.sh   # 仅首次
./run_tests.sh
```

所有测试使用内存数据库，彼此隔离。

## 项目结构

```
├── app
│   ├── main.py               # 应用入口
│   ├── config.py             # 配置集中管理
│   ├── database.py           # 异步引擎与会话
│   ├── models                # ORM 模型
│   ├── schemas               # Pydantic 请求/响应
│   ├── api                   # 路由端点
│   ├── services              # 业务逻辑层
│   ├── core                  # 安全、权限、依赖
│   └── utils                 # 工具函数
├── tests                     # 自动化测试
│   ├── conftest.py
│   ├── test_auth.py
│   ├── test_authors.py
│   ├── test_books.py
│   ├── test_admin.py
│   ├── test_models.py
│   └── test_schemas.py
├── alembic                   # 数据库迁移
│   ├── env.py
│   └── versions
├── .env.example
├── requirements.txt
├── run_tests.sh
└── README.md
```

## 设计决策记录

### 为什么选择 JWT + Refresh Token？

- **无状态**：JWT 不依赖服务端存储会话，易于水平扩展。
- **安全性**：Access Token 短寿命（15分钟）降低泄露风险；Refresh Token 长寿命（7天）提供良好用户体验。
- **滚动刷新**：每次使用 Refresh Token 时颁发新的 Refresh Token 并撤销旧的，防止长期未发现泄露。

### 为什么审计日志异步写入？

- **性能**：日志写入不能阻塞业务请求，使用 `BackgroundTasks` 在响应返回后执行。
- **可靠性**：日志写入失败（如数据库暂时不可用）不会影响业务操作。

### 为什么删除作者时禁止级联删除图书？

- **数据完整性**：避免误删导致图书数据丢失。
- **显式操作**：要求用户先处理（删除或迁移）关联图书后再删作者，提高操作可感知性。

## 协同开发流程（AI 辅助）

本项目采用“契约定义 → 验证先行 → 逐步实现”的模式：

1. **需求分解**：将需求文档拆分为认证、资源、权限、审计四大模块。
2. **定义契约**：先编写 Pydantic Schema 和 API 契约文档，明确输入输出。
3. **编写测试**：每个模块先写自动化测试（如 `test_auth.py`），确保覆盖所有场景。
4. **实现功能**：在测试驱动下逐步实现路由、服务层、安全工具。
5. **AI 协作**：
   - 将清晰的、小颗粒度的任务描述作为提示词提供给 AI。
   - 每次 AI 生成代码后，通过自动化测试验证正确性。
   - 遇到问题时，分析错误信息后请求 AI 修正，保持迭代快速。
6. **重构**：在功能稳定后将业务逻辑从路由抽取到服务层，保持架构一致。

## 许可证

MIT