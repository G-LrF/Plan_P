"""
Plan Training API —— 计划规划执行系统 · 后端入口

【这一层是"路由层"】它的唯一职责：
    把 HTTP 请求（方法 + URL）映射到具体的处理函数，然后返回数据。
它不应该关心"数据存在哪"（内存？MySQL？），那是数据层的事。

【关于 /api 前缀】
    所有接口都挂在 /api 下。原因：
    1. 浏览器里的 URL 空间是共享的，用 /api 划出一块"后端领地"，
       将来前端页面路由、静态资源、WebSocket 才不会被接口路径撞车。
    2. 生产环境用 Nginx 反向代理时，通常就是按 /api 前缀把请求转给后端，
       本地开发和生产环境的规则保持一致，少一类"上线才炸"的bug。
"""

from fastapi import APIRouter, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

# 显式写 app.schema 而不是 schema：
# 这样无论是 `uvicorn app.main:app`（在 backend 目录下运行）
# 还是 `python -m app.main` 都能正常导入，是更稳的写法。
from app.schema import PlanCreate, PlanUpdate

app = FastAPI(
    title="Plan Training API",
    version="0.3.0",
    description="计划规划执行系统 · 后端接口（P1-01 阶段：内存数据版）",
)

# ---------------------------------------------------------------------------
# CORS（跨域资源共享）中间件
# ---------------------------------------------------------------------------
# 【为什么需要它】
#   浏览器有"同源策略"：协议 + 域名 + 端口，三者任一不同就算"跨域"。
#   前端 http://localhost:5173 与后端 http://127.0.0.1:8000 端口不同 → 跨域。
#   跨域时，浏览器会先发一个 OPTIONS 预检请求问后端"我能不能来"，
#   后端必须明确回答"允许"，否则浏览器直接拦掉响应，前端只看到 CORS 报错。
#
# 【allow_origins 为什么要写两个】
#   虽然都指向本机，但在浏览器眼里 "localhost" 和 "127.0.0.1" 是两个不同的源，
#   少写一个就会出现"我明明配了怎么还报错"的经典问题。
#
# 【⚠️ 生产环境注意】
#   allow_origins=["*"]（允许所有来源）+ allow_credentials=True 是危险组合，
#   生产环境必须把 allow_origins 收紧成真实域名白名单，例如：
#       allow_origins=["https://plan.example.com"]
#   这是典型的安全事故来源，务必记住。
#
# 【补充】本地开发我们还会在 Vite 里配 proxy（方案 B）。两个都留着，
#   是为了让你亲眼看到两种方案的效果，也让后端在浏览器直连时也能工作。
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # Vite 默认开发地址
        "http://127.0.0.1:5173",   # 同上，IP 写法算另一个源
    ],
    allow_credentials=True,
    allow_methods=["*"],           # 允许 GET / POST / PUT / DELETE 等
    allow_headers=["*"],           # 允许 Content-Type 等自定义请求头
)


# ---------------------------------------------------------------------------
# 数据层（临时）：内存列表
# ---------------------------------------------------------------------------
# 【⚠️ 已知设计债 1】数据存在 Python 内存里 → 重启服务数据全丢。
#     这不是 bug，是 P1-01 阶段的合理简化。下一步接 MySQL 就彻底解决。
#     那时这块会被替换成 "SQLAlchemy 查询 Session"，接口签名不变。
plans = [
    {
        "id": 1,                            # 计划编号（唯一，由后端生成，客户端不能指定）
        "title": "学习 Python",             # 计划标题
        "content": "掌握 FastAPI 基础",      # 计划内容
        "status": 0,                        # 0 = 未完成，1 = 已完成
    },
    {
        "id": 2,
        "title": "完成接口测试",
        "content": "测试 GET 请求",
        "status": 1,
    },
]


# 统一前缀：APIRouter 是 FastAPI 拆分路由的标准工具（下一阶段把这里的
# 函数搬到 app/routers/plans.py 时会用到），现在先用 prefix 参数达到同一效果。
# tags=["plans"] 只影响 Swagger 文档的分组展示，让接口按业务归类。
router = APIRouter(prefix="/api", tags=["plans"])


# ---------------------------------------------------------------------------
# 1. 健康检查：给"运维/监控"用的接口
# ---------------------------------------------------------------------------
# 【为什么企业一定有这么个接口】
#   K8s 的 liveness/readiness 探针、Nginx 上游健康检查、监控告警，
#   都需要一个"最轻量、不查数据库、永远快速返回"的地址来判断服务是否活着。
#   注意不要和根路由 "/" 混用：根路由可能返回业务首页，语义不同。
@router.get("/health", summary="健康检查")
def health():
    return {"status": "ok", "service": "plan-training-api"}


# ---------------------------------------------------------------------------
# 2. 获取所有计划
# ---------------------------------------------------------------------------
@router.get("/plans", summary="获取计划列表")
def get_plans():
    return {
        "total": len(plans),   # 总数：前端做分页/统计时不用再自己数
        "data": plans,         # 数据本体
    }


# ---------------------------------------------------------------------------
# 3. 创建计划
# ---------------------------------------------------------------------------
# 【关键知识点一：status_code=201】
#   REST 规范里，201 Created 表示"资源被创建成功"，比 200 OK 更准确。
#   前端可以根据状态码区分"查询成功"和"创建成功"，做不同的处理。
#
# 【关键知识点二：参数 plan_data: PlanCreate 是"自动校验"】
#   FastAPI 会用 Pydantic 校验请求体：
#     - 缺字段 / 类型不对 / 长度越界 → 自动返回 422，附带详细的错误字段说明
#     - 校验通过 → 把请求体转成一个 PlanCreate 对象交给我们
#   所以函数体内【不需要】再写 if not title: return 400 这类代码，
#   校验层的活就该校验层干——这叫"关注点分离"。
#
# 【关键知识点三：id 由后端生成，绝不接受客户端传 id】
#   让客户端指定主键，会出现两个客户端抢同一个 id、或恶意覆盖他人数据的问题。
#   这是真实安全事故（越权覆盖）的常见起因。
@router.post("/plans", status_code=status.HTTP_201_CREATED, summary="创建计划")
def create_plan(plan_data: PlanCreate):
    # 取当前最大 id + 1。
    # default=0 的作用：列表为空时 max() 会抛 ValueError，给个默认值就不会崩。
    new_id = max((plan["id"] for plan in plans), default=0) + 1

    new_plan = {
        "id": new_id,
        "title": plan_data.title,
        "content": plan_data.content,
        # 新建的计划一定是"未完成"，状态由业务规则决定，不由客户端传。
        "status": 0,
    }
    plans.append(new_plan)
    return new_plan


# ---------------------------------------------------------------------------
# 4. 搜索计划
# ---------------------------------------------------------------------------
# 【关键知识点：路由顺序陷阱】
#   FastAPI 按"注册顺序"匹配路由。
#   如果把 @router.get("/plans/{plan_id}") 写在 @router.get("/plans/search") 前面，
#   请求 /plans/search 会先撞上 /plans/{plan_id}，然后 FastAPI 试图把字符串
#   "search" 转成 int 失败 → 返回 422，你会一脸茫然地以为搜索功能坏了。
#   所以：固定路径必须写在动态路径之前。这是个真实项目里天天踩的坑。
@router.get("/plans/search", summary="按关键词搜索计划")
def search_plans(keyword: str = ""):
    # 【修正点】原来默认值是 " "（一个空格），看起来像占位符。
    # 语义应该是"不传关键词 = 不过滤，返回全部"。
    # strip() 后再判断：用户只输入空格时也视为"没输入"，避免返回一堆无意义结果。
    keyword = keyword.strip()
    if not keyword:
        result = plans
    else:
        result = [
            plan for plan in plans
            if keyword in plan["title"] or keyword in plan["content"]
        ]
    return {
        "keyword": keyword,
        "total": len(result),
        "data": result,
    }


# ---------------------------------------------------------------------------
# 5. 按 ID 获取单条计划
# ---------------------------------------------------------------------------
@router.get("/plans/{plan_id}", summary="获取单条计划")
def get_plan(plan_id: int):
    for plan in plans:
        if plan["id"] == plan_id:
            return plan

    # 找不到时返回 404，而不是返回 None 或空对象假装成功。
    # 【为什么】前端需要"明确的失败信号"才能显示"该计划不存在"；
    # 返回空成功会让前端把空数据显示成正常内容，用户以为数据丢了。
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"计划 ID {plan_id} 不存在",
    )


# ---------------------------------------------------------------------------
# 6. 按 ID 更新计划
# ---------------------------------------------------------------------------
@router.put("/plans/{plan_id}", summary="更新计划")
def update_plan(plan_id: int, plan_data: PlanUpdate):
    for plan in plans:
        if plan["id"] == plan_id:
            plan["title"] = plan_data.title
            plan["content"] = plan_data.content
            plan["status"] = plan_data.status
            return plan

    # 注意缩进：raise 必须在 for 循环【外面】。
    # 如果写在 if 里，只有找到时才抛异常，逻辑就反了。
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"计划 ID {plan_id} 不存在",
    )


# ---------------------------------------------------------------------------
# 7. 按 ID 删除计划
# ---------------------------------------------------------------------------
@router.delete("/plans/{plan_id}", summary="删除计划")
def delete_plan(plan_id: int):
    for plan in plans:
        if plan["id"] == plan_id:
            plans.remove(plan)
            # 返回被删除的对象：前端可据此做"撤销删除"或提示"已删除《学习 Python》"。
            # 只回一句"删除成功"，前端就拿不到被删内容的标题了。
            return {"message": "计划删除成功", "data": plan}

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"计划 ID {plan_id} 不存在",
    )


# 把路由挂到应用上。以后拆分成多个 router（plans / users / stats）时，
# 这里会有多行 app.include_router(...)，main.py 始终只做"装配"这一件事。
app.include_router(router)


# ---------------------------------------------------------------------------
# 直接运行入口：python -m app.main 也能起服务（等价于 uvicorn app.main:app --reload）
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
