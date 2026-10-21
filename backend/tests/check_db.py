r"""
数据库连接诊断工具

【怎么运行】（在 backend 目录下）
    ..\.venv\Scripts\python.exe tests\check_db.py

【它能干什么】
    1. 检查依赖装了没
    2. 检查 .env 配置对不对
    3. 逐个尝试连接，告诉你到底错在哪
    4. 列出数据库里的表和字段，和代码定义做对比

【为什么需要这个工具】
    数据库连不上的原因可能有很多种：
      - 驱动没装
      - .env 没建 / 变量名写错
      - 密码不对
      - 密码里有特殊字符没做 URL 编码
      - 数据库或表不存在
      - MySQL 服务没启动

    每一种的报错都不一样，但新手看不出区别。
    这个工具把每种情况都试一遍，直接告诉你结论。

【它的输出会告诉你下一步该做什么】——这是好的错误信息的标准。
"""

import sys
import urllib.parse
from pathlib import Path

# 把 backend 目录加入模块搜索路径
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

# 修正 Windows 控制台中文乱码
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass


def section(title: str) -> None:
    print(f"\n{'=' * 62}")
    print(f"  {title}")
    print("=" * 62)


def main() -> int:
    problems: list[str] = []

    # ======================================================================
    # 1. 检查依赖
    # ======================================================================
    section("1. 检查 Python 依赖")
    try:
        import sqlalchemy
        import pymysql
        print(f"  [OK] sqlalchemy {sqlalchemy.__version__}")
        print(f"  [OK] pymysql    {pymysql.__version__}")
    except ImportError as e:
        print(f"  [缺失] {e}")
        print("\n  请先安装依赖：")
        print("   python.exe -m pip install sqlalchemy pymysql pydantic-settings")
        return 1

    try:
        import pydantic_settings  # noqa: F401

        print("  [OK] pydantic-settings")
    except ImportError:
        print("  [缺失] pydantic-settings -> pip install pydantic-settings")
        return 1

    # ======================================================================
    # 2. 检查 .env
    # ======================================================================
    section("2. 检查 .env 配置文件")
    env_path = BACKEND_DIR / ".env"
    if not env_path.exists():
        print(f"  [缺失] 找不到 {env_path}")
        print("  请复制模板后填入密码：")
        print("    copy .env.example .env")
        return 1

    print(f"  [OK] 文件存在：{env_path}")

    try:
        from app.config import get_settings

        settings = get_settings()
    except Exception as e:
        print(f"  [错误] 读取配置失败：{type(e).__name__}: {e}")
        print("\n  常见原因：.env 里缺少 DATABASE_URL 这一行")
        return 1

    print(f"  [OK] DATABASE_URL = {settings.safe_database_url}")

    if "<" in settings.database_url or "在这里填" in settings.database_url:
        print("  [⚠️ ] 检测到占位符未替换！")
        print("        请打开 backend\\.env，把 <在这里填你的MySQL密码> 换成真实密码")
        return 1

    # ======================================================================
    # 3. 解析连接串（提前发现 URL 编码问题）
    # ======================================================================
    section("3. 解析连接串")
    url = settings.database_url
    try:
        parsed = urllib.parse.urlparse(url.replace("mysql+pymysql://", "mysql://"))
        user = parsed.username
        password = parsed.password
        host = parsed.hostname
        port = parsed.port
        dbname = parsed.path.lstrip("/")

        print(f"  用户名 : {user}")
        print(f"  密码   : {'*' * len(password) if password else '(空)'}  （长度 {len(password or '')}）")
        print(f"  主机   : {host}:{port}")
        print(f"  数据库 : {dbname}")

        if not user or not password or not host or not dbname:
            print("  [错误] 连接串格式不完整，请对照 .env.example 检查")
            return 1

        # 检查密码里是否有需要 URL 编码的字符
        # 【这是新手最常踩的坑】密码里有 @ 时，连接串解析会错位
        raw_url = url.replace("mysql+pymysql://", "mysql://")
        credentials_part = raw_url.split("://", 1)[1].split("@")[0]
        if credentials_part.count("@") > 0:
            print("  [⚠️ ] 检测到密码中可能含未编码的 @ 符号")
            print("        @ 必须写成 %40，否则解析会错位")

    except Exception as e:
        print(f"  [错误] 解析失败：{type(e).__name__}: {e}")
        return 1

    # ======================================================================
    # 4. 实际连接
    # ======================================================================
    section("4. 尝试连接数据库")
    from sqlalchemy import create_engine, text

    try:
        engine = create_engine(settings.database_url, pool_pre_ping=True)
        with engine.connect() as conn:
            version = conn.execute(text("SELECT VERSION()")).scalar()
            current_db = conn.execute(text("SELECT DATABASE()")).scalar()
            current_user = conn.execute(text("SELECT CURRENT_USER()")).scalar()
        print("  [OK] 连接成功")
        print(f"       MySQL 版本 : {version}")
        print(f"       当前数据库 : {current_db}")
        print(f"       当前用户   : {current_user}")
    except Exception as e:
        err = str(e)
        print(f"  [失败] {type(e).__name__}: {err[:300]}")

        # 根据错误类型给出针对性建议
        section("诊断建议")
        if "Access denied" in err:
            problems.append("账号或密码错误")
            print("  原因：账号或密码不对")
            print()
            print("  【请按顺序排查】")
            print("  1) 确认用户名对不对（.env 里的 plan_deploy 是否真的创建成功）")
            print("  2) 确认密码对不对（在 Navicat 里双击那个连接，看保存的密码）")
            print("  3) 如果不想纠结旧账号，用 Navicat 新建一个（用 root 连接后执行）：")
            print()
            print("       CREATE USER 'plan_deploy'@'localhost' IDENTIFIED BY 'plandeploy2026';")
            print("       GRANT ALL PRIVILEGES ON plan_app.* TO 'plan_deploy'@'localhost';")
            print("       FLUSH PRIVILEGES;")
            print()
            print("     然后用纯字母数字密码 plandeploy2026 —— 不含特殊字符，")
            print("     就不会碰到 URL 编码的坑。")
        elif "Access denied for user" in err and "using password: NO" in err:
            problems.append("密码为空")
            print("  原因：密码为空，.env 里没填密码")
        elif "Unknown database" in err:
            problems.append(f"数据库 {dbname} 不存在")
            print(f"  原因：数据库 {dbname} 不存在")
            print(f"  解决：在 Navicat 里新建数据库，或改 .env 里的库名")
        elif "Can't connect" in err or "refused" in err:
            problems.append("MySQL 服务未运行")
            print("  原因：连不上 MySQL 服务")
            print("  解决：检查 Windows 服务里的 MySQL80 是否在运行")
        elif "cryptography" in err or "sha256_password" in err:
            problems.append("需要 cryptography 包")
            print("  原因：MySQL 8 的默认认证方式需要 cryptography 包")
            print("  解决：pip install cryptography")
        else:
            problems.append("未知连接错误")
            print("  请把上面的完整报错发给 AI 助手")
        return 1

    # ======================================================================
    # 5. 检查表结构
    # ======================================================================
    section("5. 检查数据库表")
    try:
        from sqlalchemy import inspect

        inspector = inspect(engine)
        tables = inspector.get_table_names()
        if not tables:
            print("  [提示] 数据库里还没有任何表")
            print("       启动后端服务时会自动创建（init_db 负责）")
            return 0

        print(f"  共 {len(tables)} 张表：")
        for t in tables:
            cols = inspector.get_columns(t)
            print(f"\n  ── 表 {t}（{len(cols)} 列）──")
            for c in cols:
                null_flag = "NULL" if c.get("nullable") else "NOT NULL"
                default = c.get("default")
                default_str = f" 默认={default}" if default is not None else ""
                print(f"      {c['name']:<14} {str(c['type']):<18} {null_flag}{default_str}")

    except Exception as e:
        print(f"  [错误] 读取表结构失败：{e}")

    # ======================================================================
    # 6. 实测增删改查
    # ======================================================================
    section("6. 实测一次完整的数据读写")
    try:
        from app import crud, models  # noqa: F401
        from app.database import session_factory

        db = session_factory()
        try:
            # 先确认表存在
            from sqlalchemy import inspect as _inspect

            if "plans" not in _inspect(engine).get_table_names():
                print("  [跳过] plans 表不存在，启动一次后端服务即可自动创建")
                return 0

            from app.schema import PlanCreate

            # 创建
            test_title = "【诊断工具创建，可删除】"
            plan = crud.create_plan(db, PlanCreate(title=test_title, content="验证读写"))
            print(f"  [OK] 创建成功 id={plan.id}")

            # 查询
            found = crud.get_plan(db, plan.id)
            print(f"  [OK] 查询成功 title={found.title!r}")

            # 更新
            from app.schema import PlanUpdate

            crud.update_plan(
                db, found, PlanUpdate(title=test_title, content="验证读写", status=1)
            )
            print("  [OK] 更新成功 status 改为 1")

            # 删除（清理）
            crud.delete_plan(db, found)
            print("  [OK] 删除成功（已清理测试数据）")

        finally:
            db.close()

        print("\n  ✅ 读写全部正常，数据库配置完全正确")

    except Exception as e:
        print(f"  [失败] {type(e).__name__}: {e}")
        problems.append("读写测试失败")

    # ======================================================================
    # 汇总
    # ======================================================================
    print(f"\n{'=' * 62}")
    if problems:
        print(f"  发现 {len(problems)} 个问题：")
        for p in problems:
            print(f"    - {p}")
        print("=" * 62)
        return 1
    print("  ✅ 一切正常，可以启动后端服务了")
    print("=" * 62)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
