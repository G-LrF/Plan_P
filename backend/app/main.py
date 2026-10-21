"""
Plan Training API —— 计划规划执行系统 · 后端入口

【本次改造的核心变化】
    改造前：数据存在内存列表 plans = [...]，重启即丢
    改造后：数据存在 MySQL 数据库，永久保存

    【关键】接口的 URL、请求格式、返回格式【完全没有变化】。
    所以前端一行代码都不用改 —— 这就是"外部行为不变，内部实现替换"，
    是好架构的标志。如果换数据库还需要改前端，说明耦合了，是设计问题。

【分层结构（本次新增了三层）】
    config.py     配置层：从 .env 读数据库地址和密码
    database.py   连接层：管理连接池，提供 Session
    models.py     模型层：用 Python 类描述表结构
    crud.py       数据层：所有数据库读写操作
    main.py       路由层：接收请求、调用 crud、返回响应  ← 你在这里

    【为什么这么拆】路由层不应该知道"数据存在哪、怎么查"。
    它只该关心"收到什么请求、返回什么结果"。
    这样将来换数据库、加缓存、加权限校验，路由基本不用动。
"""

from sqlalchemy import text
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from app import crud
from app.config import get_settings
from app.database import get_db, init_db
from app.schema import PlanCreate, PlanListOut, PlanOut, PlanUpdate

# 读取配置（.env 里的值）
settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="计划规划执行系统 · 后端接口（阶段 1：MySQL 数据库版）",
)

# ---------------------------------------------------------------------------
# CORS（跨域资源共享）中间件
# ---------------------------------------------------------------------------
# 【为什么需要它】
#   浏览器有"同源策略"：协议 + 域名 + 端口，三者任一不同就算"跨域"。
#   前端 http://localhost:5173 与后端 http://127.0.0.1:8000 端口不同 → 跨域。
#
# 【allow_origins 从哪来】
#   原来写死在代码里，现在从 .env 的 CORS_ORIGINS 读取。
#   好处：部署到服务器时，只改 .env 就能改成真实域名，不用改代码。
#
# 【⚠️ 生产环境注意】
#   allow_origins=["*"] + allow_credentials=True 是危险组合，
#   生产环境必须把 allow_origins 收紧成真实域名白名单。
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# 应用启动事件：建表
# ---------------------------------------------------------------------------
@app.on_event("startup")
def on_startup() -> None:
    """服务启动时自动建表。

    【为什么放在 startup 事件里】
        保证"服务能对外提供服务"之前，数据库结构一定已经就绪。
        如果放在模块顶层，import 阶段就连数据库，
        会导致"连不上数据库时连错误页面都打不开"，排查更困难。

    【init_db 做了什么】
        根据 models.py 的定义，创建所有【不存在】的表。
        已存在的表不会被修改（改表结构需要 Alembic 迁移工具）。

    【⚠️ 生产环境的做法不同】
        生产环境通常不让应用自动建表，而是把建表交给迁移流程
        （CI/CD 里执行 alembic upgrade head），因为：
          - 多实例同时启动会并发建表，可能冲突
          - 建表权限不该给应用账号
        现在单机开发，自动建表最省事。
    """
    init_db()


# 统一前缀：APIRouter 是 FastAPI 拆分路由的标准工具
router = APIRouter(prefix="/api", tags=["plans"])


# ---------------------------------------------------------------------------
# 1. 健康检查
# ---------------------------------------------------------------------------
@router.get("/health", summary="健康检查")
def health(db: Session = Depends(get_db)):
    """检查服务和数据库是否都正常。

    【本次改进：健康检查会验证数据库连接】
        原来只返回一句 ok，但"服务活着"不等于"能干活"。
        如果数据库挂了，健康检查还返回 ok，负载均衡器就会继续把流量
        打过来，每个请求都失败 —— 这是真实的事故场景。

    【用 SELECT 1 而不是查业务表】
        查大表会变慢，健康检查必须轻量；
        而且业务表为空不代表数据库有问题。
        SELECT 1 是最小开销的连通性验证。

    【数据库不通时返回 503 而不是 200】
        这样监控系统和 K8s 探针才能正确判断服务状态。
    """
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        # 【注意】不把原始异常直接返回给调用方 ——
        # 异常信息可能包含连接串（含密码），泄露到响应或日志都是事故。
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"数据库连接失败：{type(exc).__name__}",
        ) from exc

    return {
        "status": "ok",
        "service": "plan-training-api",
        "database": "connected",
    }


# ---------------------------------------------------------------------------
# 2. 获取所有计划
# ---------------------------------------------------------------------------
@router.get("/plans", response_model=PlanListOut, summary="获取计划列表")
def get_plans(db: Session = Depends(get_db)):
    """返回全部计划。

    【response_model=PlanListOut 的三个作用】
      1. 按定义过滤字段，多余字段不会泄露出去（防意外泄露）
      2. Swagger 文档里显示完整的返回结构
      3. 自动校验返回值类型，写错会立刻报错而不是悄悄返回脏数据
    """
    plans = crud.get_plans(db)
    return {"total": len(plans), "data": plans}


# ---------------------------------------------------------------------------
# 3. 创建计划
# ---------------------------------------------------------------------------
@router.post(
    "/plans",
    status_code=status.HTTP_201_CREATED,
    response_model=PlanOut,
    summary="创建计划",
)
def create_plan(plan_data: PlanCreate, db: Session = Depends(get_db)):
    """创建一条计划。

    【依赖注入 db: Session = Depends(get_db) 是什么意思】
        FastAPI 看到这个声明，会在调用函数【之前】自动：
          1. 执行 get_db() 生成器，拿到一个 Session
          2. 把 Session 传给你的函数
          3. 请求结束后，继续执行生成器的 finally，自动 close()

        所以你【永远不用管连接的创建和关闭】，也不可能忘记关闭。
        这是依赖注入最大的价值：把容易出错的事交给框架保证。

    【校验在数据库之前完成】
        Pydantic 先校验，不过就直接 422，数据库连碰都不会碰。
        所以业务函数里不需要写 if not title: return 400。
    """
    return crud.create_plan(db, plan_data)


# ---------------------------------------------------------------------------
# 4. 搜索计划
# ---------------------------------------------------------------------------
# 【关键知识点：路由顺序陷阱】
#   FastAPI 按"注册顺序"匹配路由。
#   如果把 /plans/{plan_id} 写在 /plans/search 前面，
#   请求 /plans/search 会先撞上 /plans/{plan_id}，然后试图把字符串
#   "search" 转成 int 失败 → 返回 422。
#   所以：固定路径必须写在动态路径之前。
@router.get(
    "/plans/search",
    response_model=PlanListOut,
    summary="按关键词搜索计划",
)
def search_plans(keyword: str = "", db: Session = Depends(get_db)):
    """按关键词搜索标题或内容。不传关键词则返回全部。"""
    keyword = keyword.strip()
    result = crud.search_plans(db, keyword)
    return {"keyword": keyword, "total": len(result), "data": result}


# ---------------------------------------------------------------------------
# 5. 按 ID 获取单条计划
# ---------------------------------------------------------------------------
@router.get("/plans/{plan_id}", response_model=PlanOut, summary="获取单条计划")
def get_plan(plan_id: int, db: Session = Depends(get_db)):
    """按 id 查询，找不到返回 404。"""
    plan = crud.get_plan(db, plan_id)
    if plan is None:
        # 明确返回 404，而不是返回空对象假装成功。
        # 前端需要明确的失败信号才能显示"该计划不存在"。
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"计划 ID {plan_id} 不存在",
        )
    return plan


# ---------------------------------------------------------------------------
# 6. 按 ID 更新计划
# ---------------------------------------------------------------------------
@router.put("/plans/{plan_id}", response_model=PlanOut, summary="更新计划")
def update_plan(plan_id: int, plan_data: PlanUpdate, db: Session = Depends(get_db)):
    """更新计划标题、内容和状态。

    【为什么先查再改】
        需要判断"存不存在"来返回 404。
        查出来后把【对象】传给 crud.update_plan，避免 crud 里再查一次，
        省一次数据库往返。
    """
    plan = crud.get_plan(db, plan_id)
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"计划 ID {plan_id} 不存在",
        )
    return crud.update_plan(db, plan, plan_data)


# ---------------------------------------------------------------------------
# 7. 按 ID 删除计划
# ---------------------------------------------------------------------------
@router.delete("/plans/{plan_id}", summary="删除计划")
def delete_plan(plan_id: int, db: Session = Depends(get_db)):
    """删除计划，返回被删除的对象。

    【为什么返回被删除的数据】
        前端可据此提示"已删除《学习 Python》"，或做撤销功能。
        只回一句"删除成功"，前端就拿不到被删内容的标题了。

    【为什么先取出数据再删】
        删除并 commit 后，SQLAlchemy 对象会变成 detached 状态，
        再访问属性可能报错。所以先用 PlanOut 复制一份出来。
    """
    plan = crud.get_plan(db, plan_id)
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"计划 ID {plan_id} 不存在",
        )

    # 删除前先复制出要返回的数据
    deleted = PlanOut.model_validate(plan)

    crud.delete_plan(db, plan)

    return {"message": "计划删除成功", "data": deleted}


# 把路由挂到应用上
app.include_router(router)


# ---------------------------------------------------------------------------
# 直接运行入口
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
