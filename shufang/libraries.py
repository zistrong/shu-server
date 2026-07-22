"""图书馆（多目录）扫描。"""
import os
import json

from .config import BOOKS_DIR

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
