"""
配置层 —— 把 .env 文件里的配置读进程序

【这个文件存在的意义】
    程序里到处都要用"数据库地址"这个值。如果每个文件都自己写
        os.getenv("DATABASE_URL")
    会带来三个问题：
      1. 环境变量名打错时不会报错，只会拿到 None，然后程序在奇怪的地方崩
      2. 没有类型提示，编辑器不知道它是什么
      3. 没有默认值，缺少配置时无法给出友好提示

    pydantic-settings 解决了这三点：声明一次，全局复用，类型安全。

【企业里的做法】
    配置集中在这一个文件里。除了这里，任何地方都不许直接读 os.environ。
    这样"这个项目需要配哪些东西"永远只有一个答案。
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置。

    【继承 BaseSettings 后会发生什么】
        Pydantic 会按下面的顺序找每个字段的值：
          1. 环境变量（比如 shell 里 export 的）
          2. .env 文件
          3. 字段的默认值
        优先级从高到低。这就是为什么同一个程序在本地和服务器上
        可以用不同的配置 —— 不用改代码，只改环境变量。
    """

    # model_config 是 Pydantic v2 的配置写法
    model_config = SettingsConfigDict(
        # 从哪个文件读配置。相对路径基准是"运行程序时的当前目录"，
        # 也就是 backend/，所以这里写 ".env" 即可。
        env_file=".env",
        env_file_encoding="utf-8",
        # 允许 .env 里有这里没声明的字段（比如以后加了别的配置项，
        # 老代码不会因为多了个键就报错）。这叫"前向兼容"。
        extra="ignore",
        # 环境变量名不区分大小写
        case_sensitive=False,
    )

    # ------------------------------------------------------------------
    # 数据库
    # ------------------------------------------------------------------
    # 【为什么类型是 str 而不是别的】
    #   数据库连接串本质就是个字符串，SQLAlchemy 读的时候自己解析。
    #   这里不做过深解析，保持简单。
    #
    # 【Field(...) 里三个点是什么意思】
    #   Field(...) 省略号表示"必填，没有默认值"。
    #   如果 .env 里漏了这一项，程序启动时立刻报错退出，
    #   而不是跑起来之后在某个查询里莫名其妙崩掉。
    #   —— 这叫"快速失败"（fail fast），是企业级应用的常见要求。
    database_url: str = Field(
        ...,
        description="MySQL 连接串，格式 mysql+pymysql://用户名:密码@主机:端口/库名?charset=utf8mb4",
    )

    # ------------------------------------------------------------------
    # 应用元信息
    # ------------------------------------------------------------------
    app_name: str = Field(default="Plan Training API", description="应用名称")
    app_version: str = Field(default="0.4.0", description="应用版本号")
    debug: bool = Field(default=False, description="调试模式，生产环境必须为 false")

    # ------------------------------------------------------------------
    # 跨域配置
    # ------------------------------------------------------------------
    # 【为什么用 str 而不是 list】
    #   .env 文件里没法写 Python 的列表语法（[a, b]），
    #   所以用逗号分隔的字符串存，读出来再切分。
    #   这是环境变量的通用做法。
    cors_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        description="允许跨域的前端地址，多个用逗号分隔",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        """把逗号分隔的字符串转成列表。

        【为什么要 .strip()】
            写成 "a, b" 时，逗号后面有空格，split 出来第二个元素是 " b"，
            带前导空格，匹配 origin 时会失败。
            这种小细节不注意，就会变成"我明明配了 CORS 却不生效"的悬案。
        """
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def safe_database_url(self) -> str:
        """把连接串里的密码替换成 ***，用于日志和错误提示。

        【为什么需要这个】
            数据库连不上时，最常见的做法是把连接串打进日志方便排查。
            但那样会把明文密码写进日志文件 —— 日志常常被收集到公共平台，
            等于把密码公开了。

            安全做法：任何要展示连接串的地方，都用这个属性。
        【真实案例】有公司把带密码的连接串打进了日志系统，
                    日志被第三方运维平台收集，密码就这样泄露了。
        """
        url = self.database_url
        if "://" in url and "@" in url:
            # 拆成 "mysql+pymysql://" 和 "user:pass@host/db"
            head, tail = url.split("://", 1)
            if "@" in tail:
                credentials, hostpart = tail.rsplit("@", 1)
                if ":" in credentials:
                    user, _ = credentials.split(":", 1)
                    return f"{head}://{user}:***@{hostpart}"
        return url


@lru_cache
def get_settings() -> Settings:
    """获取配置对象（单例）。

    【lru_cache 在这里起什么作用】
        保证整个程序只读一次 .env 文件，之后每次调用都返回同一个对象。
        这带来两个好处：
          1. 性能：不用每次读磁盘
          2. 一致性：运行时改了 .env，程序里的值不会突变
             （想生效就重启服务 —— 这是可预期的行为）

    【怎么用】
        在需要配置的地方：
            from app.config import get_settings
            settings = get_settings()
            print(settings.database_url)
    """
    return Settings()
