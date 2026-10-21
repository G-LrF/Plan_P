# 前端 · 计划规划执行系统

Vue 3（组合式 API）+ Vite 构建的仪表盘前端。数据全部来自后端 FastAPI 接口，
不再有任何写死的演示数据。

---

## 启动

```powershell
npm.cmd install      # 首次必做
npm.cmd run dev
```

> ⚠️ **PowerShell 里必须写 `npm.cmd`**，写 `npm` 会报
> `Cannot run a document in the middle of a pipeline`。
> 原因是 PowerShell 把 `npm` 解析成了 `.ps1` 包装脚本，不能用于管道。

启动后打开终端打印的地址（默认 http://localhost:5173）。
**注意：5173 被占用时 Vite 会自动换到 5174、5175…… 请以终端输出为准。**

## 前置条件

**必须先启动后端**，否则页面会显示"无法连接到后端服务"的错误提示条：

```powershell
cd ..\backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

---

## 常用命令

| 命令 | 作用 |
|---|---|
| `npm.cmd run dev` | 启动开发服务器（带热更新） |
| `npm.cmd run build` | 生产构建，产物输出到 `dist/` |
| `npm.cmd run preview` | 本地预览生产构建结果 |
| `node tests\verify_calendar.mjs` | 校验日历逻辑（26 项，无需启动服务） |
| `node tests\verify_lang.mjs` | 校验语言配置产物（需先 build） |
| `node tests\verify_calendar_bundle.mjs` | 校验日历产物（需先 build） |
| `..\.venv\Scripts\python.exe tests\verify_integration.py` | 联调验证（需前后端都启动） |

---

## 目录结构

```text
src/
├── api/
│   └── plan.js          【核心】唯一允许出现 fetch 的地方，全部接口调用收口于此
├── App.vue              界面与交互逻辑（仪表盘、计划列表、专注计时器、日历）
├── main.js              应用入口
└── style.css            全局样式（浅绿主题）
```

### 为什么 `api/plan.js` 只能有一个

这是本项目最重要的一条前端纪律：**组件里禁止直接写 `fetch`**。

原因：一旦请求散落在各处，将来出现这些需求时就要改遍全项目——
- 后端地址变更（8000 → 8080）
- 新增登录，请求要携带 token
- 统一处理 401（跳登录页）
- 后端字段改名

集中在一个文件后，上面每件事都只改一处。

---

## 架构：请求是怎么走的

```text
App.vue
  │  调用 api/plan.js 里的函数
  ▼
api/plan.js
  │  fetch('/api/plans')   ← 注意是相对路径
  ▼
Vite 开发服务器 (5173)
  │  server.proxy 把 /api 转发出去
  ▼
FastAPI 后端 (127.0.0.1:8000)
```

**为什么 URL 要写相对路径 `/api/...` 而不是 `http://127.0.0.1:8000/api/...`**：

- 写相对路径 → 浏览器认为在请求 5173 自己，**不存在跨域问题**，由 Vite 代理转发
- 写绝对地址 → 上线后域名一换，全站请求全部失效

代理配置在 `vite.config.js` 的 `server.proxy`。
**这就是生产环境 Nginx 反向代理的本机版本**，理解它能直接迁移到部署阶段。

---

## 国际化的实现方式

界面支持中英文，**默认中文**。

```text
All UI text → messages[lang][key] → t('key') → 渲染
```

- 语言状态：`lang`（`'zh'` / `'en'`），默认值由 `DEFAULT_LANG` 决定
- 切换按钮：显示"点击后会变成的语言"，这是双语界面的通行做法
- 新增语言：只需在 `SUPPORTED_LANGS`、`LANG_LABELS`、`messages` 各加一项

**注意**：月份标题和星期名**不在词典里**，由 `toLocaleDateString` 按语言自动生成。
因为它们是能从 `Date` 推导出来的事实，手写进词典迟早会忘了同步。

---

## 日历的实现要点

按当前月份动态生成，不写死任何日期。

| 技术点 | 做法 | 为什么 |
|---|---|---|
| 当月天数 | `new Date(y, m + 1, 0).getDate()` | "下月第 0 天 = 本月最后一天"，自动处理闰年 |
| 首日偏移 | `(getDay() + 6) % 7` | 表头从周一开始，而 `getDay()` 里 0 是周日 |
| 月份标题 | `toLocaleDateString(locale, {year, month})` | 中文"2026年10月"、英文"October 2026"，语序不同，不能手拼 |
| 今天判定 | `toLocaleDateString('en-CA')` 得到 ISO 格式 | 免去手动补零，`2026-10-5` 与 `2026-10-05` 比较会失败 |
| 空格位表示 | 用 `null`，不用 `0` | 用 0 会在日历上渲染出一排 "0" |

---

## 已接入后端的交互

| 界面操作 | 触发的接口 |
|---|---|
| 页面加载 | `GET /api/plans` |
| 输入框回车 / 点 + | `POST /api/plans` |
| 点圆圈切换完成状态 | `PUT /api/plans/{id}` |
| 点垃圾桶删除 | `DELETE /api/plans/{id}` |

**成功时**直接更新本地数组（不重新拉全量），**失败时**顶部显示红色提示条并提供重试按钮。

---

## 已知限制（尚未接入后端的部分）

以下区块仍是演示数据，**界面上已明确标注**，避免误以为整个页面都联调完了：

- 「Up next」（接下来的会议）—— 2 条固定内容
- 搜索框 —— 输入框存在但不能用
- 「Export summary」按钮 —— 无功能
- 添加计划的分页签（收件箱/明天/下周/自定义）—— 仅视觉切换，不真正分类
- 日期「‹」翻页按钮 —— 不可点（`viewYear`/`viewMonth` 已改成 ref，想启用只需绑事件）

**为什么单独列出来**：把"还没做的"标清楚，比假装做完了更有价值。
三个月后你自己也会需要这份清单来确认进度。
