"""
后端接口自动化测试 —— 一条命令验证全部接口是否正常

【怎么运行】（在 backend 目录下）
    ..\\.venv\\Scripts\\python.exe tests\\test_api.py

【为什么要有这个文件】
    没有测试时，验证接口的唯一办法是打开浏览器 → 点 Swagger → 手点一遍。
    改一次代码点一遍，改三次就漏了，而且你无法证明"我改完老功能还是好的"。
    有了它，改完代码跑一条命令，几秒内告诉你 30 多项检查是否全过。

    这就是"可回归"：每次改动后自动确认老功能没被改坏。
    企业里把这套东西放进 CI（持续集成）流水线，每次提交代码自动跑。
    你在本地做的，其实就是 CI 的雏形。

================================ 重要说明 ================================
【为什么不用 FastAPI 官方的 TestClient】
    Starlette 1.x 的 TestClient 底层要求安装 httpx2 这个包。
    我们尝试安装时被本机环境的权限限制挡住了（pip 无法在临时目录创建文件），
    属于环境问题，不是代码问题。

    所以这里改为【用标准库自己实现一个极简 ASGI 客户端】。
    好处：
      1. 零第三方依赖 —— 符合"不引入不必要依赖"的要求
      2. 顺带把 HTTP 请求在 Python 里到底怎么走的看明白，这在企业里很值钱
    代价：
      它只是"够测试用"的极简实现，不覆盖流式响应、文件上传等场景。

【将来想换回官方 TestClient 时】
    1. pip install httpx2
    2. 把下面 "★ 切换点 A" 的两行替换为：
           from fastapi.testclient import TestClient
           client = TestClient(app)
    3. 代码里的 client.get(...) / client.post(...) 调用方式完全不用改，
       因为我们的迷你客户端故意模仿了 TestClient 的接口签名。
    —— 这种"接口长得一样、实现可以替换"的设计，正是企业里
       "面向接口编程"的朴素版本。

【⚠️ 诚实的边界说明】
    这是"进程内测试"：请求直接交给 FastAPI 的 ASGI 应用处理，不经过真实端口。
    所以它能证明：
        ✅ 路由匹配、参数校验、业务逻辑、CORS 响应头都正确
    它不能证明：
        ❌ uvicorn 真的能在 8000 端口起起来、防火墙没拦、浏览器能连上
    后者由真实 HTTP 冒烟测试覆盖，两层验证都要做。
==========================================================================
"""

import asyncio
import json
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# 修正 Windows 控制台中文乱码
# ---------------------------------------------------------------------------
# 【为什么需要】Windows 的 PowerShell/CMD 默认代码页是 GBK(936)，
# 而我们的源码文件是 UTF-8。Python 往控制台写字时按 GBK 编码，
# 中文就变成 "�" 这种乱码。日志看不懂，等于白打。
# reconfigure(encoding="utf-8") 强制标准输出用 UTF-8。
# 【真实场景】这是 Windows 上跑中文日志的经典坑；Linux/Docker 里默认就是
# UTF-8，所以同一份代码在服务器上正常、在本地乱码，很多人因此找了半天。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass  # 极端环境下不支持就跳过，不让它影响测试本身

# 把 backend 目录加入模块搜索路径，这样无论从哪里运行脚本都能 import app 包。
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.main import app  # noqa: E402


# ===========================================================================
# 迷你 ASGI 客户端（零第三方依赖）
# ===========================================================================
class Response:
    """模拟一个 HTTP 响应对象，接口对齐 requests / TestClient 的用法。"""

    def __init__(self, status_code: int, headers: dict, body: bytes):
        self.status_code = status_code
        self.headers = headers   # 键统一转成了小写，方便查找
        self.body = body

    @property
    def text(self) -> str:
        """响应正文的字符串形式，失败时打在日志里方便排查。"""
        return self.body.decode("utf-8", errors="replace")

    def json(self):
        """把 JSON 正文解析成 Python 对象。"""
        return json.loads(self.body.decode("utf-8"))


class MiniClient:
    """够测试用的极简 ASGI 客户端。

    【原理】ASGI 规定，一个应用就是一个可调用对象：
        app(scope, receive, send)
    - scope：  本次请求的元信息（方法、路径、请求头…），本质是个字典
    - receive：应用用它来"接收"请求体，调用后返回一个消息字典
    - send：   应用用它来"发出"响应，调用时传入消息字典

    所以"发一个 HTTP 请求"在这里就变成了：
        准备 scope → 调用 app → 从 send 里收集响应
    这层理解很重要：FastAPI/Starlette/Django 的底层都是这套协议，
    看懂它，以后遇到"框架报错看不懂"的情况，能顺着协议往下查。
    """

    def __init__(self, app):
        self.app = app

    async def request(
        self,
        method: str,
        path: str,
        params: dict | None = None,
        json_body: dict | None = None,
        headers: dict | None = None,
    ) -> Response:
        # --- 1. 拼接查询字符串（?keyword=xxx），并进行 URL 编码 ---
        query = b""
        if params:
            from urllib.parse import urlencode

            query = urlencode(params).encode("utf-8")

        # --- 2. 准备请求体 ---
        if json_body is not None:
            body = json.dumps(json_body).encode("utf-8")
            # 必须声明 Content-Type，否则 FastAPI 不知道该怎么解析请求体
            content_type = b"application/json"
        else:
            body = b""
            content_type = b""

        # --- 3. 构造请求头（ASGI 要求全部是 bytes 键值对）---
        raw_headers = [(k.lower().encode("latin-1"), v.encode("latin-1"))
                       for k, v in (headers or {}).items()]
        if content_type:
            raw_headers.append((b"content-type", content_type))

        # --- 4. 构造 scope：本次请求的"身份证" ---
        scope = {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": method.upper(),
            "path": path,
            "raw_path": path.encode("utf-8"),
            "query_string": query,
            "root_path": "",
            "headers": raw_headers,
            "client": ("127.0.0.1", 12345),   # 假装是本地浏览器
            "server": ("127.0.0.1", 8000),
            "scheme": "http",
        }

        # --- 5. receive：负责把请求体"喂"给应用 ---
        # ASGI 要求调用方在数据发完后返回 http.disconnect。
        # 用列表当可变标志位，是为了在闭包里能修改它（Python 闭包的经典写法）。
        body_sent = [False]

        async def receive():
            if not body_sent[0]:
                body_sent[0] = True
                return {"type": "http.request", "body": body, "more_body": False}
            return {"type": "http.disconnect"}

        # --- 6. send：收集应用吐出来的响应 ---
        response_started = {}
        body_parts = []

        async def send(message):
            if message["type"] == "http.response.start":
                response_started["status"] = message["status"]
                response_started["headers"] = message.get("headers", [])
            elif message["type"] == "http.response.body":
                body_parts.append(message.get("body", b""))
                # more_body=True 表示后面还有数据（流式响应）。
                # 我们的接口都是小 JSON，一次就发完了，所以这里不用循环等待。

        await self.app(scope, receive, send)

        # --- 7. 组装成友好的 Response 对象 ---
        resp_headers = {
            k.decode("latin-1").lower(): v.decode("latin-1")
            for k, v in response_started.get("headers", [])
        }
        return Response(
            status_code=response_started.get("status", 0),
            headers=resp_headers,
            body=b"".join(body_parts),
        )

    # --- 下面四个方法让调用写起来和官方 TestClient 一样 ---
    def get(self, path, params=None, headers=None):
        return asyncio.run(self.request("GET", path, params=params, headers=headers))

    def post(self, path, json_body=None, headers=None):
        return asyncio.run(self.request("POST", path, json_body=json_body, headers=headers))

    def put(self, path, json_body=None, headers=None):
        return asyncio.run(self.request("PUT", path, json_body=json_body, headers=headers))

    def delete(self, path, headers=None):
        return asyncio.run(self.request("DELETE", path, headers=headers))


# ★ 切换点 A：想换回官方 TestClient 时，把上面这一整段换掉即可
client = MiniClient(app)


# ===========================================================================
# 测试主体
# ===========================================================================
passed = 0
failed = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    """做一个检查：通过打 [PASS]，失败打 [FAIL] 并附上详情。

    【为什么用布尔值而不是直接 assert】
    assert 一旦失败就中断，你一次只能看到一个错误。
    这样写即使某项失败也会继续跑完，你能一次看到【所有】问题，
    避免"修一个跑一次、修一个跑一次"的来回折腾。
    """
    global passed, failed
    if condition:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}  <-- 详情: {detail}")


def main() -> int:
    print("\n=== 1. 健康检查 GET /api/health ===")
    r = client.get("/api/health")
    check("状态码 200", r.status_code == 200, f"实际 {r.status_code}")
    check("返回 status=ok", r.json().get("status") == "ok", r.text)
    # 真实案例：曾有团队把健康检查写成"要查一次数据库"，数据库一慢，
    # K8s 以为服务挂了就把 Pod 重启，反而造成雪崩。健康检查必须轻量。

    print("\n=== 2. 列表 GET /api/plans ===")
    r = client.get("/api/plans")
    check("状态码 200", r.status_code == 200, f"实际 {r.status_code}")
    body = r.json()
    check("含 total 字段", "total" in body, r.text)
    check("含 data 字段且是列表", isinstance(body.get("data"), list), r.text)
    check("total 与 data 长度一致", body.get("total") == len(body.get("data", [])), r.text)
    initial_total = body.get("total", 0)
    print(f"        （当前初始数据 {initial_total} 条）")

    print("\n=== 3. 单条 GET /api/plans/1 ===")
    r = client.get("/api/plans/1")
    check("状态码 200", r.status_code == 200, f"实际 {r.status_code}")
    check("id 匹配", r.json().get("id") == 1, r.text)

    print("\n=== 4. 边界：不存在的 ID 应返回 404 ===")
    r = client.get("/api/plans/9999")
    check("状态码 404", r.status_code == 404, f"实际 {r.status_code}")
    # 验证"失败时给明确信号"，而不是假装成功返回空数据。
    # 否则前端会把空数据当正常内容渲染，用户以为数据丢了。

    print("\n=== 5. 参数校验：非法请求应返回 422 ===")
    r = client.post("/api/plans", json_body={"title": "", "content": "内容"})
    check("空标题 -> 422", r.status_code == 422, f"实际 {r.status_code}")
    r = client.post("/api/plans", json_body={"title": "只有标题"})
    check("缺字段 -> 422", r.status_code == 422, f"实际 {r.status_code}")
    r = client.post("/api/plans", json_body={"title": 123, "content": "内容"})
    check("类型错误 -> 422", r.status_code == 422, f"实际 {r.status_code}")
    # 这三项证明"校验层真的在工作"，是接口健壮性的证据。
    # 注意：这些校验代码我们一行都没写，全部由 Pydantic 根据 schema.py 自动完成。

    print("\n=== 6. 创建 POST /api/plans ===")
    r = client.post("/api/plans", json_body={"title": "测试计划", "content": "自动化测试创建"})
    check("状态码 201", r.status_code == 201, f"实际 {r.status_code}")
    created = r.json()
    check("返回了整数 id", isinstance(created.get("id"), int), r.text)
    check("初始 status 为 0", created.get("status") == 0, r.text)
    check("title 已保存", created.get("title") == "测试计划", r.text)
    new_id = created.get("id")
    # 客户端没传 id 和 status，是后端补上的 —— 验证"安全边界"设计生效。

    print("\n=== 7. 搜索 GET /api/plans/search ===")
    r = client.get("/api/plans/search", params={"keyword": "测试计划"})
    check("状态码 200", r.status_code == 200, f"实际 {r.status_code}")
    check("能搜到刚创建的计划", r.json().get("total") == 1, r.text)
    # 这是"路由顺序陷阱"的回归测试：
    # 若 /plans/{plan_id} 注册在 /plans/search 之前，字符串 "search" 会
    # 被当成路径参数去转 int 而失败 → 返回 422，这一项就会 FAIL。
    check("未被动态路由误吞（不是 422）", r.status_code != 422, r.text)

    r = client.get("/api/plans/search", params={"keyword": "不存在的关键词xyz"})
    check("无结果时 total=0", r.json().get("total") == 0, r.text)

    r = client.get("/api/plans/search")
    check("不传关键词 -> 返回全部", r.json().get("total") == initial_total + 1, r.text)

    print("\n=== 8. 更新 PUT /api/plans/{id} ===")
    r = client.put(
        f"/api/plans/{new_id}",
        json_body={"title": "测试计划(已更新)", "content": "内容也改了", "status": 1},
    )
    check("状态码 200", r.status_code == 200, f"实际 {r.status_code}")
    check("title 已更新", r.json().get("title") == "测试计划(已更新)", r.text)
    check("status 已更新", r.json().get("status") == 1, r.text)
    # 更新后再查一次：确认真的写进数据了，而不是只改了返回值。
    # 这种"改完再读回来验证"的思路，在真实项目里能抓住大量隐蔽 bug。
    r = client.get(f"/api/plans/{new_id}")
    check("重新查询确认已写入数据", r.json().get("status") == 1, r.text)

    r = client.put(
        "/api/plans/9999",
        json_body={"title": "x", "content": "y", "status": 0},
    )
    check("更新不存在的 ID -> 404", r.status_code == 404, f"实际 {r.status_code}")

    print("\n=== 9. CORS 预检（带 Origin 请求头）===")
    r = client.get("/api/health", headers={"Origin": "http://localhost:5173"})
    allow_origin = r.headers.get("access-control-allow-origin")
    check(
        "返回了 CORS 放行头",
        allow_origin == "http://localhost:5173",
        f"实际 access-control-allow-origin={allow_origin!r}",
    )
    # 证明后端确实在告诉浏览器"这个跨域来源我允许"。
    # 如果漏配 CORSMiddleware，这里的值会是 None，浏览器就会拦掉请求。

    print("\n=== 10. 删除 DELETE /api/plans/{id} ===")
    r = client.delete(f"/api/plans/{new_id}")
    check("状态码 200", r.status_code == 200, f"实际 {r.status_code}")
    check("返回了被删除的对象", r.json().get("data", {}).get("id") == new_id, r.text)
    r = client.get(f"/api/plans/{new_id}")
    check("删除后查询 -> 404", r.status_code == 404, f"实际 {r.status_code}")
    r = client.delete(f"/api/plans/{new_id}")
    check("重复删除 -> 404", r.status_code == 404, f"实际 {r.status_code}")
    # 重复删除也报 404：说明不会静默成功骗前端。

    print("\n=== 11. 收尾一致性检查 ===")
    r = client.get("/api/plans")
    check("删除后总数回到初始值", r.json().get("total") == initial_total, r.text)

    print("\n" + "=" * 50)
    print(f"  测试结果：{passed} 项通过，{failed} 项失败")
    print("=" * 50)
    if failed:
        print("  [X] 有失败项，请按上面的详情修正后再继续。\n")
        return 1
    print("  [OK] 全部通过，后端接口可以被前端安全调用。\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
