"""核心阅读数据 API：图书馆列表、聚合状态、进度、最近在读、删除。"""
from . import db
from .base import route, needs_db
from .libraries import list_libraries
from .tags import tags_for
from .readtime import readtime_for


class ReadingMixin:
    @route("GET", "/api/libraries")
    def api_libraries(self):
        return self._send_json(list_libraries())

    @route("GET", "/api/state")
    @needs_db
    def api_state(self):
        """返回该用户的全部进度、最近在读、标签与阅读时长。"""
        user = self._user()
        prog = {}
        for d in db.col_prog.find({"user": user}):
            key = f"{d.get('lib', 'cn')}/{d['bookid']}"
            prog[key] = {"top": d.get("top", 0), "pct": d.get("pct", 0),
                         "secs": int(d.get("secs", 0) or 0)}
        rec = db.col_recent.find_one({"_id": user})
        recent = rec.get("items", []) if rec else []
        return self._send_json({
            "prog": prog,
            "recent": recent,
            "tags": tags_for(user),
            "readtime": readtime_for(user),
        })

    @route("POST", "/api/progress")
    @needs_db
    def api_save_progress(self):
        data = self._read_body()
        lib, bid = self._libbook(data)
        if not lib:
            return self._send_json({"error": "bad-lib-or-bookid"}, 400)
        user = self._user()
        db.col_prog.update_one(
            {"user": user, "lib": lib, "bookid": bid},
            {"$set": {
                "top": float(data.get("top", 0)),
                "pct": int(data.get("pct", 0)),
            }},
            upsert=True,
        )
        return self._send_json({"ok": True})

    @route("POST", "/api/recent")
    @needs_db
    def api_save_recent(self):
        lib, bid = self._libbook(self._read_body())
        if not lib:
            return self._send_json({"error": "bad-lib-or-bookid"}, 400)
        user = self._user()
        rec = db.col_recent.find_one({"_id": user})
        items = rec.get("items", []) if rec else []
        items = [x for x in items if not (x.get("lib") == lib and str(x.get("bookid")) == bid)]
        items.insert(0, {"lib": lib, "bookid": bid})
        items = items[:20]
        db.col_recent.update_one({"_id": user}, {"$set": {"items": items}}, upsert=True)
        return self._send_json({"ok": True, "recent": items})

    @route("POST", "/api/delete")
    @needs_db
    def api_delete(self):
        """删除一本书的阅读记录：进度 + 最近在读。"""
        lib, bid = self._libbook(self._read_body())
        if not lib:
            return self._send_json({"error": "bad-lib-or-bookid"}, 400)
        user = self._user()
        db.col_prog.delete_one({"user": user, "lib": lib, "bookid": bid})
        rec = db.col_recent.find_one({"_id": user})
        items = rec.get("items", []) if rec else []
        items = [x for x in items if not (x.get("lib") == lib and str(x.get("bookid")) == bid)]
        if rec:
            db.col_recent.update_one({"_id": user}, {"$set": {"items": items}})
        return self._send_json({"ok": True, "recent": items})
