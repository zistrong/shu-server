"""每日阅读时长 API。"""
from . import db
from .base import route, needs_db

MAX_SECS = 86400                                    # 单次上报封顶一天


def _to_secs(v):
    """规整为 [0, 86400] 的整数秒；非法返回 0。"""
    try:
        return min(max(int(v), 0), MAX_SECS)
    except (TypeError, ValueError):
        return 0


def readtime_for(user):
    """某用户每日阅读秒数 {日期: 秒}，供 /api/state 汇总。"""
    return {d["date"]: int(d.get("secs", 0)) for d in db.col_readtime.find({"user": user})}


class ReadTimeMixin:
    @route("POST", "/api/readtime")
    @needs_db
    def api_readtime(self):
        """累加阅读秒数：

        - buckets：{日期: 秒} 计入每日总时长（readtime 集合）。
        - books： [{lib, bookid, secs}] 计入每本书总时长（progress 集合的 secs 字段）。
        兼容旧形状 {date, secs}。
        """
        data = self._read_body()
        buckets = data.get("buckets")
        if not isinstance(buckets, dict):
            buckets = {str(data.get("date", "")): data.get("secs", 0)}
        user = self._user()
        for date, secs in buckets.items():
            date = str(date)[:10]
            secs = _to_secs(secs)
            if not date or secs <= 0:
                continue
            db.col_readtime.update_one(
                {"user": user, "date": date},
                {"$inc": {"secs": secs}},
                upsert=True,
            )
        for book in data.get("books") or []:
            if not isinstance(book, dict):
                continue
            lib, bid = self._libbook(book)
            secs = _to_secs(book.get("secs", 0))
            if not lib or secs <= 0:
                continue
            db.col_prog.update_one(
                {"user": user, "lib": lib, "bookid": bid},
                {"$inc": {"secs": secs}},
                upsert=True,
            )
        return self._send_json({"ok": True})
