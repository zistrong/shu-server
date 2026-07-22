"""每日阅读时长 API。"""
from . import db
from .base import route, needs_db


def readtime_for(user):
    """某用户每日阅读秒数 {日期: 秒}，供 /api/state 汇总。"""
    return {d["date"]: int(d.get("secs", 0)) for d in db.col_readtime.find({"user": user})}


class ReadTimeMixin:
    @route("POST", "/api/readtime")
    @needs_db
    def api_readtime(self):
        """按日期累加阅读秒数。支持 {date, secs} 或 {buckets:{date:secs}}。"""
        data = self._read_body()
        buckets = data.get("buckets")
        if not isinstance(buckets, dict):
            buckets = {str(data.get("date", "")): data.get("secs", 0)}
        user = self._user()
        for date, secs in buckets.items():
            date = str(date)[:10]
            try:
                secs = int(secs)
            except (TypeError, ValueError):
                continue
            if not date or secs <= 0:
                continue
            secs = min(secs, 86400)                 # 单次上报封顶一天
            db.col_readtime.update_one(
                {"user": user, "date": date},
                {"$inc": {"secs": secs}},
                upsert=True,
            )
        return self._send_json({"ok": True})
