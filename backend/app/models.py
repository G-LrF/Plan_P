"""
模型层 —— 用 Python 类描述数据库表

==========================================================================
【ORM 是什么，为什么要用它】
--------------------------------------------------------------------------
    ORM = Object Relational Mapping（对象关系映射）。
    简单说：把"数据库的表"映射成"Python 的类"，把"表的行"映射成"类的实例"。

    不用 ORM（手写 SQL）：
        cursor.execute("SELECT id, title FROM plans WHERE status = %s", (0,))
        rows = cursor.fetchall()
        for r in rows:
            print(r[0], r[1])          # 只能靠下标，第 0 个是啥？要回看 SQL

    用 ORM：
        plans = db.query(Plan).filter(Plan.status == 0).all()
        for p in plans:
            print(p.id, p.title)       # 有属性名，编辑器还能自动补全

    【ORM 的真正价值不是少写代码，而是】
      1. 表结构写在一个地方，代码就是文档
      2. 换数据库（MySQL→PostgreSQL）基本不用改业务代码
      3. 避免 SQL 注入：ORM 会自动做参数化查询
         （手拼 SQL 字符串是 SQL 注入的头号来源，这是真实存在的重大安全漏洞）
      4. 字段名改了，编辑器立刻报错提醒你哪里没改

    【代价】
      复杂查询时 ORM 生成的 SQL 可能不如手写高效。
      所以真实项目里是"ORM 为主 + 关键查询手写 SQL"混合使用。
==========================================================================
"""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Index, Integer, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """所有模型类的基类。

    【它的作用】
        SQLAlchemy 通过继承这个基类来"登记"所有表。
        所以 Base.metadata 里就包含全部表结构定义，
        init_db() 里一句 create_all() 就能把所有表建出来。

    【注意】这个类本身不代表任何表，它只是"登记册"。
    """


class Plan(Base):
    """计划表。

    【表名为什么用复数 plans】
        SQL 社区的通行约定：表名用复数（plans），模型类名用单数（Plan）。
        因为一张表存的是"多条计划"，而一个对象是"一条计划"。

    【__table_args__ 里的索引说明】
        单个字段上的 index=True 已经能建索引，
        这里额外声明复合/命名索引是为了给索引起明确的名字，
        便于以后在数据库里定位"是哪个索引慢了"。
    """

    __tablename__ = "plans"

    # ======================================================================
    # 字段定义
    # ======================================================================
    # 【Mapped[...] 是什么】
    #   这是 SQLAlchemy 2.0 的新写法（类型注解式）。
    #   Mapped[int] 表示"这个属性在 Python 层面是 int 类型"，
    #   同时告诉 SQLAlchemy "这是个要映射到数据库的列"。

    # mapped_column(...) 里的参数就是建表时的列属性。

    # ----------------------------------------------------------------------
    # id：主键
    # ----------------------------------------------------------------------
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        # autoincrement=True：由数据库自动生成递增编号。
        # 【为什么不在代码里算 max(id)+1】
        #   两个请求同时来，都读到 max=3，都算出 4，就会主键冲突。
        #   交给数据库的 AUTO_INCREMENT，它保证原子性，并发下也不会重复。
        autoincrement=True,
        comment="计划编号，主键",
    )

    # ----------------------------------------------------------------------
    # title：标题
    # ----------------------------------------------------------------------
    title: Mapped[str] = mapped_column(
        # String(100) 对应 SQL 的 VARCHAR(100)
        String(100),
        # nullable=False 对应 SQL 的 NOT NULL
        nullable=False,
        comment="计划标题",
    )

    # ----------------------------------------------------------------------
    # content：内容
    # ----------------------------------------------------------------------
    # 【为什么是 500，而代码里只校验 100】
    #   数据库上限放宽，业务规则收紧。
    #   这样将来产品要求"内容可以写 300 字"时，只改 schema.py 一行，
    #   不用 ALTER TABLE（大表改结构可能锁表，线上要停服务）。
    content: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="计划内容",
    )

    # ----------------------------------------------------------------------
    # status：完成状态
    # ----------------------------------------------------------------------
    # 【为什么用 Integer 而不是布尔】
    #   现在只有 0/1，看起来 bool 更合适。
    #   但真实业务里状态往往会扩展：0=未开始 1=进行中 2=已完成 3=已取消。
    #   用 int 留了扩展空间，用 bool 就得改类型。
    #
    # server_default="0" 和 default=0 的区别：
    #   default=0         → Python 层默认值（ORM 插入时填上）
    #   server_default="0"→ 数据库层默认值（即使绕过 ORM 直接插数据也生效）
    #   两个都写是最稳的，这里用 server_default 保证数据库层面也正确。
    status: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
        index=True,  # 建索引：会经常按状态筛选
        comment="状态：0=未完成，1=已完成",
    )

    # ----------------------------------------------------------------------
    # category：分类（预留字段）
    # ----------------------------------------------------------------------
    # 【Mapped[str | None] 表示"可以是 None"】
    #   对应 SQL 里允许 NULL。
    # 【为什么现在就要这个字段】
    #   前端现在用 id % 5 假装分类，这是临时方案（设计债）。
    #   加了这个字段才能正式还债。现在建表顺手加上，成本为零；
    #   以后再加要 ALTER TABLE，还有写迁移脚本、考虑回滚。
    category: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="分类：work/study/health，NULL=未分类",
    )

    # ----------------------------------------------------------------------
    # due_date：截止日期（预留字段）
    # ----------------------------------------------------------------------
    # 【为什么用 Date 而不是 DateTime】
    #   产品需求只到"天"，不需要精确到时分秒。
    #   用 DateTime 反而会引入无意义的争议："今天 00:00 算不算已过期？"
    #   数据类型要贴着业务语义选，不是越精确越好。
    due_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        index=True,  # 会按截止日期排序/筛选
        comment="截止日期，NULL=不限",
    )

    # ----------------------------------------------------------------------
    # created_at：创建时间
    # ----------------------------------------------------------------------
    # 【server_default=func.now() 的效果】
    #   插入时如果没传这个字段，数据库自动填当前时间。
    #   你永远不用手动写"创建时间"，也就不可能忘。
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        comment="创建时间",
    )

    # ----------------------------------------------------------------------
    # updated_at：最后更新时间
    # ----------------------------------------------------------------------
    # 【onupdate=func.now() 是这里的关键】
    #   每次执行 UPDATE 时自动刷新为当前时间，代码里一行都不用写。
    #
    # 【为什么所有表都该有 created_at / updated_at】
    #   线上出了问题，第一个问题永远是"这条数据什么时候进来的、
    #   什么时候被改的、改之前是什么"。
    #   没有时间戳，等于飞机没有黑匣子。
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="最后更新时间",
    )

    # ======================================================================
    # 索引声明
    # ======================================================================
    # 【为什么给索引起名字】
    #   自动生成的索引名是 idx_plans_status 这类，但命名不规则。
    #   显式命名后，将来在数据库里排查慢查询时，
    #   能一眼看出是哪个索引、以及为什么建它。
    #
    # 【为什么需要这个复合索引】
    #   业务上最常见的查询是"某分类下未完成的计划"：
    #       WHERE category = ? AND status = ?
    #   单字段索引在组合条件时效果有限，复合索引能一次命中。
    #   注意字段顺序：(category, status) 和 (status, category) 效果不同，
    #   区别在于"最左前缀原则" —— 查询条件里的字段顺序要和索引对齐才能用上。
    __table_args__ = (
        Index("idx_plans_category_status", "category", "status"),
    )

    def __repr__(self) -> str:
        """打印对象时显示成有意义的字符串。

        【为什么需要它】
            不写的话，print(plan) 会输出：
                <app.models.Plan object at 0x000001F2A3B4C5D0>
            完全没用。写了之后输出：
                <Plan id=1 title='学习 Python' status=0>
            调试时一眼就能看出问题。
        """
        return f"<Plan id={self.id} title={self.title!r} status={self.status}>"
