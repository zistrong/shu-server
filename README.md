# shu-server
这位老哥 https://github.com/dooshu/shu 的图书的server端
## 如何使用
### 前置
需要安装docker， docker-compose
### 启动server
1. 将本程序clone到上面的老哥的shu的同级目录下
2. 执行 docker-compose up -d（第一次较慢， 需要下载一些镜像）
3. 打开 http://your-ip:8000/
4. 愉快的阅读吧， 享受阅读的乐趣。
## 功能列表
1. 按照书库展示图书列表
2. 注册、登录
3. 记录阅读进度， 阅读时长
4. 删除阅读记录
5. 图书标签，记录精彩片段
6. 统计读书时长
7. PWA 支持：可「安装到主屏幕」，离线也能打开阅读器并重读最近看过的书

> PWA 的安装与离线功能需要安全上下文：通过 `localhost` 访问即可；
> 若通过局域网 IP（http://your-ip:8000/）访问，浏览器不会注册 Service Worker，
> 需自行套一层 HTTPS（如反向代理）才能启用离线与安装。
## 声明
本程序由AI生成


