# 验证记录

## 2026-10-31：目录顺序与轻量限流

本地使用 macOS / Nginx 1.31.8，完整中央配置的临时副本替换本机证书、路径、端口，移除 macOS 不支持的 epoll；生产兼容 Nginx 1.18 的 `listen 443 ssl http2` 写法保持。全局限流区使用 256 KiB，兼容本机 16 KiB 内存页；IP 区使用 1 MiB，新增区域合计约 5 MiB。

- Python 标准库驱动真实 Nginx 的 10 项测试，覆盖 `/` 和 `/help` 的目录顺序、原有静态资源和应用入口、API 前缀转发、监控 JSON/报告、ACME 通道、专用日志和电子书批量封面。
- 验证静态共享单 IP 额度、电子书/RSS 共用额度、Netdata 初始化突发后限流；请求超额返回 429，等待后恢复；API 限流不会消耗静态请求的专属后端额度。
- 在临时 Nginx 中以专用受信任测试头模拟多个来源 IP，验证全站、后端、Netdata 总速率分别触发对应 zone；此信任配置不进入生产。生产配置仍按连接来源 IP，不信任客户端自行传入的 X-Forwarded-For。
- 慢模拟后端分别验证单 IP 8 个、多个来源合计 32 个在途请求后触发 429。检查查询参数、编码路径、重复斜杠、切换服务路径与旧子域名不会绕过后端限制，且主日志记录 `lr="REJECTED"`。
- ShellCheck 和所有 shell 语法检查通过。新增 CI 执行同一组检查，tag 部署依赖该检查成功再执行线上 `nginx -t` 与 reload。
- 真实 429 验证中文 HTML 提示页和 API JSON 的内容、状态码、Content-Type、Retry-After 与禁止缓存响应头。Chromium 检查提示页 1280/375/320px 布局；在真实电子书/RSS 页面仅模拟 API 429，确认电子书列表与 RSS 订阅栏显示中文提示，未对生产发起压测。

以上速率、并发和多来源验证均针对本地模拟后端，不代表真实服务器容量压测；生产只进行低频正常页面/API 和浏览器加载验收。

### 线上验收

- 监控提示提交 `9f3b160` 的 [Deploy](https://github.com/wsgggws/navydev.top_metric/actions/runs/41202689607) 成功，线上脚本与仓库内容一致，真实摘要、Netdata API 和 GoAccess 报告可读。
- 中央配置以 `v0.0.21` 发布：[Deploy](https://github.com/wsgggws/nginx-config/actions/runs/41203178743) 成功，包含 Ubuntu CI 的 9 项真实 Nginx 测试、线上 Nginx 1.18 的 `nginx -t` 和 reload。首次 CI 暴露了测试末次请求已恢复额度的时序假设，已改为捕获实际 429 后校验响应；修正后的 main CI 与 tag CI 均通过。
- `/` 与 `/help` 均返回新目录，顺序为 `/me`、`/ebook`、`/blog`、`/rss`、`/crabtris`、`/metric`。`/help/rate-limit.html` 与仓库提示页一致；应用入口、电子书健康接口、RSS OpenAPI、监控配置/摘要/Netdata API、GoAccess 报告返回 200，真实摘要解析失败为 0。
- 独立 Chromium 会话直接访问生产站点：目录正确，375px 无页面溢出；聚合页初次加载和一次系统轮询正常；完整 Netdata 面板显示系统和 CPU 图表，观察 12 秒更新未出现 429；RSS 正常加载未出现 429。Netdata 自带外部 registry/news 请求有 CORS 错误，本机指标图正常，此类请求不属于本站限流错误。
- `v0.0.21` 的电子书真实首屏出现 4 个封面请求被误限流，封面接口只读取已有文件，已改为普通资源额度；补充一次批量 24 个封面的真实 Nginx 测试，以及耗尽 API 额度后封面仍可读取、相似非封面路径仍受 API 限制的边界检查。
- 生产没有执行超限压测，也没有伪造来源 IP。429 页面/JSON、多来源总额度及慢请求并发的拒绝行为由本地和 CI 的临时 Nginx/模拟后端验证。
