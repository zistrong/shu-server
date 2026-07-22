"""MongoDB 连接、集合句柄、索引与旧数据迁移。

pymongo 为可选依赖：若缺失或连接失败，所有集合保持为 None，
mongo_ok() 返回 False，上层 API 统一返回 503，前端自动降级到 localStorage。

其它模块请用 `from . import db` 后通过 `db.col_xxx` / `db.mongo_ok()` 访问，
不要 `from .db import col_xxx`（会在连接前把 None 固化下来）。
"""
from .config import MONGO_URL

col_prog = None
col_recent = None
col_users = None
col_sessions = None
col_tags = None
col_readtime = None


def mongo_ok():
    return col_prog is not None


def _connect():
    global col_prog, col_recent, col_users, col_sessions, col_tags, col_readtime
    from pymongo import MongoClient

    client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=2000)
    client.admin.command("ping")  # 立即验证连接
    database = client["shufang"]
    col_prog = database["progress"]
    col_recent = database["recent"]
    col_users = database["users"]
    col_sessions = database["sessions"]
    col_tags = database["tags"]
    col_readtime = database["readtime"]
    _ensure_schema()


def _ensure_schema():
    # 标签按 (用户, 图书馆, 书号) 检索
    col_tags.create_index([("user", 1), ("lib", 1), ("bookid", 1)])
    # 阅读时长按 (用户, 日期) 唯一，累加秒数
    col_readtime.create_index([("user", 1), ("date", 1)], unique=True)
    # 进度按 (用户, 图书馆, 书号) 唯一；同一书号可跨馆并存
    try:
        col_prog.drop_index("user_1_bookid_1")  # 迁移旧单馆索引
    except Exception:
        pass
    col_prog.create_index([("user", 1), ("lib", 1), ("bookid", 1)], unique=True)
    migrated = _migrate_legacy()
    print(f"已连接 MongoDB: {MONGO_URL}（迁移旧记录 {migrated} 条）", flush=True)


def _migrate_legacy():
    """无 lib 的进度默认归为 cn；recent 的 ids → items。"""
    migrated = 0
    for d in col_prog.find({"lib": {"$exists": False}}):
        try:
            col_prog.update_one(
                {"_id": d["_id"]},
                {"$set": {"lib": "cn", "bookid": str(d.get("bookid", ""))}})
            migrated += 1
        except Exception:
            pass
    for r in col_recent.find({"ids": {"$exists": True}}):
        items = [{"lib": "cn", "bookid": str(x)} for x in r.get("ids", [])]
        col_recent.update_one(
            {"_id": r["_id"]},
            {"$set": {"items": items}, "$unset": {"ids": ""}})
        migrated += 1
    return migrated


try:
    _connect()
except Exception as e:  # pymongo 缺失或连接失败
    print(f"未连接 MongoDB（将由前端使用 localStorage 降级）: {e}", flush=True)
