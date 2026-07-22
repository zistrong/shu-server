"""HTTP 基础设施：请求工具、用户身份、路由注册与分发。

各功能模块用 @route(method, path) 注册处理方法，导入时写入下方路由表；
BaseHandler 在请求时按路径分发，未匹配的 GET 回退到静态文件。
@needs_db 包装需要数据库的处理方法，无库时统一返回 503。
"""
import json
import functools
import traceback
from urllib.parse import urlparse, parse_qs
from http.server import SimpleHTTPRequestHandler

from . import db

# 路由表：path -> 方法名。由 @route 在各功能模块导入时填充。
GET_ROUTES = {}
POST_ROUTES = {}


def route(method, path):
    """把被装饰的处理方法注册到路由表。"""
    table = GET_ROUTES if method.upper() == "GET" else POST_ROUTES

    def deco(fn):
        table[path] = fn.__name__
        return fn
    return deco


def needs_db(fn):
    """需要 MongoDB 的处理方法：无库时返回 503。"""
    @functools.wraps(fn)
    def wrap(self, *a, **kw):
        if not db.mongo_ok():
            return self._send_json({"error": "no-db"}, 503)
        return fn(self, *a, **kw)
    return wrap


class BaseHandler(SimpleHTTPRequestHandler):
    extensions_map = {
        **SimpleHTTPRequestHandler.extensions_map,
        ".txt": "text/plain; charset=utf-8",
        ".json": "application/json; charset=utf-8",
        ".html": "text/html; charset=utf-8",
    }

    # ---------- 请求工具 ----------
    def _send_json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception:
            return {}

    @staticmethod
    def _libbook(data):
        """从请求体取 (lib, bookid)，均规整为字符串；非法返回 (None, None)。"""
        lib = str(data.get("lib", "")).strip()[:32]
        bid = str(data.get("bookid", "")).strip()[:64]
        return (lib, bid) if lib and bid else (None, None)

    # ---------- 用户身份 ----------
    def _auth_user(self):
        """从 Authorization: Bearer <token> 解析已登录用户名，未登录返回 None。"""
        if not db.mongo_ok():
            return None
        auth = self.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:].strip()
            s = db.col_sessions.find_one({"_id": token})
            if s:
                return s["user"]
        return None

    def _user(self):
        """归属：已登录 → acct:<用户名>；否则匿名 → anon:<clientId>。"""
        u = self._auth_user()
        if u:
            return "acct:" + u
        q = parse_qs(urlparse(self.path).query)
        cid = (q.get("u", ["default"])[0] or "default")[:64]
        return "anon:" + cid

    # ---------- 路由分发 ----------
    def _dispatch(self, routes, fallback):
        """执行匹配的处理方法；异常统一返回 500 JSON，避免连接被重置。"""
        path = self.path.split("?")[0]
        name = routes.get(path)
        if name is None:
            return fallback()
        try:
            return getattr(self, name)()
        except Exception as e:
            traceback.print_exc()
            try:
                return self._send_json({"error": "server-error", "detail": str(e)}, 500)
            except Exception:
                pass

    def do_GET(self):
        def static():
            if self.path in ("/", ""):
                self.path = "/index.html"
            return SimpleHTTPRequestHandler.do_GET(self)
        return self._dispatch(GET_ROUTES, static)

    def do_POST(self):
        return self._dispatch(POST_ROUTES, lambda: self.send_error(404))

    def list_directory(self, path):
        self.send_error(403, "Directory listing disabled")
        return None

    def log_message(self, fmt, *args):
        pass
