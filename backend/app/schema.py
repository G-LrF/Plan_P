"""
Schema 层 —— 定义"接口的数据契约"

【这一层存在的意义】
    它是前端和后端之间的一份"合同"。前端照着它发请求，后端照着它校验请求。
    有了它，前端可以不等后端写完就开工（照着契约写假数据），后端也能明确
    知道自己该收什么、该吐什么。企业里先把契约（常写成 OpenAPI/Swagger 文档）
    定下来再并行开发，就是这个道理。

【Pydantic 在这里干的三件事】
    1. 类型校验：title 必须是字符串，传数字/对象会直接报错
    2. 业务校验：min_length / max_length / ge / le 这些约束
    3. 自动生成 Swagger 文档：Field 里的 description 会出现在 /docs 页面上，
       前端同事点开就知道每个字段是什么意思，不用来问你
"""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class PlanCreate(BaseModel):
    """创建计划时的请求体（POST /api/plans）。

    【⚠️ 已修正】原类名 PlanCrate 是 PlanCreate 的拼写错误。
    类名拼错不会让程序崩溃，但会让后来的人（包括三个月后的你自己）
    在搜索 "PlanCreate" 时找不到它。命名是给未来的自己留的路标，
    名不副实比没注释更伤——因为错误的命名会主动误导人。
    """

    title: str = Field(
        min_length=1,
        max_length=100,
        description="计划标题，长度为 1～100 个字符",
    )
    content: str = Field(
        min_length=1,
        max_length=100,
        description="计划内容，长度为 1～100 个字符",
    )

    # 【有意不包含 id 和 status】原因：
    #   id      → 由后端生成，客户端指定会引发主键冲突/越权覆盖
    #   status  → 新建计划按业务规则固定为 0（未完成）
    # "客户端能传什么"本身就是一个安全边界，不是随便定的。


class PlanUpdate(BaseModel):
    """更新计划时的请求体（PUT /api/plans/{id}）。

    【为什么更新要用独立的类，不直接复用 PlanCreate】
    因为两者的规则不同：
      - 创建时 content 必须有内容（min_length=1）
      - 更新时允许把 content 清空（min_length=0）
    如果共用一个类，就没法表达这种差异，只能在校验层放松要求，
    结果创建接口也跟着变松了。契约要精确到"每个接口各自的规则"。
    """

    title: str = Field(
        min_length=1,
        max_length=100,
        description="更新后的计划标题",
    )
    content: str = Field(
        min_length=0,
        max_length=100,
        description="更新后的计划内容（允许留空）",
    )
    status: int = Field(
        ge=0,
        le=1,
        description="计划状态：0 表示未完成，1 表示已完成",
    )


# ---------------------------------------------------------------------------
# 响应模型 —— 接口【返回】给前端的数据格式
# ---------------------------------------------------------------------------
# 【为什么要单独定义"返回"的模型，不直接返回数据库对象】
#   之前接口返回的是裸 dict 或者数据库对象，有两个隐患：
#
#   1. 【意外泄露字段】
#      如果以后 Plan 表加了 password_hash、internal_note 这类字段，
#      直接把 ORM 对象返回出去，这些字段会【自动】出现在响应里。
#      用户打开 F12 就能看到内部数据 —— 这是真实发生过的安全事故。
#      有了显式响应模型，只有这里列出的字段才会被返回，默认安全。
#
#   2. 【契约不稳定】
#      数据库加字段就改接口返回，前端可能因此报错。
#      有了 PlanOut，数据库怎么变，只要这里不变，前端就无感。
#
#   【一句话】响应模型是"接口对外的白名单"。安全上永远用白名单，不用黑名单。


class PlanOut(BaseModel):
    """单条计划的响应格式（GET / POST / PUT 都返回这个）。"""

    # from_attributes=True 是关键：它允许 Pydantic 直接从
    # SQLAlchemy 模型对象（有 .id / .title 这些属性）构造响应对象，
    # 而不需要先手动转成 dict。少了这一句会报校验错误。
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="计划编号，由后端生成")
    title: str = Field(description="计划标题")
    content: str = Field(description="计划内容")
    status: int = Field(description="状态：0=未完成，1=已完成")

    # 以下三个是本次接数据库后新增的字段。
    # 【为什么现在就加到响应里】前端暂时用不到，但加了不破坏兼容性
    # （前端只读它认识的字段，多出来的会被忽略）。
    # 而提前返回它们，等前端要展示时不用再改后端。
    category: str | None = Field(default=None, description="分类，NULL=未分类")
    due_date: date | None = Field(default=None, description="截止日期，NULL=不限")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="最后更新时间")


class PlanListOut(BaseModel):
    """计划列表的响应格式（GET /api/plans）。"""

    total: int = Field(description="计划总数")
    data: list[PlanOut] = Field(description="计划列表")

