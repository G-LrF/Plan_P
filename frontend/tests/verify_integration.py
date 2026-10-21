"""
前端联调验证脚本 —— 验证"浏览器 → Vite 代理 → FastAPI"这条链路真的通了

【怎么运行】（在 frontend 目录下，需要后端和 Vite 开发服务器都已启动）
    ..\\.venv\\Scripts\\python.exe tests\\verify_integration.py
    ..\\.venv\\Scripts\\python.exe tests\\verify_integration.py http://localhost:5174

【它在验证什么 · 这是本轮任务的核心证据】
    这个脚本【不直接连后端】，而是连 Vite 开发服务器的端口，
    请求 /api/... 路径。如果它能拿到后端的数据，就证明了：

        浏览器视角的请求  →  Vite 代理  →  FastAPI  →  返回数据

    这条链路是通的，也就是"前后端真的联调上了"。

【如果没有这个脚本，你怎么验证】
    只能打开浏览器 → F12 → Network 面板 → 点各种按钮 → 肉眼看。
    能验证，但每次改动都要重复一遍，而且没法自动化、没法留证据。
    把它写成脚本，就变成了"一条命令出结论"。
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

FRONTEND_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5173"

passed = 0
failed = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global passed, failed
    if condition:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}  <-- 详情: {detail}")


def call(method: str, path: str, payload: dict | None = None):
    """向【前端服务器】发请求。注意：不是直接连后端。

    返回 (状态码, 解析后的响应体, 原始文本)。
    """
    url = f"{FRONTEND_URL}{path}"
    data = None
    headers = {"Accept": "application/json, text/html"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read()
            text = raw.decode("utf-8", errors="replace")
            try:
                return resp.status, json.loads(text), text
            except json.JSONDecodeError:
                return resp.status, None, text
    except urllib.error.HTTPError as e:
        raw = e.read()
        text = raw.decode("utf-8", errors="replace")
        try:
            return e.code, json.loads(text), text
        except json.JSONDecodeError:
            return e.code, None, text
    except urllib.error.URLError as e:
        print(f"\n  [致命] 连不上前端服务器 {FRONTEND_URL} -> {e.reason}")
        print("         请确认 Vite 开发服务器已启动：")
        print("           cd frontend")
        print("           npm run dev")
        print("         并注意 Vite 打印的实际端口（5173 被占用时会自动换端口）\n")
        raise SystemExit(2)


def main() -> int:
    print(f"\n目标前端服务器：{FRONTEND_URL}")
    print("=" * 60)

    print("\n=== 1. 前端页面能加载 HTML ===")
    code, _, html = call("GET", "/")
    check("状态码 200", code == 200, f"实际 {code}")
    # Vite 的 index.html 里一定有挂载点（Vue 应用就挂在这个 div 上）
    check(
        "HTML 含 Vue 挂载点 <div id=\"app\">",
        'id="app"' in html,
        html[:200],
    )
    check(
        "HTML 引入了入口脚本 /src/main.js",
        "/src/main.js" in html,
        html[:300],
    )

    print("\n=== 2. 入口脚本 main.js 能被服务器编译返回 ===")
    code, _, js = call("GET", "/src/main.js")
    check("状态码 200", code == 200, f"实际 {code}")
    check("内容是 JavaScript", "createApp" in js or "import" in js, js[:200])

    print("\n=== 3. ★ 代理转发：/api/plans 能拿到后端数据 ===")
    # 这是整个验证的核心。请求发给了 Vite（前端服务器），
    # 如果 Vite 代理配置正确，它会转发给后端并把数据带回来。
    code, body, text = call("GET", "/api/plans")
    check("状态码 200", code == 200, f"实际 {code} | {text[:200]}")
    check("响应是 JSON（不是 HTML 错误页）", body is not None, text[:200])
    if body:
        check("含 total 字段", "total" in body, text[:200])
        check("含 data 数组", isinstance(body.get("data"), list), text[:200])
        # 如果这里拿到的还是 Vite 自己的 index.html，说明代理没生效 ——
        # 这是最常见的"配了 proxy 但没重启 dev server"症状。
        check(
            "不是前端页面（证明真的转发到后端了）",
            "id=\"app\"" not in text,
            "拿到的是 index.html，说明代理没生效 —— 检查是否重启了 dev server",
        )

    print("\n=== 4. 通过代理创建计划（POST 也能转发）===")
    code, body, text = call(
        "POST", "/api/plans",
        {"title": "代理链路验证", "content": "经 Vite 代理写入"},
    )
    check("状态码 201", code == 201, f"实际 {code} | {text[:200]}")
    new_id = (body or {}).get("id")
    check("返回了 id", isinstance(new_id, int), text[:200])

    print("\n=== 5. 通过代理读取刚写入的数据 ===")
    code, body, text = call("GET", f"/api/plans/{new_id}")
    check("状态码 200", code == 200, f"实际 {code}")
    check("标题正确", (body or {}).get("title") == "代理链路验证", text[:200])

    print("\n=== 6. 通过代理删除（清理）===")
    code, _, text = call("DELETE", f"/api/plans/{new_id}")
    check("状态码 200", code == 200, f"实际 {code} | {text[:200]}")
    code, _, _ = call("GET", f"/api/plans/{new_id}")
    check("删除后 404", code == 404, f"实际 {code}")

    print("\n=== 7. 代理下的健康检查 ===")
    code, body, _ = call("GET", "/api/health")
    check("状态码 200", code == 200, f"实际 {code}")
    check("status=ok", (body or {}).get("status") == "ok", str(body))

    print("\n" + "=" * 60)
    print(f"  前后端联调验证：{passed} 项通过，{failed} 项失败")
    print("=" * 60)
    if failed:
        print("  [X] 有失败项。常见原因：")
        print("      - Vite dev server 在改完 vite.config.js 后没重启")
        print("      - 后端没启动，或代理 target 端口写错")
        print("      - 访问的端口不是 Vite 实际打印的端口\n")
        return 1
    print("  [OK] 浏览器 → Vite 代理 → FastAPI 链路完全打通。\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
