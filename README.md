# shu-server
这位老哥 https://github.com/dooshu/shu 的图书的server端
## 如何使用
### 前置
需要安装docker， docker-compose（没有需要手动安装Python3, MongoDB）
### 启动server
1. 将本程序clone到上面的老哥的shu的同级目录下
2. 执行 docker-compose up -d（第一次较慢， 需要下载一些镜像）
3. 打开 http://your-ip:8000/
4. 愉快的阅读吧， 享受阅读的乐趣。
## 功能列表
1. 按照书库展示图书列表
2. 注册、登录（用户名/密码，微信扫码登录可选）
3. 记录阅读进度， 阅读时长
4. 删除阅读记录
5. 图书标签，记录精彩片段
6. 统计读书时长
7. PWA 支持：可「安装到主屏幕」，离线也能打开阅读器并重读最近看过的书

> PWA 的安装与离线功能需要安全上下文：通过 `localhost` 访问即可；
> 若通过局域网 IP（http://your-ip:8000/）访问，浏览器不会注册 Service Worker，
> 需自行套一层 HTTPS（如反向代理）才能启用离线与安装。

## 微信扫码登录（可选）
在 [微信开放平台](https://open.weixin.qq.com) 注册并通过认证后：
1. 「管理中心 → 网站应用 → 创建网站应用」，获取 `AppID` 与 `AppSecret`；
2. 在应用设置中把「授权回调域」填为访问本服务的域名
   （如 `your-ip` 或 `your-domain.com`，不含协议与路径）；
3. 给服务设置环境变量后重启：

| 环境变量 | 说明 |
| --- | --- |
| `WECHAT_APPID` | 网站应用的 AppID |
| `WECHAT_SECRET` | 网站应用的 AppSecret |
| `WECHAT_REDIRECT_URI` | 可选。回调地址，默认自动推导为 `http(s)://<访问域名>/api/wechat/callback`；经反向代理且回调域与访问域名不一致时需显式设置 |

未配置上述变量时，登录弹窗不显示微信入口，原有账号密码登录不受影响。

> 注意：微信扫码后会把浏览器重定向回本服务，因此该服务必须能被手机访问到
> （公网 IP 或内网穿透），否则扫码无法完成授权。
## 声明
本程序由AI生成


