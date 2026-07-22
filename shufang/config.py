"""路径与环境变量配置。"""
import os

# server/ 目录（含 index.html 与 books/），即本包的上级目录
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOOKS_DIR = os.path.join(ROOT, "books")
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
