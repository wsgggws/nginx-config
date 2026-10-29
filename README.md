# Nginx 配置模板与最佳实践

一个生产级的 Nginx 配置模板库，采用关注点分离的架构设计。
适用于构建中央化的 Nginx 管理系统。

## 📋 项目结构

```
nginx/
├── README.md                      # 本文档
├── .gitignore
├── config/
│   └── nginx/
│       ├── snippets/              # 公共配置片段库
│       │   ├── ssl-params.conf              # SSL/TLS 安全参数
│       │   ├── security-headers.conf        # 安全响应头
│       │   ├── gzip.conf                    # Gzip 压缩配置
│       │   ├── static-cache.conf            # 静态资源缓存
│       │   ├── proxy-params.conf            # 反向代理参数
│       │   └── letsencrypt.conf             # ACME 验证
│       └── conf.d/
│           ├── http.conf                   # HTTP 重定向配置示例
│           └── navydev-top.conf            # navydev.top 的四个站点
│       └── help/
│           └── index.html                  # /help 索引页（nginx 直接发）
├── templates/                     # 配置文件模板
│   ├── static-site.conf.template             # 静态网站配置模板
│   └── reverse-proxy.conf.template           # 反向代理配置模板
└── docs/
    ├── BEST_PRACTICES.md          # 最佳实践指南
    └── FAQ.md                     # 常见问题解答
```

## ✨ 核心设计理念

### 1️⃣ 关注点分离

- **中央项目**：管理基础设施（SSL、安全头、Gzip、Certbot）
- **子项目**：只包含业务相关的路由配置

### 2️⃣ DRY 原则

- 公共配置放在 `snippets/` 目录
- 站点配置通过 `include` 引用
- 避免重复配置

### 3️⃣ 可扩展性

- 新增站点只需最小化配置
- 公共配置更新自动应用到所有站点

## 📦 navydev.top 上的路径

所有站点都在 `navydev.top` 这一个域名下，用路径区分：

| 路径 | 是什么 | 后端 |
| --- | --- | --- |
| `/`、`/help` | 索引页 | nginx 直接发静态文件 |
| `/ebook` | navy's ebook | `127.0.0.1:8010` |
| `/blog` | Hugo 博客（同时发布到 GitHub Pages） | 静态站 `/var/www/navydev.top/blog/` |
| `/me` | 原 `navydev.top` | 静态站 `/var/www/navydev.top/me/` |
| `/rss` | 原 `rss.navydev.top` | 静态站 `/var/www/navydev.top/rss/` + API `127.0.0.1:8000` |
| `/crabtris` | 原 `crabtris.navydev.top` | 静态站 `/var/www/crabtris.navydev.top/` |

配置在 `config/nginx/conf.d/navydev-top.conf`；索引页在 `config/nginx/help/index.html`，
部署时复制到 `/var/www/navydev/help/`。首页采用 [LuZhu.nvim](https://github.com/wsgggws/LuZhu.nvim) 最新潭绿配色作为默认主题（底色 `#1D3229`、正文 `#DCE8D5`、强调色 `#89C79B`），提供 GitHub 与 BiliBili 图标链接。

各路径都不要求尾斜杠；`/me/`、`/rss/`、`/crabtris/` 等旧形式仍然可用。
老的子域名会 301 到新路径（`rss.navydev.top` → `navydev.top/rss`），老书签不会失效。
`/nghh` 也会 301 到 `/me/nghh/`。

有声电子书那段有几处特别处理：

- HTTP/2 走 `listen 443 ssl http2;`（**nginx 1.18 用这个写法**；
  1.25.1 以上可以改成 `http2 on;`，但那样 1.18 会起不来）。
- 后端要设 `LECTOR_BASE_PATH=/ebook`，路径原样传过去；
  `proxy_pass` 后面**不能带斜杠**，带了就等于把 `/ebook` 前缀吃掉。
- 静态资源在 nginx 这层缓存（它的 css/js 没有版本号，所以不用 immutable 长期缓存，
  免得前端更新了浏览器还拿旧的）。
- 音频与上传各自单开一个 location，合成慢、上传大都不会被掐断。

站点默认拒绝明显的 `curl`、`wget`、`python-requests` 等命令行 User-Agent。
健康检查、带 `X-Lector-Client: terminal` 的官方终端和带 Bearer token 的
管理请求例外；应用层还会继续校验同源来源和 token。

`/me` 与 `/rss` 的前端必须按子路径构建：Vite 的 `base` 分别是 `/me/` 与
`/rss/`。否则二者的 `/assets` 会冲突，只能有一个站点正常工作。

## 🚀 使用方式

### 1. 作为配置模板库使用

**复制 snippets 到你的 Nginx 项目：**

```bash
cp -r config/nginx/snippets /etc/nginx/
```

### 2. 在你的配置中引用片段

在你的 nginx.conf 或站点配置中：

```nginx
server {
    listen 443 ssl http2;
    server_name example.com;

    ssl_certificate /etc/letsencrypt/live/example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/example.com/privkey.pem;

    # 引用公共配置片段
    include /etc/nginx/snippets/ssl-params.conf;
    include /etc/nginx/snippets/security-headers.conf;
    include /etc/nginx/snippets/static-cache.conf;

    # 你的站点配置
    root /var/www/html;
    # ...
}
```

### 3. 使用配置模板

基于模板创建新站点配置：

```bash
# 复制静态网站模板
cp templates/static-site.conf.template /etc/nginx/conf.d/mysite.conf
sed -i 's/DOMAIN_NAME/mysite.com/g' /etc/nginx/conf.d/mysite.conf

# 验证配置
nginx -t

# 重新加载
nginx -s reload
```

## 📦 子项目配置规范

### 目录结构

每个子项目应包含：

```
your-project/
└── config/nginx/conf.d/
    └── yourdomain.com.conf
```

### 配置模板

#### 静态网站

```nginx
# yourdomain.com - 静态站点
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;

    # SSL 证书
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    # 引用公共配置
    include /etc/nginx/snippets/ssl-params.conf;
    include /etc/nginx/snippets/security-headers.conf;
    include /etc/nginx/snippets/static-cache.conf;

    # 网站根目录
    root /usr/share/nginx/html/yourdomain.com;
    index index.html;

    location / {
        try_files $uri $uri/ =404;
    }
}
```

#### 反向代理

```nginx
# api.yourdomain.com - API 反向代理
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name api.yourdomain.com;

    # SSL 证书
    ssl_certificate /etc/letsencrypt/live/api.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.yourdomain.com/privkey.pem;

    # 引用公共配置
    include /etc/nginx/snippets/ssl-params.conf;
    include /etc/nginx/snippets/security-headers.conf;
    include /etc/nginx/snippets/proxy-params.conf;

    # 速率限制
    limit_req zone=api burst=20 nodelay;
    limit_conn addr 10;

    location / {
        proxy_pass http://backend:8080;
    }
}
```

## 🔐 SSL 证书管理

### 申请新证书

```bash
# 强烈建议使用 webroot 方式申请证书
certbot certonly \
  --webroot \
  -w /var/www/certbot \
  -d yourdomain.com \
```

1. 在 `config/nginx/conf.d/http.conf` 中添加域名：

```nginx
server_name navydev.top ... yourdomain.com;
```

### 自动续期

```sh
# 验证
systemctl list-timers | grep certbot

certbot renew --post-hook "systemctl reload nginx"
```

### 重启 nginx

```sh
nginx -t && systemctl reload nginx
```

## 🔗 外部资源

- [Nginx 官方文档](https://nginx.org/en/docs/)
- [Let's Encrypt 文档](https://letsencrypt.org/docs/)
- [Mozilla SSL Configuration Generator](https://ssl-config.mozilla.org/)
- [Nginx Security Best Practices](https://docs.nginx.com/)
