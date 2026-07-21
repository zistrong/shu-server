FROM python:3.12-slim

WORKDIR /app
RUN pip install --no-cache-dir "pymongo>=4,<5"

ENV IN_DOCKER=1 \
    PORT=8000 \
    MONGO_URL=mongodb://mongo:27017

# 代码与图书通过 volume 挂载进来（见 docker-compose.yml），
# 避免把约 2GB 的 txt 打进镜像。
EXPOSE 8000
CMD ["python3", "server.py"]
