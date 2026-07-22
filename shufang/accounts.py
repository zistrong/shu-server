"""账号 API：注册 / 登录 / 登出 / 当前用户。"""
import secrets

from . import db
from .base import route, needs_db
from .security import hash_pw, verify_pw


class AccountMixin:
    @route("POST", "/api/register")
    @needs_db
    def api_register(self):
        data = self._read_body()
        username = str(data.get("username", "")).strip()
        password = str(data.get("password", ""))
        if not (1 <= len(username) <= 32):
            return self._send_json({"error": "用户名需为 1-32 个字符"}, 400)
        if len(password) < 6:
            return self._send_json({"error": "密码至少 6 位"}, 400)
        if db.col_users.find_one({"_id": username}):
            return self._send_json({"error": "该用户名已被注册"}, 409)
        salt, h = hash_pw(password)
        db.col_users.insert_one({"_id": username, "salt": salt, "pwhash": h})
        token = self._new_session(username)
        return self._send_json({"ok": True, "token": token, "username": username})

    @route("POST", "/api/login")
    @needs_db
    def api_login(self):
        data = self._read_body()
        username = str(data.get("username", "")).strip()
        password = str(data.get("password", ""))
        u = db.col_users.find_one({"_id": username})
        if not u or not verify_pw(password, u["salt"], u["pwhash"]):
            return self._send_json({"error": "用户名或密码错误"}, 401)
        token = self._new_session(username)
        return self._send_json({"ok": True, "token": token, "username": username})

    @route("POST", "/api/logout")
    def api_logout(self):
        if db.mongo_ok():
            auth = self.headers.get("Authorization", "")
            if auth.startswith("Bearer "):
                db.col_sessions.delete_one({"_id": auth[7:].strip()})
        return self._send_json({"ok": True})

    @route("GET", "/api/me")
    def api_me(self):
        return self._send_json({"username": self._auth_user()})

    def _new_session(self, username):
        token = secrets.token_urlsafe(32)
        db.col_sessions.insert_one({"_id": token, "user": username})
        return token
