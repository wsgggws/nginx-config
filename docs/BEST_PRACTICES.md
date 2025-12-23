# 最佳实践指南

## 📐 Snippets 库的作用

这个项目提供的是模块化的 Nginx 配置片段库，用于在你的 Nginx 项目中快速应用最佳实践。

### 项目范围

**提供的配置片段：**

- ✅ SSL/TLS 安全参数
- ✅ 安全响应头配置
- ✅ Gzip 压缩设置
- ✅ 静态资源缓存策略
- ✅ 反向代理通用参数
- ✅ Let's Encrypt ACME 验证配置

**你的 Nginx 项目需要提供：**

- ✅ 主配置文件 (nginx.conf)
- ✅ 服务器块配置
- ✅ 日志格式和路径
- ✅ 性能调优参数（worker_processes 等）
- ✅ 速率限制区域定义（可选）

## 🔒 安全最佳实践

### SSL/TLS 配置

**推荐：在你的服务器块中使用 snippet**

```nginx
server {
    listen 443 ssl http2;
    server_name example.com;

    # 证书配置（必须在包含 ssl-params 之前）
    ssl_certificate /etc/letsencrypt/live/example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/example.com/privkey.pem;

    # 引用我们的 SSL 安全配置
    include /etc/nginx/snippets/ssl-params.conf;

    # ... 其他配置
}
```

**配置包含：**

- TLS 1.2 和 1.3
- 现代化的加密套件
- Session 缓存优化
- OCSP Stapling

### 安全响应头

```nginx
server {
    # ...

    # 引用安全头配置
    include /etc/nginx/snippets/security-headers.conf;

    # 可以针对特定站点覆盖
    add_header Content-Security-Policy "default-src 'self';" always;
}
```

**配置包含：**

- HSTS（强制 HTTPS）
- X-Frame-Options（防点击劫持）
- X-Content-Type-Options（防 MIME 嗅探）
- X-XSS-Protection（XSS 保护）
- CSP 示例

## ⚡ 性能优化

### 静态资源缓存

```nginx
server {
    root /var/www/html;

    # 包含缓存策略
    include /etc/nginx/snippets/static-cache.conf;

    # 或手动配置
    location ~* \.(jpg|jpeg|png|gif|ico|svg)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

### Gzip 压缩

在 nginx.conf 的 http 块中使用：

```nginx
http {
    include /etc/nginx/snippets/gzip.conf;

    server {
        # 服务器配置...
    }
}
```

### 反向代理优化

```nginx
location /api {
    # 引用反向代理参数
    include /etc/nginx/snippets/proxy-params.conf;

    # 后端服务地址
    proxy_pass http://backend:8080;
}
```

**配置包含：**

- 真实 IP 转发
- WebSocket 支持
- 超时和缓冲优化
- 连接池配置

## 📝 完整配置示例

### 静态网站

```nginx
# HTTP -> HTTPS 重定向
server {
    listen 80;
    listen [::]:80;
    server_name example.com www.example.com;

    include /etc/nginx/snippets/letsencrypt.conf;

    location / {
        return 301 https://$host$request_uri;
    }
}

# HTTPS 站点
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name example.com www.example.com;

    # SSL 证书
    ssl_certificate /etc/letsencrypt/live/example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/example.com/privkey.pem;

    # 安全配置
    include /etc/nginx/snippets/ssl-params.conf;
    include /etc/nginx/snippets/security-headers.conf;

    # 网站配置
    root /var/www/html/example.com;
    index index.html;

    # 静态资源缓存
    include /etc/nginx/snippets/static-cache.conf;

    location / {
        try_files $uri $uri/ =404;
    }

    # 错误页面
    error_page 404 /404.html;
}
```

### 反向代理

```nginx
server {
    listen 443 ssl http2;
    server_name api.example.com;

    ssl_certificate /etc/letsencrypt/live/api.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.example.com/privkey.pem;

    include /etc/nginx/snippets/ssl-params.conf;
    include /etc/nginx/snippets/security-headers.conf;

    location / {
        include /etc/nginx/snippets/proxy-params.conf;
        proxy_pass http://backend:3000;
    }
}
```

## 🔄 部署流程

### 使用模板创建新站点

```bash
# 1. 复制模板
cp templates/static-site.conf.template /etc/nginx/conf.d/mysite.conf

# 2. 编辑配置，替换占位符
sed -i 's/DOMAIN_NAME/mysite.com/g' /etc/nginx/conf.d/mysite.conf

# 3. 重新加载
nginx -t && systemctl reload nginx
```

### 配置变更步骤

1. **准备配置文件**
2. **语法验证**：`nginx -t`
3. **重新加载**：`nginx -s reload`
4. **验证结果**：`curl -I https://example.com`
5. **检查日志**：`tail -f /var/log/nginx/access.log`

## 📊 监控和日志

### 查看日志

```bash
# 实时访问日志
tail -f /var/log/nginx/access.log

# 错误日志
tail -f /var/log/nginx/error.log

# 过滤错误
grep " 5[0-9][0-9] " /var/log/nginx/access.log
```

### 关键监控指标

- HTTP 状态码分布（特别是 4xx 和 5xx）
- 响应时间
- SSL 握手失败
- 证书过期时间

## 🔧 常见问题排查

### 配置错误

```bash
# 查看具体错误
nginx -t
```

### 证书问题

```bash
# 检查证书文件
ls -la /etc/letsencrypt/live/example.com/

# 检查有效期
openssl x509 -in /etc/letsencrypt/live/example.com/fullchain.pem -noout -dates
```

### 权限问题

```bash
# 检查 Nginx 运行用户
ps aux | grep nginx

# 检查文件权限
ls -la /var/www/html/
ls -la /etc/nginx/
```

### 端口冲突

```bash
# 检查端口占用
sudo lsof -i :80
sudo lsof -i :443
```

## 📚 相关资源

- [Nginx 官方文档](https://nginx.org/en/docs/)
- [Mozilla SSL Configuration Generator](https://ssl-config.mozilla.org/)
- [Let's Encrypt 文档](https://letsencrypt.org/docs/)
- [OWASP Nginx Hardening](https://owasp.org/www-project-secure-headers/)
