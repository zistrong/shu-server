"""标签 API：选中文字 + 笔记 + 定位。"""
import time
import secrets

from . import db
from .base import route, needs_db


def tag_view(d):
    """把 MongoDB 标签文档整理成前端使用的形状。"""
    return {
        "id": d["_id"],
        "lib": d.get("lib", ""),
        "bookid": str(d.get("bookid", "")),
        "text": d.get("text", ""),
        "note": d.get("note", ""),
        "chap": int(d.get("chap", 0) or 0),
        "ch": d.get("ch", ""),
        "top": float(d.get("top", 0) or 0),
        "created": float(d.get("created", 0) or 0),
    }


def tags_for(user):
    """某用户全部标签（按创建时间倒序），供 /api/state 汇总。"""
    return [tag_view(d) for d in db.col_tags.find({"user": user}).sort("created", -1)]


class TagsMixin:
    @route("POST", "/api/tag_add")
    @needs_db
    def api_tag_add(self):
        data = self._read_body()
        lib, bid = self._libbook(data)
        if not lib:
            return self._send_json({"error": "bad-lib-or-bookid"}, 400)
        text = str(data.get("text", "")).strip()[:500]
        note = str(data.get("note", "")).strip()[:2000]
        if not text and not note:
            return self._send_json({"error": "empty-tag"}, 400)
        doc = {
            "_id": secrets.token_hex(8),
            "user": self._user(),
            "lib": lib,
            "bookid": bid,
            "text": text,
            "note": note,
            "chap": int(data.get("chap", 0) or 0),
            "ch": str(data.get("ch", "")).strip()[:120],
            "top": float(data.get("top", 0) or 0),
            "created": time.time(),
        }
        db.col_tags.insert_one(doc)
        return self._send_json({"ok": True, "tag": tag_view(doc)})

    @route("POST", "/api/tag_del")
    @needs_db
    def api_tag_del(self):
        tid = str(self._read_body().get("id", "")).strip()
        if not tid:
            return self._send_json({"error": "bad-id"}, 400)
        db.col_tags.delete_one({"_id": tid, "user": self._user()})
        return self._send_json({"ok": True})
