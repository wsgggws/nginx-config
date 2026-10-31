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
│           └── navydev-top.conf            # navydev.top 的站点入口
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
| `/me` | 原 `navydev.top` | 静态站 `/var/www/navydev.top/me/` |
| `/ebook` | navy's ebook | `127.0.0.1:8010` |
| `/blog` | Hugo 博客（同时发布到 GitHub Pages） | 静态站 `/var/www/navydev.top/blog/` |
| `/rss` | 原 `rss.navydev.top` | 静态站 `/var/www/navydev.top/rss/` + API `127.0.0.1:8000` |
| `/crabtris` | 原 `crabtris.navydev.top` | 静态站 `/var/www/crabtris.navydev.top/` |
| `/metric` | 访问统计 + CPU/内存/磁盘/网络（公开） | GoAccess 静态报告 + Netdata `127.0.0.1:19999` |

配置在 `config/nginx/conf.d/navydev-top.conf`；索引页在 `config/nginx/help/index.html`，
部署时复制到 `/var/www/navydev/help/`。首页采用 [LuZhu.nvim](https://github.com/wsgggws/LuZhu.nvim) 最新潭绿配色作为默认主题（底色 `#1D3229`、正文 `#DCE8D5`、强调色 `#89C79B`），提供 GitHub 与 BiliBili 图标链接。
目录顺序固定为 `/me`、`/ebook`、`/blog`、`/rss`、`/crabtris`、`/metric`；`/` 与 `/help` 使用同一份索引。

各路径都不要求尾斜杠；`/me/`、`/rss/`、`/crabtris/` 等旧形式仍然可用。
老的子域名会 301 到新路径（`rss.navydev.top` → `navydev.top/rss`），老书签不会失效。
`/nghh` 也会 301 到 `/me/nghh/`。

`/metric` 对应独立项目 `../navydev.top_metric`，公开显示精简总览（系统数值和趋势在上，访问图表和路径计数在下）。
该项目的 CI 首次自动安装监控依赖，后续跳过安装并更新页面和程序；首次部署
完成后再发布本仓库配置。手动部署入口为 `sudo bash scripts/deploy.sh`。
`00-metric-log.conf` 保留重写前路径并去掉查询参数；`metric-locations.conf` 提供公开页面、配置/摘要 JSON、
报告及 Netdata API 反代；19999 端口仍仅监听本机。专用日志 `/var/log/nginx/navydev-metric.access.log` 包含静态
资源和接口；日志轮转沿用系统 `/etc/logrotate.d/nginx`。新增 location 若设置了
自己的 `access_log`，也必须显式写入这份专用日志，才能保持统计完整。

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

## 请求限流

采用 Nginx 内置 `limit_req` + `limit_conn`，不新增服务。分类与额度定义在
`config/nginx/conf.d/01-rate-limits.conf`，执行规则在
`config/nginx/snippets/navydev-rate-limits.conf`，由主站及仍代理后端的旧子域名统一引用。

| 范围 | 每 IP 持续速率 / 突发额度 | 所有 IP 合计持续速率 / 突发额度 | 同时处理请求 |
| --- | --- | --- | --- |
| 全部内容：`/`、`/help`、`/me`、`/ebook` 页面/JS、`/blog`、`/rss` 前端、`/crabtris`、`/metric` 静态页面与 JSON，以及下列接口 | 30 次/秒 / 100 | 200 次/秒 / 200 | — |
| 电子书 `/ebook/api/`（含上传、音频）、RSS `/rss/backend/` 与文档/OpenAPI、仍代理 RSS 的旧子域名 | 5 次/秒 / 15 | 后端组共享 30 次/秒 / 30 | 每 IP 8，后端组共享 32 |
| Netdata `/metric/system/api/` | 15 次/秒 / 60 | Netdata API 组共享 60 次/秒 / 120 | — |

这些是小站初始保护值，尚非容量压测结果。各层叠加生效；同一 IP 切换路径不会重置共享额度。
每个 CSS/JS/图片、每次 API 调用分别计一次请求，所以静态内容和完整监控面板保留较大突发余量。
电子书 `/ebook/api/v1/books/<id>/cover` 只读取已有封面文件，按普通资源额度计数，避免书架批量加载图片时误限流。
电子书播放器预取后续 3 句的音频和词边界，后端并发额度兼顾这组请求。

算法限制持续平均速率，允许短时突发；`nodelay` 不排队等待，超额直接返回 **429**，
额度随时间恢复。并发限制覆盖整个慢请求处理/传输期间，避免上传和音频合成长期占满后端。
HTTP/2 的每个在途请求各占一份并发额度。纯 301/302 跳转和原有 UA 的 403 在更早阶段返回，
内容目标受限；ACME 验证保留原有 HTTP 通道。Bearer token 和官方终端不豁免限流。

超限页面显示中文提示，提供“重试当前页面”和“返回首页”；API 返回兼容电子书/RSS 的中文 JSON 错误，
统一附带 `Retry-After: 5` 和 `Cache-Control: no-store`。提示页不自动刷新或重新提交上传；
`/metric` 会明确提示访问频繁，按原刷新间隔重试。完整 Netdata 仪表板沿用上游自己的错误界面，API 返回相同的 429 JSON。

使用真实连接来源 IP；不信任客户端自行提交的 `X-Forwarded-For`。以后引入 CDN 时，
需只信任供应商已核实的代理网段并限制源站入口。共享总额度能保护后端，但被攻击者占满时正常请求
也可能收到 429；本机限流无法抵御打满带宽的分布式攻击，持续攻击应增加上游 CDN/WAF/DDoS 防护。
选型、继承与 URI 规范化依据见 [限流研究](docs/RATE_LIMIT_RESEARCH.md)。

调参时同时检查 rate、burst、并发数和真实访问错误率。主访问日志中的 `lr="REJECTED"` /
`lc="REJECTED"` 表示 Nginx 主动限流，error log 会记录命中的 zone；应用自己的 429 不会冒充该状态。
修改各路径 location 时继承 server 整组规则；子 location 自定义一条 `limit_req` 或 `limit_conn`
会覆盖父层同类规则，应同步检查全部保护层。

## 验证与发布

```bash
# 本地需真实 nginx、openssl、Python 标准库和 ShellCheck
python3 -m unittest discover -s tests -v
shellcheck scripts/*.sh
for script in scripts/*.sh; do bash -n "$script"; done
```

测试只启动本机临时 Nginx 和模拟后端，验证完整配置、入口顺序、静态/动态额度、
多来源总额度、并发上限、友好提示、超限后恢复和绕过边界；模拟 IP 的专用头只在临时配置中受信任。
CI 在 push/PR 时执行，tag 部署也先执行相同检查，通过后再上传、线上 `nginx -t` 和 reload。
发布前核对远程 tag，创建新的 `v*.*.*` tag。验收记录见 [验证记录](docs/VERIFICATION.md)。

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
