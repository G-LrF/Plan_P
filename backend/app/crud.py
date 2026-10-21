"""
CRUD 层 —— 所有数据库读写操作集中在这里

==========================================================================
【为什么要把数据库操作单独抽一层】
--------------------------------------------------------------------------
    假设不抽，直接在路由里写数据库代码：

        @router.get("/plans")
        def get_plans(db: Session = Depends(get_db)):
            return db.query(Plan).all()          # ← 数据库代码混在路由里

    看起来没什么，但会带来这些问题：

      1. 【无法复用】路由 A 和路由 B 都想"按 id 查计划"，
         就得复制同一段代码。改需求时要改两处，必然漏一处。

      2. 【无法测试】想测"查询逻辑对不对"，必须先起一个 HTTP 服务。

      3. 【改动扩散】将来要加"只能查自己的数据"，
         有 10 个路由就要改 10 处。

    抽出 crud 层后：
      - 路由只关心"收到请求、调函数、返回结果"
      - crud 只关心"怎么和数据库打交道"
      - 每一层都能独立测试

    【这一层命名的历史】CRUD = Create / Read / Update / Delete，
    是"数据增删改查"的通用叫法。很多框架（Django、Spring）都有类似分层。
==========================================================================
"""

from datetime import date

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app import models
from app.schema import PlanCreate, PlanUpdate


# ==========================================================================
# Read（读）
# ==========================================================================
def get_plans(db: Session) -> list[models.Plan]:
    """查询全部计划，按创建时间倒序（最新的排前面）。

    【order_by(models.Plan.created_at.desc()) 为什么重要】
        不排序的话，数据库返回顺序是"不确定的"（取决于存储引擎的物理顺序）。
        这意味着同一个页面刷新两次，列表顺序可能变 —— 用户会觉得"东西在跳"。
        【显式排序是必须的】，不能依赖数据库的默认顺序。
    """
    return (
        db.query(models.Plan)
        .order_by(models.Plan.created_at.desc(), models.Plan.id.desc())
        .all()
    )


def get_plan(db: Session, plan_id: int) -> models.Plan | None:
    """按 id 查询单条计划，找不到返回 None。

    【为什么返回 None 而不是抛异常】
        这一层只负责"取数据"，取不到就是取不到，这不是错误。
        "取不到该不该报 404" 是【业务决策】，属于路由层的判断。
        把决策和取数分开，crud 才能被更多场景复用
        （比如"更新时先查一下存不存在"，这时不希望它抛异常）。

    【db.get 和 db.query().filter().first() 的区别】
        db.get(Model, pk) 是专门为主键查询优化的：先查 Session 缓存，
        命中就直接返回，不查数据库。比 filter 快，代码也更短。
        所以主键查询优先用 get。
    """
    return db.get(models.Plan, plan_id)


def search_plans(db: Session, keyword: str) -> list[models.Plan]:
    """按关键词搜索标题或内容。

    【or_ 是什么】
        SQL 里的 OR 条件。等价的 SQL：
            WHERE title LIKE %关键词% OR content LIKE %关键词%
        用 or_ 时必须【显式】把两个条件包起来，
        否则 SQLAlchemy 会把它们当成 AND 处理（这是个常见错误）。

    【contains() 做了什么】
        models.Plan.title.contains(keyword) 会生成
            title LIKE '%关键词%'
        是参数化查询，不会 SQL 注入。

    【⚠️ 性能提醒（真实生产环境的坑）】
        以 % 开头的 LIKE 查询【无法使用索引】，数据量大时会全表扫描。
        几万条以下感觉不到，上百万条就是秒级卡顿。
        真实项目的解决方案：
          - 全文索引（MySQL 的 FULLTEXT）
          - 专门的搜索引擎（Elasticsearch）
        现阶段数据量小，先用简单方案，知道有这个坑即可。
    """
    if not keyword:
        return get_plans(db)

    return (
        db.query(models.Plan)
        .filter(
            or_(
                models.Plan.title.contains(keyword),
                models.Plan.content.contains(keyword),
            )
        )
        .order_by(models.Plan.created_at.desc())
        .all()
    )


# ==========================================================================
# Create（增）
# ==========================================================================
def create_plan(db: Session, plan_data: PlanCreate) -> models.Plan:
    """创建一条计划。

    【流程：构造对象 → 加入会话 → 提交 → 刷新】
        add()    只是"登记"，还没真正写进数据库
        commit() 才真正发送 INSERT 语句
        refresh() 从数据库重新读回，拿到数据库生成的值（id / 时间戳）

    【为什么必须有 refresh()】
        commit 之后，id 和 created_at 是数据库生成的。
        如果不 refresh，对象里的这些字段可能是 None 或旧值。
        调用方拿到 return 的对象时会发现 id 是空的 —— 这种 bug 很难查。

    【为什么 id 和 status 不接收客户端的值】
        id      → 由数据库 AUTO_INCREMENT 生成，客户端指定会导致主键冲突/越权覆盖
        status  → 新建的计划按业务规则固定为"未完成"，不该由客户端决定
        这是【安全边界】：不是"客户端用不到所以不传"，而是"不允许它控制"。
    """
    db_plan = models.Plan(
        title=plan_data.title,
        content=plan_data.content,
        status=0,  # 新建计划固定为未完成
    )
    db.add(db_plan)
    db.commit()
    db.refresh(db_plan)
    return db_plan


# ==========================================================================
# Update（改）
# ==========================================================================
def update_plan(
    db: Session, db_plan: models.Plan, plan_data: PlanUpdate
) -> models.Plan:
    """更新一条计划。

    【注意参数：传的是 db_plan 对象，不是 plan_id】
        为什么不干脆在函数里按 id 查？
        因为路由层已经查过一次了（为了判断是否存在、返回 404）。
        再查一次是浪费一次数据库往返。
        【传对象进来】避免重复查询，也让"不存在"的处理留在路由层。

    【为什么不 setattr 循环赋值】
        现在的写法是逐字段显式赋值。看起来啰嗦，但好处是：
          1. 一眼能看出"这个更新会改哪几个字段"
          2. 客户端多传了字段也不会被意外写进去（安全）
        如果用 for k, v in plan_data.model_dump().items(): setattr(...)，
        那么将来 schema 加了敏感字段（比如 is_admin），
        客户端就有可能改到它 —— 这是真实存在的越权漏洞模式。
        【显式赋值 = 白名单，动态赋值 = 黑名单。安全上永远选白名单。】

    【category 和 due_date 现在不更新】
        因为 schema.PlanUpdate 里还没有这两个字段。
        等前端加上输入框，schema 加了字段，这里再补两行。
        现在不写，是为了保持"接口行为与改造前完全一致"。
    """
    db_plan.title = plan_data.title
    db_plan.content = plan_data.content
    db_plan.status = plan_data.status

    db.commit()
    db.refresh(db_plan)
    return db_plan


# ==========================================================================
# Delete（删）
# ==========================================================================
def delete_plan(db: Session, db_plan: models.Plan) -> None:
    """删除一条计划。

    【为什么返回 None 而不是返回被删的对象】
        对象被删掉之后再返回它，属性访问可能报错
        （SQLAlchemy 在 commit 后对象状态会变成 detached）。
        所以由路由层在【删除之前】先把要返回的数据取出来（比如 id 和 title）。
        这是为了避免"返回一个已经死掉的对象"这种隐蔽 bug。

    【⚠️ 真实业务里通常不这么做】
        生产系统一般用"软删除"：加一个 deleted_at 字段，
        删除时不真删，只标记时间。查询时过滤掉。
        原因：
          1. 误删能恢复（用户最常投诉的损失）
          2. 数据可审计（删了谁、什么时候删的）
          3. 外键引用不会断
        硬删除只适合"确实不需要留痕"的场景。
        本项目现在用硬删除保持简单，这是【已知的设计债】，已记录在文档中。
    """
    db.delete(db_plan)
    db.commit()
