#!/usr/bin/env python3
"""书房阅读器 —— 本地服务器 + MongoDB 阅读进度后端。

静态文件（index.html / books.json / *.txt）照常提供；
另外提供 /api/* 接口，把阅读进度和「最近在读」保存到 MongoDB。

环境变量：
    MONGO_URL   MongoDB 连接串（默认 mongodb://localhost:27017）
    PORT        监听端口（默认 8000）

用法：
    python3 server.py            # 本地运行（需 pip install pymongo）
    docker compose up            # 推荐：一并启动 MongoDB

若 MongoDB 不可用，API 返回 503，前端会自动降级到浏览器 localStorage，
阅读器依然可用。
"""
import os
import sys
import json
import hashlib
import secrets
import webbrowser
from functools import partial
from http.server import HTTPServer, SimpleHTTPRequestHandler

ROOT = os.path.dirname(os.path.abspath(__file__))
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")

# ---------- MongoDB（可选） ----------
_col_prog = None
_col_recent = None
_col_users = None
_col_sessions = None
try:
    from pymongo import MongoClient

    _client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=2000)
    _client.admin.command("ping")  # 立即验证连接
    _db = _client["shufang"]
    _col_prog = _db["progress"]
    _col_recent = _db["recent"]
    _col_users = _db["users"]
    _col_sessions = _db["sessions"]
    # 进度按 (用户, 图书馆, 书号) 唯一；同一书号可跨馆并存
    try:
        _col_prog.drop_index("user_1_bookid_1")  # 迁移旧单馆索引
    except Exception:
        pass
    _col_prog.create_index([("user", 1), ("lib", 1), ("bookid", 1)], unique=True)
    # 迁移旧数据：无 lib 的进度默认归为 cn；recent 的 ids → items
    migrated = 0
    for d in _col_prog.find({"lib": {"$exists": False}}):
        try:
            _col_prog.update_one(
                {"_id": d["_id"]},
                {"$set": {"lib": "cn", "bookid": str(d.get("bookid", ""))}})
            migrated += 1
        except Exception:
            pass
    for r in _col_recent.find({"ids": {"$exists": True}}):
        items = [{"lib": "cn", "bookid": str(x)} for x in r.get("ids", [])]
        _col_recent.update_one(
            {"_id": r["_id"]},
            {"$set": {"items": items}, "$unset": {"ids": ""}})
        migrated += 1
    print(f"已连接 MongoDB: {MONGO_URL}（迁移旧记录 {migrated} 条）", flush=True)
except Exception as e:  # pymongo 缺失或连接失败
    print(f"未连接 MongoDB（将由前端使用 localStorage 降级）: {e}", flush=True)


def mongo_ok():
    return _col_prog is not None


# ---------- 图书馆（多目录） ----------
BOOKS_DIR = os.path.join(ROOT, "books")
LIB_NAMES = {"cn": "中文", "en": "English", "yi": "翻译"}


def list_libraries():
    libs = []
    if os.path.isdir(BOOKS_DIR):
        for name in sorted(os.listdir(BOOKS_DIR)):
            meta = os.path.join(BOOKS_DIR, name, "books.json")
            if os.path.isfile(meta):
                try:
                    n = len(json.load(open(meta, encoding="utf-8")))
                except Exception:
                    n = 0
                libs.append({"id": name, "name": LIB_NAMES.get(name, name), "count": n})
    return libs


# ---------- 密码哈希（标准库 PBKDF2） ----------
def hash_pw(password, salt=None):
    salt = salt or secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                            bytes.fromhex(salt), 120_000).hex()
    return salt, h


def verify_pw(password, salt, expected):
    _, h = hash_pw(password, salt)
    return secrets.compare_digest(h, expected)


class Handler(SimpleHTTPRequestHandler):
    extensions_map = {
        **SimpleHTTPRequestHandler.extensions_map,
        ".txt": "text/plain; charset=utf-8",
        ".json": "application/json; charset=utf-8",
        ".html": "text/html; charset=utf-8",
    }

    # ---------- 工具 ----------
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

    def _auth_user(self):
        """从 Authorization: Bearer <token> 解析已登录用户名，未登录返回 None。"""
        if not mongo_ok():
            return None
        auth = self.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:].strip()
            s = _col_sessions.find_one({"_id": token})
            if s:
                return s["user"]
        return None

    def _user(self):
        """进度归属：已登录 → acct:<用户名>；否则匿名 → anon:<clientId>。"""
        u = self._auth_user()
        if u:
            return "acct:" + u
        from urllib.parse import urlparse, parse_qs
        q = parse_qs(urlparse(self.path).query)
        cid = (q.get("u", ["default"])[0] or "default")[:64]
        return "anon:" + cid

    # ---------- 路由 ----------
    def _dispatch(self, routes, fallback):
        """执行匹配的 API 处理函数；异常统一返回 500 JSON，避免连接被重置。"""
        path = self.path.split("?")[0]
        fn = routes.get(path)
        if fn is None:
            return fallback()
        try:
            return fn()
        except Exception as e:
            import traceback
            traceback.print_exc()
            try:
                return self._send_json({"error": "server-error", "detail": str(e)}, 500)
            except Exception:
                pass

    def do_GET(self):
        def static():
            if self.path in ("/", ""):
                self.path = "/index.html"
            return super(Handler, self).do_GET()
        return self._dispatch({
            "/api/state": self.api_state,
            "/api/me": self.api_me,
            "/api/libraries": lambda: self._send_json(list_libraries()),
        }, static)

    def do_POST(self):
        return self._dispatch({
            "/api/register": self.api_register,
            "/api/login": self.api_login,
            "/api/logout": self.api_logout,
            "/api/progress": self.api_save_progress,
            "/api/recent": self.api_save_recent,
            "/api/delete": self.api_delete,
        }, lambda: self.send_error(404))

    # ---------- 账号 API ----------
    def api_register(self):
        if not mongo_ok():
            return self._send_json({"error": "no-db"}, 503)
        data = self._read_body()
        username = str(data.get("username", "")).strip()
        password = str(data.get("password", ""))
        if not (1 <= len(username) <= 32):
            return self._send_json({"error": "用户名需为 1-32 个字符"}, 400)
        if len(password) < 6:
            return self._send_json({"error": "密码至少 6 位"}, 400)
        if _col_users.find_one({"_id": username}):
            return self._send_json({"error": "该用户名已被注册"}, 409)
        salt, h = hash_pw(password)
        _col_users.insert_one({"_id": username, "salt": salt, "pwhash": h})
        token = self._new_session(username)
        return self._send_json({"ok": True, "token": token, "username": username})

    def api_login(self):
        if not mongo_ok():
            return self._send_json({"error": "no-db"}, 503)
        data = self._read_body()
        username = str(data.get("username", "")).strip()
        password = str(data.get("password", ""))
        u = _col_users.find_one({"_id": username})
        if not u or not verify_pw(password, u["salt"], u["pwhash"]):
            return self._send_json({"error": "用户名或密码错误"}, 401)
        token = self._new_session(username)
        return self._send_json({"ok": True, "token": token, "username": username})

    def api_logout(self):
        if mongo_ok():
            auth = self.headers.get("Authorization", "")
            if auth.startswith("Bearer "):
                _col_sessions.delete_one({"_id": auth[7:].strip()})
        return self._send_json({"ok": True})

    def api_me(self):
        return self._send_json({"username": self._auth_user()})

    def _new_session(self, username):
        token = secrets.token_urlsafe(32)
        _col_sessions.insert_one({"_id": token, "user": username})
        return token

    # ---------- API 实现 ----------
    @staticmethod
    def _libbook(data):
        """从请求体取 (lib, bookid)，均规整为字符串；非法返回 (None, None)。"""
        lib = str(data.get("lib", "")).strip()[:32]
        bid = str(data.get("bookid", "")).strip()[:64]
        return (lib, bid) if lib and bid else (None, None)

    def api_state(self):
        """返回该用户的全部进度与最近在读（按图书馆区分）。"""
        if not mongo_ok():
            return self._send_json({"error": "no-db"}, 503)
        user = self._user()
        prog = {}
        for d in _col_prog.find({"user": user}):
            key = f"{d.get('lib', 'cn')}/{d['bookid']}"
            prog[key] = {"top": d.get("top", 0), "pct": d.get("pct", 0)}
        rec = _col_recent.find_one({"_id": user})
        recent = rec.get("items", []) if rec else []
        return self._send_json({"prog": prog, "recent": recent})

    def api_save_progress(self):
        if not mongo_ok():
            return self._send_json({"error": "no-db"}, 503)
        data = self._read_body()
        lib, bid = self._libbook(data)
        if not lib:
            return self._send_json({"error": "bad-lib-or-bookid"}, 400)
        user = self._user()
        _col_prog.update_one(
            {"user": user, "lib": lib, "bookid": bid},
            {"$set": {
                "top": float(data.get("top", 0)),
                "pct": int(data.get("pct", 0)),
            }},
            upsert=True,
        )
        return self._send_json({"ok": True})

    def api_save_recent(self):
        if not mongo_ok():
            return self._send_json({"error": "no-db"}, 503)
        lib, bid = self._libbook(self._read_body())
        if not lib:
            return self._send_json({"error": "bad-lib-or-bookid"}, 400)
        user = self._user()
        rec = _col_recent.find_one({"_id": user})
        items = rec.get("items", []) if rec else []
        items = [x for x in items if not (x.get("lib") == lib and str(x.get("bookid")) == bid)]
        items.insert(0, {"lib": lib, "bookid": bid})
        items = items[:20]
        _col_recent.update_one({"_id": user}, {"$set": {"items": items}}, upsert=True)
        return self._send_json({"ok": True, "recent": items})

    def api_delete(self):
        """删除一本书的阅读记录：进度 + 最近在读。"""
        if not mongo_ok():
            return self._send_json({"error": "no-db"}, 503)
        lib, bid = self._libbook(self._read_body())
        if not lib:
            return self._send_json({"error": "bad-lib-or-bookid"}, 400)
        user = self._user()
        _col_prog.delete_one({"user": user, "lib": lib, "bookid": bid})
        rec = _col_recent.find_one({"_id": user})
        items = rec.get("items", []) if rec else []
        items = [x for x in items if not (x.get("lib") == lib and str(x.get("bookid")) == bid)]
        if rec:
            _col_recent.update_one({"_id": user}, {"$set": {"items": items}})
        return self._send_json({"ok": True, "recent": items})

    def list_directory(self, path):
        self.send_error(403, "Directory listing disabled")
        return None

    def log_message(self, fmt, *args):
        pass


def main():
    port = int(os.environ.get("PORT", 8000))
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print("端口需为数字，例如: python3 server.py 8888")
            return

    handler = partial(Handler, directory=ROOT)
    httpd = HTTPServer(("0.0.0.0", port), handler)
    url = f"http://127.0.0.1:{port}/"
    print(f"书房阅读器已启动 → {url}")
    print("按 Ctrl+C 停止")
    # 仅本地运行时尝试开浏览器（容器内无桌面环境）
    if not os.environ.get("IN_DOCKER"):
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")


if __name__ == "__main__":
    main()
