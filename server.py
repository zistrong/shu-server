#!/usr/bin/env python3
"""书房阅读器 —— 本地服务器入口。

静态文件（index.html / books.json / *.txt）照常提供；另外提供 /api/* 接口，
把阅读进度、最近在读、标签与每日阅读时长保存到 MongoDB。

代码按功能拆分在 shufang/ 包中：
    config     路径与环境变量
    db         MongoDB 连接、集合、索引与迁移
    security   密码哈希（PBKDF2）
    libraries  图书馆目录扫描
    base       HTTP 基础设施与路由注册（@route / @needs_db / BaseHandler）
    accounts / reading / tags / readtime   各功能 API
    handler    组装最终 Handler

环境变量：
    MONGO_URL   MongoDB 连接串（默认 mongodb://localhost:27017）
    PORT        监听端口（默认 8000）

用法：
    python3 server.py [端口]      # 本地运行（需 pip install pymongo）
    docker compose up            # 推荐：一并启动 MongoDB

若 MongoDB 不可用，API 返回 503，前端会自动降级到浏览器 localStorage，
阅读器依然可用。
"""
import os
import sys
import webbrowser
from functools import partial
from http.server import HTTPServer

from shufang.config import ROOT
from shufang.handler import Handler


def main():
    port = int(os.environ.get("PORT", 8000))
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print("端口需为数字，例如: python3 server.py 8888")
            return

    handler = partial(Handler, directory=ROOT)
    httpd = HTTPServer(("0.0.0.0", port), handler)
    url = f"http://127.0.0.1:{port}/"
    print(f"书房阅读器已启动 → {url}")
    print("按 Ctrl+C 停止")
    # 仅本地运行时尝试开浏览器（容器内无桌面环境）
    if not os.environ.get("IN_DOCKER"):
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")


if __name__ == "__main__":
    main()
