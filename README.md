# 计划规划执行系统 · Plan Training

> 一个用于练习完整企业级开发流程的全栈项目：从界面到接口、从开发到部署。
> 技术栈：Vue 3 + FastAPI，后续演进方向为 MySQL → Docker → Kubernetes → AI 能力。

**这不是一个"能演示的作业"，而是一条走完整开发链路的实践路线。**

--- 

## 项目当前状态

> ⚠️ **重要：项目仍在开发中，数据存储尚未接入数据库（存在内存中，服务重启即清空）。**

| 模块 | 状态 | 说明 |
|---|---|---|
| 计划 CRUD 接口 | ✅ 完成 | 增删改查 + 搜索 + 参数校验全部可用 |
| 前端仪表盘界面 | ✅ 完成 | 中英双语、日历动态生成、专注计时器 |
| 前后端联调 | ✅ 完成 | Vite 代理打通，数据真实流转 |
| 自动化测试 | ✅ 完成 | 4 个测试脚本，共 96 项检查 |
| 用户登录鉴权 | ❌ 未开始 | 任何人访问接口都能增删数据 |
| MySQL 数据库 | ❌ 未开始 | **数据重启即丢失（当前最大缺陷）** |
| Docker 容器化 | ❌ 未开始 | 本机尚未安装 Docker |
| Kubernetes 部署 | ❌ 未开始 | 依赖上一步 |
| AI 能力 | ❌ 未开始 | 自然语言建计划 / 智能任务拆解 |

完整的阶段路线与验收标准见 [docs/开发实训路线图.md](docs/开发实训路线图.md)。

---

## 快速开始

### 前置条件

| 依赖 | 版本要求 | 验证命令 |
|---|---|---|
| Python | 3.11+ | `python -V` |
| Node.js | 18+ | `node -v` |
| Git | 任意较新版本 | `git --version` |

> 本项目开发环境实测：Python 3.13.5 / Node.js 24.19.0 / npm 11.17.0

### 第 1 步：启动后端

```powershell
cd backend

# 首次运行：创建虚拟环境并安装依赖
python -m venv ..\.venv
..\.venv\Scripts\python.exe -m pip install -r requirements.txt

# 启动服务（--reload 表示改代码自动重启）
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

启动成功后应该看到：

```text
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Application startup complete.
```

**立刻验证后端是否正常**，打开浏览器访问：

- http://127.0.0.1:8000/api/health → 应返回 `{"status":"ok","service":"plan-training-api"}`
- http://127.0.0.1:8000/docs → **Swagger 交互文档，可以直接点按钮测试所有接口**

> 💡 **`/docs` 是 FastAPI 最大的优势之一**：接口文档自动生成，不用手写。
> 调试后端时不看它，等于闭着眼睛写代码。

### 第 2 步：启动前端

**另开一个终端**（后端那个不要关）：

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

> ⚠️ **PowerShell 里必须写 `npm.cmd` 而不是 `npm`**，否则会报
> `Cannot run a document in the middle of a pipeline`。
> 原因是 PowerShell 把 `npm` 解析成了 `.ps1` 包装脚本，无法用于管道。

终端会打印访问地址（默认 http://localhost:5173）。
**如果 5173 被占用，Vite 会自动换到 5174、5175…… 请以终端输出为准。**

### 第 3 步：验证联调成功

打开前端页面，应该能看到：

- 左上角欢迎卡片的进度显示「已完成 1 / 共 2 项」
- 旁边有个**绿色小标「数据来自后端」** ← 出现这个说明联调成功
- 计划列表里有 2 条初始数据：「学习 Python」「完成接口测试」

在输入框里输入文字按回车 → 列表立刻多出一条 → **刷新页面它还在**（说明真的存到后端了，不是前端假数据）。

> ⚠️ 但**重启后端服务后数据会清空** —— 这是当前已知缺陷，见上方状态表。

---

## 项目结构

```text
plan-training/
├── backend/                    后端（Python + FastAPI）
│   ├── app/
│   │   ├── main.py             应用装配 + 全部路由 + CORS 配置
│   │   └── schema.py           数据契约（Pydantic 校验模型）
│   ├── tests/
│   │   ├── test_api.py         进程内测试，32 项检查
│   │   ├── smoke_test.py       真实 HTTP 测试，22 项检查
│   │   └── show_plans.py       数据查看/清理小工具
│   └── requirements.txt
│
├── frontend/                   前端（Vue 3 + Vite）
│   ├── src/
│   │   ├── api/plan.js         【核心】唯一允许出现 fetch 的文件
│   │   ├── App.vue             界面与交互逻辑
│   │   ├── main.js             应用入口
│   │   └── style.css           全局样式
│   ├── tests/
│   │   ├── verify_integration.py      前后端联调验证（18 项）
│   │   ├── verify_lang.mjs            语言配置产物验证（10 项）
│   │   ├── verify_calendar.mjs        日历逻辑验证（26 项）
│   │   └── verify_calendar_bundle.mjs 日历产物验证（14 项）
│   └── vite.config.js          开发代理配置
│
├── docs/                       项目文档
│   ├── 项目状态与交接.md        当前进度、待办、技术债、踩坑记录
│   ├── 开发实训路线图.md        阶段路线与 8 步开发流程
│   └── 交接模板_每轮训练.md     每轮收工前照填的模板
│
├── Test_V1/ Test_V2/           早期 Python CLI 版本（学习演进对照，非主线）
└── 训练日志_*.md                开发过程与踩坑记录
```

---

## 接口文档

所有接口统一 `/api` 前缀。启动后端后可访问 `/docs` 查看交互式文档。

| 方法 | 路径 | 说明 | 成功状态码 |
|---|---|---|---|
| GET | `/api/health` | 健康检查 | 200 |
| GET | `/api/plans` | 获取计划列表 | 200 |
| GET | `/api/plans/search?keyword=xxx` | 按关键词搜索 | 200 |
| GET | `/api/plans/{id}` | 获取单条计划 | 200 / 404 |
| POST | `/api/plans` | 创建计划 | 201 / 422 |
| PUT | `/api/plans/{id}` | 更新计划 | 200 / 404 / 422 |
| DELETE | `/api/plans/{id}` | 删除计划 | 200 / 404 |

### 数据结构

```json
{
  "id": 1,
  "title": "学习 Python",
  "content": "掌握 FastAPI 基础",
  "status": 0
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | 整数 | **由后端生成，客户端不可指定**（防止主键冲突与越权覆盖） |
| `title` | 字符串 | 计划标题，1~100 字符 |
| `content` | 字符串 | 计划内容，1~100 字符 |
| `status` | 整数 | `0` = 未完成，`1` = 已完成 |

### 示例请求

```powershell
# 创建一条计划
curl.exe -X POST http://127.0.0.1:8000/api/plans `
  -H "Content-Type: application/json" `
  -d '{\"title\":\"学 Docker\",\"content\":\"先装 Docker Desktop\"}'
```

---

## 测试

**测试分两层，各管一段，两层都要跑。**

### 第 1 层：后端进程内测试（不需要启动服务）

```powershell
cd backend
..\.venv\Scripts\python.exe tests\test_api.py
```

期望结果：**32 项通过，0 项失败**，退出码 0。

覆盖：健康检查、列表、单条、404 边界、三种 422 校验失败、创建 201、
搜索（含路由顺序陷阱回归）、更新并回读确认、CORS 响应头、删除与重复删除。

### 第 2 层：真实 HTTP 冒烟测试（需要后端已启动）

```powershell
cd backend
..\.venv\Scripts\python.exe tests\smoke_test.py
```

期望结果：**22 项通过，0 项失败**，退出码 0。

> 这层测试用 **uuid 生成唯一标记**来造数据，并在 `finally` 里自动清理，
> 因此**对已有数据完全免疫**，可以反复运行不留下垃圾数据。

**为什么两层都要有**：
- `test_api.py` 全过，但 uvicorn 起不来 → 只有冒烟测试能发现
- 端口通了，但业务逻辑有 bug → 只有 `test_api.py` 能精确定位

### 第 3 层：前端逻辑验证

```powershell
cd frontend
node tests\verify_calendar.mjs          # 26 项：日历逻辑（含闰年边界）
npm.cmd run build                        # 构建产物
node tests\verify_lang.mjs              # 10 项：语言配置产物
node tests\verify_calendar_bundle.mjs   # 14 项：日历产物
```

### 第 4 层：前后端联调验证（需要前后端都启动）

```powershell
cd frontend
..\.venv\Scripts\python.exe tests\verify_integration.py
```

期望结果：**18 项通过**。这层验证的是「浏览器 → Vite 代理 → FastAPI」整条链路，
最关键的一项是：请求 `/api/plans` 拿到的必须是**后端 JSON**，而不是前端自己的 `index.html`。

### 一键跑完全部（PowerShell 示例）

```powershell
# 后端
cd backend
..\.venv\Scripts\python.exe tests\test_api.py
# 前端（后端需另开终端启动中）
cd ..\frontend
node tests\verify_calendar.mjs
npm.cmd run build
node tests\verify_lang.mjs
node tests\verify_calendar_bundle.mjs
```

---

## 技术说明：为什么这样设计

### 1. 前端所有请求收口在一个文件

`frontend/src/api/plan.js` 是**全项目唯一允许出现 `fetch` 的地方**，组件通过 import 调用它。

**为什么**：如果请求散落在各处，以下任一需求都要改遍全项目——

- 后端地址从 8000 换成 8080
- 新增登录，请求要携带 token
- 统一处理 401（跳转登录页）
- 后端字段改名

收口后，每件事只改一处。企业里管这叫"防腐层"。

### 2. 前端 URL 一律用相对路径 `/api/...`

**绝不写死** `http://127.0.0.1:8000`。

- 相对路径 → 浏览器认为请求 5173 自己，**不存在跨域问题**，由 Vite 代理转发
- 写死绝对地址 → 上线后域名一换，全站请求全部失效

代理配置在 `vite.config.js` 的 `server.proxy`。**这就是生产环境 Nginx 反向代理的本机版本。**

### 3. 同时配置 CORS 和代理（双层）

| 方案 | 位置 | 企业对应 |
|---|---|---|
| `CORSMiddleware` | 后端 | 前后端不同域名时使用 |
| `server.proxy` | 前端 | 本地开发标准做法，生产对应 Nginx |

两个都配是为了对照理解两种机制。注意后端同时放行了 `localhost` 和 `127.0.0.1`
——在浏览器眼里它们是两个不同的源，少配一个就会出现"明明配了还是报错"。

### 4. 数据校验交给 Pydantic

缺字段、类型错误、长度越界统一返回 **422**，并附带出错字段说明。
业务函数里因此不需要写 `if not title: return 400` 这类代码。

### 5. 错误返回明确状态码而非空成功

查不到返回 **404**，而不是返回空对象。因为前端需要明确的失败信号，
否则会把空数据当正常内容渲染，用户以为数据丢了。

---

## 常见问题

### `Cannot run a document in the middle of a pipeline: npm`

PowerShell 里要写 **`npm.cmd`**，不是 `npm`。

### 页面显示「无法连接到后端服务」

后端没启动，或端口不对。检查：
1. 后端终端是否还在运行
2. 访问 http://127.0.0.1:8000/api/health 是否有响应
3. 前端 `vite.config.js` 里 proxy 的 target 端口是否与后端一致

### 前端端口不是 5173

5173 被占用时 Vite 会自动换端口。**以终端输出的 `Local: http://localhost:xxxx/` 为准。**

### 控制台中文显示成 `�������`

Windows 终端默认 GBK 编码，而源码是 UTF-8。本项目测试脚本已在开头自动处理
（`sys.stdout.reconfigure(encoding="utf-8")`）。若是你自己的脚本，需要加同样的处理。

### 数据重启后消失了

**这是当前已知缺陷，不是 bug**：数据存在后端内存列表里。
接入 MySQL 是路线图的阶段 1，届时会彻底解决。

### 后端改了代码但接口没变

可能有个**旧的服务进程还占着 8000 端口**。症状是"我明明改了却没生效"，非常容易误判。

```powershell
# 查看谁占用了 8000
netstat -ano | Select-String ":8000"

# 确认接口版本（当前应为 0.3.0，若显示 0.1.0 说明跑的是旧代码）
curl.exe http://127.0.0.1:8000/openapi.json
```

### `git push` 提示 `remote origin already exists`

说明远程已配置过。要改地址用 `set-url` 而不是 `add`：

```powershell
git remote set-url origin git@github.com:G-LrF/Plan_P.git
```

### Git 提交时报 `Author identity unknown`

需要先配身份（把名字邮箱换成你自己的）：

```powershell
git config --local user.name "你的名字"
git config --local user.email "你的邮箱"
```

---

## 路线图

| 阶段 | 目标 | 状态 |
|---|---|---|
| 0 | 工程地基（Git / 文档 / README） | 🔄 进行中 |
| 1 | 接入 MySQL，数据持久化 | ⬜ 待开始 |
| 2 | 用户注册登录 + JWT 鉴权 + 数据隔离 | ⬜ 待开始 |
| 3 | 自动化测试完善 + CI 流水线 | ⬜ 待开始 |
| 4 | Docker 容器化 | ⬜ 待开始 |
| 5 | 部署到云服务器，域名 + HTTPS | ⬜ 待开始 |
| 6 | Kubernetes 编排 + 监控 | ⬜ 待开始 |
| 7 | AI 能力（自然语言建计划） | ⬜ 待开始 |

详细任务与验收标准见 [docs/开发实训路线图.md](docs/开发实训路线图.md)。

---

## 开发者须知

**如果你（或 AI 助手）要接手这个项目，请先读
[docs/项目状态与交接.md](docs/项目状态与交接.md)。**

那份文档包含：当前准确进度、下一步待办、13 条已知技术债、踩坑记录、
以及必须遵守的技术铁律。**代码里的注释可能滞后，但那份文档的进度一节必须保持准确。**

---

## 许可

本项目为个人学习实践用途，未声明开源许可。
