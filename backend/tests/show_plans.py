"""
计划数据查看 / 清理小工具

【怎么运行】（在 backend 目录下，需要后端已启动）
    ..\\.venv\\Scripts\\python.exe tests\\show_plans.py
    ..\\.venv\\Scripts\\python.exe tests\\show_plans.py http://127.0.0.1:8002

【这个工具解决什么问题】
    我们的数据存在后端内存里。调试时经常需要回答：
      - 现在库里到底有几条？字段值对不对？
      - 上一轮测试留下的垃圾数据清掉了没？
    没有界面的时候，就需要这样一个小工具。
    企业里这类东西叫"运维脚本"或"CLI 工具"，是开发者的日常顺手兵器。

【重要提醒】它【只查看】，不修改数据。
    想清理测试数据时加 --clean 参数（会先让你看到要删什么）。
    "只读默认、破坏性操作要显式加参数" —— 这是命令行工具设计的基本礼貌，
    避免手快执行了危险的命令。
"""

import json
import sys
import urllib.error
import urllib.parse
import urllib.request

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

# 解析参数：第一个非 -- 开头的参数当作后端地址
args = [a for a in sys.argv[1:] if not a.startswith("--")]
CLEAN = "--clean" in sys.argv
BASE_URL = args[0] if args else "http://127.0.0.1:8000"

# 判定"测试垃圾数据"的关键词。
# 做成常量而不是散在代码里，方便你以后加自己的关键词。
TEST_KEYWORDS = ("冒烟测试", "测试计划", "自动化测试", "联调")


def api(method: str, path: str):
    req = urllib.request.Request(f"{BASE_URL}{path}", method=method)
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            raw = resp.read()
            return resp.status, (json.loads(raw.decode("utf-8")) if raw else None)
    except urllib.error.HTTPError as e:
        return e.code, None
    except urllib.error.URLError as e:
        print(f"[致命] 连不上 {BASE_URL} -> {e.reason}")
        print("       请先启动后端：")
        print("         cd backend")
        print("         ..\\.venv\\Scripts\\python.exe -m uvicorn app.main:app --reload")
        raise SystemExit(2)


def main() -> int:
    code, body = api("GET", "/api/plans")
    if code != 200 or not body:
        print(f"[错误] 获取列表失败，HTTP {code}")
        return 1

    plans = body.get("data", [])
    print(f"\n后端地址：{BASE_URL}")
    print(f"当前共 {body.get('total', 0)} 条计划")
    print("-" * 62)

    if not plans:
        print("  （空列表）")
    for p in plans:
        mark = "[已完成]" if p.get("status") == 1 else "[未完成]"
        print(f"  id={p.get('id'):<4} {mark}  {p.get('title')}")
        print(f"        content: {p.get('content')}")

    if not CLEAN:
        print("-" * 62)
        print("提示：加 --clean 参数可清理测试遗留数据（会先列出待删项）")
        print()
        return 0

    # --- 清理模式 ---
    targets = [p for p in plans if any(k in str(p.get("title", "")) for k in TEST_KEYWORDS)]
    print("-" * 62)
    if not targets:
        print("没有找到测试遗留数据，无需清理。\n")
        return 0

    print(f"将要删除以下 {len(targets)} 条（标题命中测试关键词）：")
    for p in targets:
        print(f"  - id={p.get('id')}  {p.get('title')}")

    # 二次确认。注意：用 input() 交互，非交互环境（如 CI）里会自动跳过。
    try:
        answer = input("确认删除？输入 y 继续，其他任意键取消：").strip().lower()
    except EOFError:
        print("[跳过] 当前环境不支持交互输入，未执行删除。")
        print("       如需强制清理，请改用 tests/smoke_test.py 里的自清理逻辑。\n")
        return 0

    if answer != "y":
        print("已取消，未删除任何数据。\n")
        return 0

    ok = 0
    for p in targets:
        code, _ = api("DELETE", f"/api/plans/{p['id']}")
        if code == 200:
            ok += 1
        else:
            print(f"  [失败] 删除 id={p['id']} -> HTTP {code}")

    code, body = api("GET", "/api/plans")
    print(f"\n删除成功 {ok} 条，剩余 {body.get('total', 0) if body else '?'} 条。\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
