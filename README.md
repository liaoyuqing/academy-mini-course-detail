# 学院 v1 · 小程序课程详情接口（GET /api/mini/academy/courses/{id}）

会员空间平台的学院模块：小程序课程详情页所需的全部数据由一个接口返回 —— 课程基础信息、
未结束课期（按 `start_at` 升序）、讲师与条件化企业能力卡、评价摘要、当前用户权益余额。
`signup_state` 不在此处推导，一律透传报名资格校验服务的 12 种取值。

技术栈：Python 3.11+ / FastAPI / SQLAlchemy 2 / Alembic / PostgreSQL 16（本地演示可用 sqlite）。

## 1. 运行与测试

```bash
# 1) 安装依赖（只需一次）
pip install -r requirements.txt

# 2) 本地演示：sqlite + 本地替身下游，不需要 PostgreSQL、Redis、CRM、资格服务，也不需要任何密钥
$env:DATABASE_URL="sqlite+pysqlite:///./demo.sqlite3"
$env:APP_ENV="mock"
python scripts/seed_demo.py      # 写入虚构演示数据
python -m uvicorn app.main:app --host 127.0.0.1 --port 8018

# 3) 打开接口（浏览器直接访问，或 curl / Invoke-WebRequest）
#    http://127.0.0.1:8018/api/mini/academy/courses/00000000-0000-0000-0000-0000000003e9
#    http://127.0.0.1:8018/docs          交互式 OpenAPI
#    http://127.0.0.1:8018/openapi.json  机器可读 schema
```

演示登录态：请求头 `X-Mini-Token: demo-member-token`（或 `Authorization: Bearer demo-member-token`）。
不带 token 时为游客态，详情仍可读，但权益余额退化为 `0`。

```bash
# 4) 跑测试（全量 32 个用例，约 1 秒）
python -m pytest
# 预期输出：32 passed

# 5) 按验收标准分组跑
python -m pytest -k ac1    # 3 passed   —— show_company_card=false 不含企业能力卡字段
python -m pytest -k ac2    # 3 passed   —— 匿名评价不含姓名与 contact_id
python -m pytest -k ac3    # 12 passed  —— 12 种 signup_state 参数化
python -m pytest -k ac4    # 4 passed   —— offline/draft/软删除/不存在 一律 404
```

生产部署（PostgreSQL 16）：

```bash
$env:DATABASE_URL="postgresql+psycopg://app_user:***@127.0.0.1:5432/academy"
$env:APP_ENV="prod"
alembic upgrade head
python -m uvicorn app.main:app --host 0.0.0.0 --port 8018
```

## 2. 依赖什么 / 不需要什么

| 项 | 说明 |
| --- | --- |
| 需要 | Python 3.11+、`requirements.txt` 里的 FastAPI / SQLAlchemy 2 / Alembic / Pydantic / PyYAML / pytest |
| 需要（生产） | PostgreSQL 16 与可用的 `DATABASE_URL`；Redis 仅作缓存位预留，本接口无强依赖 |
| 不需要（测试与演示） | PostgreSQL、Redis、S2-CRM、S3-MINI、报名资格校验服务、任何 API Key |
| 不需要 | npm / Node / 前端构建链；本单是纯后端 |
| mock 的依赖 | `S2-CRM`（`app/clients/crm_client.py`）、报名资格校验服务（`app/clients/enrollment_check.py`）、`S3-MINI` 登录态（`app/clients/mini_client.py`） |

配置与密钥**只从环境变量读取**，见 `.env.example`；代码里没有硬编码地址与凭证。

## 3. 对接点（依赖其他工单，本单以接口桩 / mock 交付）

| 对接点 | 文件 | 真实接口 | 本单替身 |
| --- | --- | --- | --- |
| S2-CRM 企业能力卡 | `app/clients/crm_client.py` | `GET {CRM_API_BASE}/companies/{id}/capability-card` | `MockCrmClient`（`app/clients/demo_data.py` 的虚构卡片） |
| 报名资格校验服务 | `app/clients/enrollment_check.py` | `POST {ENROLLMENT_API_BASE}/signup-eligibility/resolve` | `MockEnrollmentCheckClient` |
| S3-MINI 登录态 | `app/clients/mini_client.py` | 小程序网关发放的 token | `MockMiniSessionClient` / `MINI_TOKEN_MAP` 环境变量 |

对接时要确认的口径：CRM 企业能力卡的四个公开字段（企业简称、行业、能力供给标签、一句话简介），
以及资格服务返回值的 12 种枚举拼写。两者任一变更都只需要改对应的 client 适配层。

## 4. 接口契约

`GET /api/mini/academy/courses/{id}` → 200 `AcademyCourseDetail`；非 published / 软删除 / 不存在 → 404 `{"detail": "course not found"}`。
完整 schema 见 `openapi/academy_course_detail_1918.json`（由 `python scripts/export_openapi.py` 生成）。

响应字段裁剪的三条硬规则：

1. 讲师 `show_company_card=false` 时，对象里**没有** `company_card` 键（不是 null）；为 `true` 时给出企业简称、行业、最多 5 个能力供给标签、一句话简介，联系方式字段在 client 层就被丢弃。
2. 匿名评价的 `author_name` 固定为「匿名学员」，`ReviewItem` schema 里没有 `contact_id`，实名评价也不返回 `contact_id`。
3. `remaining`（单位：分）仅在 `fee_mode=entitlement` 时出现；游客态为 `0`。

`signup_state` 共 12 种：`can_signup`、`signed_up`、`waitlisted`、`waitlist_available`、`pending_review`、
`need_auth`、`need_member`、`no_entitlement`、`not_open`、`closed`、`finished`、`application`。
资格服务超时或返回未知值时降级为 `pending_review` 并写 `signup_state_degraded` 告警日志，不返回 5xx。

## 5. 目录

```
app/
  api/mini/academy/courses_detail.py   路由与响应组装
  api/deps.py                          FastAPI 依赖（可在测试里覆盖）
  services/academy_course_detail.py    详情聚合与字段裁剪
  schemas/academy_course_detail.py     响应 schema 与字段约束
  clients/                             S2-CRM / 资格服务 / S3-MINI 对接点与 mock
  db/                                  SQLAlchemy 2 模型与会话
  domain/                              12 种 signup_state 枚举、UTC 时钟
migrations/                            Alembic 迁移（0001_academy）
tests/api/test_courses_detail.py       AC1–AC4 接口测试
tests/fixtures/                        12 种 signup_state / 企业能力卡 / 匿名评价参数化数据
tests/conftest.py                      sqlite 内存库 + 本地替身客户端装配
scripts/export_openapi.py              导出响应 schema
scripts/seed_demo.py                   写入虚构演示数据
docs/checks/                           pytest 真实输出日志
docs/evidence/demo_requests.log        真实 HTTP 请求与响应样本
```

## 6. 数据与保密

仓库内所有课程、讲师、评价、企业、contact 均为虚构数据（`example.invalid` 域名、顺序 UUID）。
不含任何真实个人信息或企业信息，不含客户名称。
配置与密钥只从环境变量读取；不引入任何向境外发送数据的第三方 SDK（唯一的 HTTP 客户端是 `httpx`，仅调用客户内网地址）。
