"""微信开放平台扫码登录。

流程（标准 OAuth2）：
    1. 前端 GET /api/wechat/login → 服务端生成 state 并返回
       微信扫码页地址（https://open.weixin.qq.com/connect/qrconnect）；
    2. 前端弹窗打开该地址，用户扫码授权后微信把浏览器重定向到
       /api/wechat/callback?code=...&state=...；
    3. 服务端校验 state，用 code 向微信换取 openid（必要时再取昵称头像），
       按 openid 查找或创建用户，签发本应用的登录 token；
    4. 302 重定向到 /wechat.html，由该页把结果 postMessage 回主窗口并自动关闭。

未配置 WECHAT_APPID / WECHAT_SECRET 时，enabled 接口返回 false，
前端不显示微信登录入口。
"""
import json
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from urllib.parse import parse_qs, urlparse

from . import db
from .base import route
from .config import WECHAT_APPID, WECHAT_SECRET, WECHAT_REDIRECT_URI

QR_URL = "https://open.weixin.qq.com/connect/qrconnect"
TOKEN_URL = "https://api.weixin.qq.com/sns/oauth2/access_token"
USERINFO_URL = "https://api.weixin.qq.com/sns/userinfo"
STATE_TTL = 600          # state 有效时长（秒），微信扫码二维码本身也约 5 分钟过期
HTTP_TIMEOUT = 8

# state -> {"created": 时间戳}；单进程内存存储即可，登录期间服务重启则本次作废
_pending = {}


def wechat_enabled():
    return bool(WECHAT_APPID and WECHAT_SECRET)


def _gc_pending():
    now = time.time()
    stale = [s for s, v in _pending.items() if now - v["created"] > STATE_TTL]
    for s in stale:
        _pending.pop(s, None)


def _http_get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "shufang/1.0"})
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8"))


def _redirect_uri(headers):
    """微信回调地址：优先环境变量，否则按请求 Host 推导（支持反代 X-Forwarded-Proto）。"""
    if WECHAT_REDIRECT_URI:
        return WECHAT_REDIRECT_URI
    host = headers.get("Host", "127.0.0.1:8000")
    proto = headers.get("X-Forwarded-Proto", "http").split(",")[0].strip()
    return f"{proto}://{host}/api/wechat/callback"


def _default_name(openid):
    return "微信用户" + openid[-4:]


class WechatMixin:
    @route("GET", "/api/wechat/enabled")
    def api_wechat_enabled(self):
        return self._send_json({"enabled": wechat_enabled()})

    @route("GET", "/api/wechat/login")
    def api_wechat_login(self):
        if not wechat_enabled():
            return self._send_json({"error": "微信登录未配置（缺少 WECHAT_APPID / WECHAT_SECRET）"}, 503)
        state = secrets.token_urlsafe(16)
        _gc_pending()
        _pending[state] = {"created": time.time()}
        params = {
            "appid": WECHAT_APPID,
            "redirect_uri": _redirect_uri(self.headers),
            "response_type": "code",
            "scope": "snsapi_login",
            "state": state,
        }
        url = QR_URL + "?" + urllib.parse.urlencode(params) + "#wechat_redirect"
        return self._send_json({"url": url, "state": state})

    @route("GET", "/api/wechat/callback")
    def api_wechat_callback(self):
        def fail(msg):
            return self._redirect("/wechat.html?" + urllib.parse.urlencode(
                {"error": msg, "state": q.get("state", [""])[0]}))

        q = parse_qs(urlparse(self.path).query)
        state = q.get("state", [""])[0]
        code = q.get("code", [""])[0]
        _gc_pending()
        if not state or not code:
            return fail("缺少授权参数")
        if state not in _pending:
            return fail("登录已过期，请重试")
        _pending.pop(state, None)

        # 用 code 换取 openid（微信公众号/开放平台的 access_token 接口）
        try:
            data = _http_get_json(TOKEN_URL + "?" + urllib.parse.urlencode({
                "appid": WECHAT_APPID,
                "secret": WECHAT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
            }))
        except Exception as e:
            print(f"微信换取 access_token 失败: {e}", flush=True)
            return fail("微信服务暂时不可用，请稍后重试")
        if not data.get("openid"):
            return fail("授权失败（" + str(data.get("errcode", "未知错误")) + "）")

        openid = data["openid"]
        nickname = None
        try:
            info = _http_get_json(USERINFO_URL + "?" + urllib.parse.urlencode({
                "access_token": data.get("access_token", ""),
                "openid": openid,
            }))
            if info.get("nickname"):
                nickname = info["nickname"]
        except Exception as e:
            print(f"获取微信用户信息失败（继续登录）: {e}", flush=True)

        # 以 wx_<openid> 作为本地账号：首次登录自动注册，之后直接登录
        uid = "wx_" + openid
        now = time.time()
        try:
            db.col_users.insert_one({
                "_id": uid, "salt": "", "pwhash": "",
                "wechat": {
                    "openid": openid,
                    "unionid": data.get("unionid", ""),
                    "nickname": nickname or _default_name(openid),
                    "created": now,
                },
            })
        except Exception:
            db.col_users.update_one(
                {"_id": uid},
                {"$set": {"wechat.nickname": nickname or _default_name(openid),
                          "wechat.openid": openid,
                          "wechat.unionid": data.get("unionid", "")}})

        token = self._new_session(uid)
        return self._redirect("/wechat.html?" + urllib.parse.urlencode({
            "token": token,
            "name": nickname or _default_name(openid),
            "state": state,
        }))
