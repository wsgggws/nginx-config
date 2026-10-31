# 中央 Nginx 维护约定

默认使用简体中文编写文档和提交信息。

## 配置边界

本仓库统一管理公网路由、TLS、公共响应头、日志与站点索引。业务项目发布自己的应用文件和服务；中央发布始终以本仓库的 `config/nginx/` 为准。

线上兼容 Nginx 1.18：HTTP/2 使用 `listen 443 ssl http2;`。新路由同时检查无尾斜杠入口、静态资源、API 转发和原有路径。

## `/metric` 协作

- 监控实现位于 `../navydev.top_metric`；公开聚合页面的系统面板在上、访问统计在下。
- 日志格式和 map 位于 `00-metric-log.conf`，文件名前缀保证在使用该格式的 server 配置前加载。
- 专用日志覆盖全站。location 自己设置 `access_log` 时，要显式包含专用日志；静态资源也需要计数。
- `metric-locations.conf` 负责精简页面、配置/摘要 JSON、完整报告与 Netdata 子路径反代。日志从原始请求取路径并去掉查询参数，保留重写前的入口。Netdata 本机服务由监控项目管理。
- 首次上线先等待监控项目部署成功，再发布中央配置。需要排查监控服务时读该项目的 `docs/operations.md`。

## 限流

- 限流分类与额度统一在 `01-rate-limits.conf` 和 `navydev-rate-limits.conf`；按规范化 `$uri` 分类，主域名与仍代理后端的旧域名共用额度。
- 新增/调整路由时核对分类、server 级规则继承与静态突发；子 location 写入任一 `limit_req` 或 `limit_conn` 会覆盖父层同类规则。选型、真实 IP 与分布式防护边界见 [docs/RATE_LIMIT_RESEARCH.md](docs/RATE_LIMIT_RESEARCH.md)。
- 限流行为变更用真实 Nginx 验证正常、429、恢复、多来源总额度及慢请求并发；页面显示中文提示，API 保持 429 JSON 与 Retry-After。压测仅使用本机临时站点，生产只做低频正常验收。

## 验证与发布

修改路由时验证完整配置及实际 HTTP 行为，覆盖受影响路径和原有应用；本机验证可在临时配置副本中替换证书、路径和端口。线上 `nginx -t` 成功后才 reload。

部署由 `.github/workflows/deploy.yml` 的 `v*.*.*` tag 触发。发布前核对当前远程版本并选用新的 tag；以 Actions 成功和公开路径验证作为完成依据。站点入口或部署行为有变化时同步更新 README。
