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

from pydantic import BaseModel, Field


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
# 【下一步预告（本轮不做，避免扩大范围）】
# 接口目前"返回"的是裸 dict，没有用 Pydantic 做响应模型。
# 企业做法是再定义 PlanOut / PlanListOut 并用 response_model= 声明，
# 好处是：响应字段被严格约束（不会不小心把密码字段吐出去）、
#        Swagger 里能显示完整的返回结构。
# 等进入 P1-02 数据库设计、字段变多时一并做，那时收益才明显。
# ---------------------------------------------------------------------------
