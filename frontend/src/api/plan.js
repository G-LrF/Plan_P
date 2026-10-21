/**
 * 计划模块 —— 前端通信层（API 客户端）
 * ==========================================================================
 * 【这个文件存在的意义 · 企业里最重要的一条纪律之一】
 *
 * 整个前端项目里，只有这一个文件允许出现 fetch / axios 这类网络请求代码。
 * 其他所有 .vue 组件都通过 import 这里的函数来拿数据。
 *
 * 【为什么必须这样】
 *   假设让每个组件自己写 fetch。将来发生这些事：
 *     1. 后端地址从 8000 换成 8080        → 要改遍所有组件
 *     2. 加了登录功能，请求要带 token      → 要改遍所有组件
 *     3. 401 要统一跳登录页               → 要改遍所有组件
 *     4. 后端把 total 改名成 count         → 要改遍所有组件
 *   集中在一个文件后，上面每一件事都只改一处。
 *
 * 这就是"收口"（也有人叫"防腐层"）：把易变的东西关进一个房间，
 * 房间外面的人不用管房间里怎么变。这个思想在企业里到处都是。
 *
 * 【为什么接口地址写 "/api" 而不是 "http://127.0.0.1:8000/api"】
 *   写相对路径 → 浏览器请求的是当前页面所在的源（5173），
 *              由 Vite 开发代理转发给 8000，不存在跨域问题；
 *              将来上线由 Nginx 转发，代码一个字都不用改。
 *   写绝对地址 → 上线后域名一换，全站请求全挂。这是常见事故。
 * ==========================================================================
 */

/**
 * 接口地址前缀。
 * 单独抽成常量而不是散落在各处，是为了以后要改时只改这一行。
 */
const API_BASE = '/api'

/**
 * 统一的请求处理函数 —— 所有接口都经过它。
 *
 * 【企业级设计的三个要点】
 *   1. 【统一鉴权入口】将来每个请求都要带 token 时，只在这里加一行 headers。
 *   2. 【统一错误处理】把 HTTP 状态码翻译成人能看懂的提示，
 *      组件层就不用各自判断 response.ok 了。
 *   3. 【统一成功/失败返回格式】返回 { ok, data, message } 这样一个固定形状，
 *      调用方永远只处理这一种结构，心智负担最小。
 *
 * 注意这里【故意不抛异常】，而是返回 ok:false。
 * 原因：抛异常会让每个调用点都要写 try/catch，代码又长又容易漏。
 * 返回固定结构让调用方"看一眼 ok 就知道成没成"，更好读也更好维护。
 *
 * @param {string} path    接口路径，例如 "/plans"
 * @param {object} options fetch 的配置项（method / body / headers）
 * @returns {Promise<{ok: boolean, data: any, message: string}>}
 */
async function request(path, options = {}) {
  const url = `${API_BASE}${path}`

  let response
  try {
    // fetch 报错（网络层）的情况：后端没启动、端口被防火墙拦了、断网。
    // 【关键】后端没启动时浏览器只给你一句 "Failed to fetch"，完全看不出原因。
    // 所以这里必须换成"人话"，否则新手会在这条报错上困惑很久。
    response = await fetch(url, {
      headers: { 'Content-Type': 'application/json' },
      ...options,
    })
  } catch (networkError) {
    return {
      ok: false,
      data: null,
      message: `无法连接到后端服务（${url}）。请确认后端已启动：\n` +
               `在 backend 目录下执行  ..\\.venv\\Scripts\\python.exe -m uvicorn app.main:app --reload`,
    }
  }

  // 解析响应体。注意：204 No Content 没有正文，强行 .json() 会抛错。
  let payload = null
  if (response.status !== 204) {
    try {
      payload = await response.json()
    } catch {
      // 后端返回了非 JSON（例如 Nginx 的错误页、502 页面）
      payload = null
    }
  }

  if (!response.ok) {
    // FastAPI 的错误格式是 { "detail": "..." }。
    // 校验失败（422）时 detail 是一个数组，要单独处理，否则会显示成 [object Object]。
    const detail = payload && payload.detail
    let message
    if (Array.isArray(detail)) {
      message = detail.map((d) => d.msg || JSON.stringify(d)).join('；')
    } else if (typeof detail === 'string') {
      message = detail
    } else {
      message = `请求失败（HTTP ${response.status}）`
    }

    // 【一线经验】所有失败都在控制台留一条记录，方便排查。
    // 用户看到的是友好提示，开发者需要看到真实状态码和原始响应。
    console.error(`[API 失败] ${options.method || 'GET'} ${url} -> ${response.status}`, payload)

    return { ok: false, data: null, message }
  }

  return { ok: true, data: payload, message: '' }
}

/* ==========================================================================
   计划相关的具体接口
   每个函数只做一件事：拼对 URL、选对方法、传对参数。
   业务判断（比如 "status 是不是 0"）不放在这里，这里只负责通信。
   ========================================================================== */

/**
 * 获取计划列表
 * 对应后端：GET /api/plans
 * @param {string} keyword 可选关键词，传了就调用搜索接口
 * @returns 成功时 data 形如 { total: 2, data: [{id,title,content,status}, ...] }
 */
export function fetchPlans(keyword = '') {
  if (keyword.trim()) {
    // URLSearchParams 会自动处理中文和特殊字符的 URL 编码。
    // 手拼字符串的话，搜索"学习 Python"（带空格）就会出错。
    const qs = new URLSearchParams({ keyword: keyword.trim() })
    return request(`/plans/search?${qs.toString()}`)
  }
  return request('/plans')
}

/**
 * 创建计划
 * 对应后端：POST /api/plans
 * @param {{title: string, content: string}} plan
 * @returns 成功时 data 是后端生成的完整对象（含 id 和 status）
 */
export function createPlan(plan) {
  return request('/plans', {
    method: 'POST',
    body: JSON.stringify({
      title: plan.title,
      content: plan.content,
    }),
  })
  // 【注意】这里不传 id、不传 status。
  // 因为契约规定：id 由后端生成（避免主键冲突和越权覆盖），
  // 新建计划的状态固定为"未完成"。前端多传了后端也会忽略。
}

/**
 * 更新计划
 * 对应后端：PUT /api/plans/{id}
 * 【注意】后端用的是 PUT，语义是"整体替换"，所以三个字段都必须传全。
 * 如果只想改一个字段，正确做法是后端提供 PATCH 接口（本轮不做）。
 */
export function updatePlan(planId, plan) {
  return request(`/plans/${planId}`, {
    method: 'PUT',
    body: JSON.stringify({
      title: plan.title,
      content: plan.content,
      status: plan.status,
    }),
  })
}

/**
 * 删除计划
 * 对应后端：DELETE /api/plans/{id}
 * @returns 成功时 data 形如 { message: "...", data: {被删除的对象} }
 */
export function deletePlan(planId) {
  return request(`/plans/${planId}`, { method: 'DELETE' })
}

/* ==========================================================================
   【下一步预告 · 本轮不做】
   现在每个接口都散着写一遍 request()。等接口多起来（比如 20 个），
   收口在函数里也会显得啰嗦，那时候的演进方向是：
     - 二次封装成 fetchPlans/createPlan 之外，用配置表批量生成
     - 或者引入 axios 并用拦截器（interceptors）统一处理
   但现在接口才 4 个，提前上那些反而更难读。
   "等痛了再重构"比"预测未来先抽象"可靠得多。
   ========================================================================== */
