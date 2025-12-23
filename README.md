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
│           └── http.conf                   # HTTP 重定向配置示例
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
