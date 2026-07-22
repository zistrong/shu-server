"""装配最终的请求处理器：合并各功能 Mixin 与 HTTP 基础设施。

导入各功能模块会触发它们通过 @route 注册路由（见 base.py 的路由表）。
"""
from .base import BaseHandler
from .accounts import AccountMixin
from .reading import ReadingMixin
from .tags import TagsMixin
from .readtime import ReadTimeMixin


class Handler(AccountMixin, ReadingMixin, TagsMixin, ReadTimeMixin, BaseHandler):
    pass
