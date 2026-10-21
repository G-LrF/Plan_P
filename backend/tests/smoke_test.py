"""
真实 HTTP 冒烟测试 —— 验证服务"真的能通过网络被访问"

【怎么运行】
    先启动后端（另开一个终端）：
        cd backend
        ..\\.venv\\Scripts\\python.exe -m uvicorn app.main:app --reload

    再运行本脚本：
        ..\\.venv\\Scripts\\python.exe tests\\smoke_test.py

    后端不在默认地址时，可以指定：
        ..\\.venv\\Scripts\\python.exe tests\\smoke_test.py http://127.0.0.1:8002

==========================================================================
【和 tests/test_api.py 有什么区别？两者都要跑，各管一段】
--------------------------------------------------------------------------
    test_api.py   进程内测试：把请求直接交给 ASGI 应用，不经过端口。
                  → 证明"代码逻辑对不对"
    smoke_test.py 真实网络测试：真的连 TCP 端口、真的发 HTTP 报文。
                  → 证明"服务确实跑起来了、端口通、网络链路没问题"

   【为什么两个都要有】它们会抓到不同的问题：
     - test_api.py 全过，但 uvicorn 起不来        -> 只有冒烟测试能发现
     - 端口通了，但业务逻辑有 bug                 -> 只有 test_api.py 能精确定位
   企业里这叫"测试分层"：单元测试管逻辑，集成/冒烟测试管链路。

   【为什么用 urllib 而不是 requests】
     零第三方依赖。urllib 是 Python 标准库自带的，够用。
==========================================================================
"""

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid

# 修正 Windows 控制台中文乱码（和 test_api.py 同样的处理）
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

# 后端地址：可以从命令行参数传入，默认 8000
BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"

# ---------------------------------------------------------------------------
# 【重要设计】给每次运行生成一个唯一标记
# ---------------------------------------------------------------------------
# 【为什么必须这样做】这是我在本机踩到的一个真实教训：
#   第一次运行时，搜索"冒烟测试"返回了 2 条而不是 1 条 ——
#   因为上一轮测试遗留的数据也命中了同样的关键词，测试就失败了。
#   但【代码其实没有问题】，是我的测试写得不严谨。
#
#   如果测试依赖"数据库是干净的"，那么在别人机器上、在 CI 里、
#   在生产库旁边跑，结果就会千奇百怪。这种测试叫"脆弱的测试"
#   (flaky test)，它会消耗团队大量时间去排查假故障。
#
#   正确做法：测试自己造数据、自己认数据、自己清数据，
#   对"环境里已有什么"完全免疫。用 uuid 生成唯一标记是最简单的实现。
RUN_TAG = uuid.uuid4().hex[:8]          # 例如 "a3f91c2b"
TEST_TITLE = f"冒烟测试-{RUN_TAG}"       # 这个标题保证全局唯一
TEST_CONTENT = "验证真实网络链路"

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


def call(method: str, path: str, payload: dict | None = None, origin: str | None = None):
    """发一个真实 HTTP 请求。

    返回 (状态码, 解析后的响应体, 响应头字典)。
    【重要】即使后端返回 4xx/5xx，也不抛异常，而是把状态码正常返回 ——
    因为"返回 404"本身就是要验证的行为之一，不是错误。
    """
    url = f"{BASE_URL}{path}"
    data = None
    headers = {"Accept": "application/json"}

    if payload is not None:
        # 【编码要点】JSON 里可能有中文，必须 ensure_ascii=False 才能保持可读；
        # 并且要显式声明 charset=utf-8，否则后端可能按 latin-1 解码导致乱码。
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"

    if origin:
        headers["Origin"] = origin

    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            raw = resp.read()
            body = json.loads(raw.decode("utf-8")) if raw else None
            return resp.status, body, dict(resp.headers)
    except urllib.error.HTTPError as e:
        # 服务端返回了 4xx/5xx —— 这也是有效响应，正常解析
        raw = e.read()
        try:
            body = json.loads(raw.decode("utf-8")) if raw else None
        except json.JSONDecodeError:
            body = None
        return e.code, body, dict(e.headers)
    except urllib.error.URLError as e:
        # 连不上：服务没启动 / 端口不对 / 被防火墙拦
        print(f"\n  [致命] 无法连接到 {BASE_URL} -> {e.reason}")
        print("         请先启动后端：")
        print("           cd backend")
        print("           ..\\.venv\\Scripts\\python.exe -m uvicorn app.main:app --reload\n")
        raise SystemExit(2)


def main() -> int:
    print(f"\n目标后端：{BASE_URL}")
    print(f"本次运行标记：{RUN_TAG}（用于造数据 + 收尾自清理）")
    print("=" * 56)

    # 记录本次自建数据的 id，供 finally 阶段清理
    created_ids: list[int] = []

    try:
        print("\n=== 1. 健康检查 GET /api/health ===")
        code, body, _ = call("GET", "/api/health")
        check("状态码 200", code == 200, f"实际 {code}")
        check("status=ok", (body or {}).get("status") == "ok", str(body))

        print("\n=== 2. 列表 GET /api/plans ===")
        code, body, _ = call("GET", "/api/plans")
        check("状态码 200", code == 200, f"实际 {code}")
        check("含 total / data", "total" in (body or {}) and "data" in (body or {}), str(body))
        initial_total = (body or {}).get("total", 0)
        # 【本次接数据库后修正】原来这里检查"响应里有'学习 Python'这个标题"，
        # 但数据库初始是空的，这个假设不再成立。
        # 现在改为：等下用中文标题创建数据后再验证中文没乱码（见第 5 步）。
        # 这样无论库里有什么，检查都有效。
        print(f"        （当前库里已有 {initial_total} 条数据）")

        print("\n=== 3. 边界：不存在 -> 404 ===")
        code, body, _ = call("GET", "/api/plans/999999")
        check("状态码 404", code == 404, f"实际 {code}")

        print("\n=== 5. 校验：空标题 -> 422 ===")
        code, body, _ = call("POST", "/api/plans", {"title": "", "content": "x"})
        check("状态码 422", code == 422, f"实际 {code}")

        print("\n=== 6. 创建 POST（含中文，标题带唯一标记）===")
        print(f"        本次运行标记：{RUN_TAG}  -> 标题：{TEST_TITLE}")
        code, body, _ = call(
            "POST", "/api/plans",
            {"title": TEST_TITLE, "content": TEST_CONTENT},
        )
        check("状态码 201", code == 201, f"实际 {code}")
        check("返回 id", isinstance((body or {}).get("id"), int), str(body))
        check("中文被正确保存", (body or {}).get("title") == TEST_TITLE, str(body))
        check("初始 status=0", (body or {}).get("status") == 0, str(body))
        new_id = (body or {}).get("id")
        if isinstance(new_id, int):
            created_ids.append(new_id)

        print("\n=== 7. 搜索（用唯一标记搜，只可能命中自己）===")
        # 【为什么搜 RUN_TAG 而不是搜"冒烟测试"】
        #   搜唯一标记 -> 无论环境里有什么历史数据，都只会命中本次创建的那条。
        #   搜宽泛关键词 -> 会命中历史遗留数据，测试结果不可复现。
        # 关键词统一走 URL 编码：现在是 ASCII 标记，但保持编码写法，
        # 将来换成中文关键词时就不会因为忘了编码而直接报错。
        kw = urllib.parse.quote(RUN_TAG)
        code, body, _ = call("GET", f"/api/plans/search?keyword={kw}")
        check("状态码 200", code == 200, f"实际 {code}")
        check("恰好搜到 1 条（证明搜索精确）", (body or {}).get("total") == 1, str(body))

        print("\n=== 8. 更新 PUT（标记完成）===")
        code, body, _ = call(
            "PUT", f"/api/plans/{new_id}",
            {"title": TEST_TITLE, "content": TEST_CONTENT, "status": 1},
        )
        check("状态码 200", code == 200, f"实际 {code}")
        check("status 变为 1", (body or {}).get("status") == 1, str(body))

        print("\n=== 9. 更新不存在的 ID -> 404 ===")
        code, _, _ = call(
            "PUT", "/api/plans/999999",
            {"title": "x", "content": "y", "status": 0},
        )
        check("状态码 404", code == 404, f"实际 {code}")

        print("\n=== 10. 删除 DELETE ===")
        code, body, _ = call("DELETE", f"/api/plans/{new_id}")
        check("状态码 200", code == 200, f"实际 {code}")
        if code == 200:
            created_ids.remove(new_id)   # 已删除，无需再清理
        code, _, _ = call("GET", f"/api/plans/{new_id}")
        check("删除后查询 404", code == 404, f"实际 {code}")
        code, _, _ = call("DELETE", f"/api/plans/{new_id}")
        check("重复删除也 404", code == 404, f"实际 {code}")

        print("\n=== 11. CORS 响应头（模拟浏览器直连）===")
        code, _, headers = call("GET", "/api/health", origin="http://localhost:5173")
        acao = headers.get("Access-Control-Allow-Origin") or headers.get(
            "access-control-allow-origin"
        )
        check(
            "返回 Access-Control-Allow-Origin",
            acao == "http://localhost:5173",
            f"实际 {acao!r}",
        )

        print("\n=== 12. 收尾一致性 ===")
        code, body, _ = call("GET", "/api/plans")
        check("总数回到初始值", (body or {}).get("total") == initial_total, str(body))

    finally:
        # -------------------------------------------------------------------
        # 【自清理】放在 finally 里，保证"无论测试成功、失败还是中途抛异常"
        # 都会执行。这样反复运行测试不会往数据里堆垃圾。
        #
        # 这里也顺便演示了一个真实工程习惯：
        #   凡是"测试自己创建的数据"，测试就有责任把它清掉。
        #   否则跑一百次测试，库里就有两百条垃圾，之后没人敢动这个库。
        # -------------------------------------------------------------------
        if created_ids:
            print(f"\n[清理] 移除本次测试创建的遗留数据：{created_ids}")
            for pid in created_ids:
                call("DELETE", f"/api/plans/{pid}")

    print("\n" + "=" * 56)
    print(f"  真实 HTTP 冒烟测试：{passed} 项通过，{failed} 项失败")
    print("=" * 56)
    if failed:
        print("  [X] 有失败项，请按上面的详情排查。\n")
        return 1
    print("  [OK] 服务真的能通过网络访问，前后端联调的基础已就绪。\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
