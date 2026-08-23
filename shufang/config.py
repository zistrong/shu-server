"""路径与环境变量配置。"""
import os

# server/ 目录（含 index.html 与 books/），即本包的上级目录
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOOKS_DIR = os.path.join(ROOT, "books")
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")

# 微信开放平台扫码登录（网站应用）
# 在 https://open.weixin.qq.com 注册「网站应用」后填入 appid / secret，
# 并在应用配置中把授权回调域设为你的域名。两项都为空时微信登录自动禁用。
WECHAT_APPID = os.environ.get("WECHAT_APPID", "")
WECHAT_SECRET = os.environ.get("WECHAT_SECRET", "")
# 授权回调地址，默认按请求 Host 自动推导为 http(s)://<host>/api/wechat/callback；
# 若经反向代理且回调域与访问域名不同，可在此显式覆盖。
WECHAT_REDIRECT_URI = os.environ.get("WECHAT_REDIRECT_URI", "")
