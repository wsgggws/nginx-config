# navydev.top 轻量限流依据

核对日期：2026-10-31。目标服务器 Nginx 1.18。资料以 Nginx 官方模块文档、1.18.0 源码和产品官方文档为准。

## 选择

采用现有 Nginx 的 `limit_req`，叠加单 IP 与共享总额度；对耗时业务接口再加 `limit_conn`。规则统一放在中央仓库，由 `map` 分类后在 server 层引用，避免修改每个 location。无需 Redis、额外进程或应用代码。

| 方案 | 适用范围 | 本次结论 |
| --- | --- | --- |
| Nginx 请求速率 + 后端并发限制 | 单 IP 刷请求、多个 IP 合计消耗源站后端 | 采用；现有 Nginx 内置能力，部署最少 |
| CDN/WAF/DDoS 防护 | 在请求到源站前过滤，抵御较大分布式流量 | 后续出现持续攻击时再接入；需要代理/DNS和源站访问边界配合 |
| Fail2ban | 从日志识别持续异常并封禁 IP | 本次不引入；需新增日志规则和封禁状态，不能替代请求即时限流 |

Nginx 官方支持同时限制同一 IP 和整个虚拟主机的请求速率，也支持同样的双层并发限制。[请求模块](https://nginx.org/en/docs/http/ngx_http_limit_req_module.html#limit_req)、[并发模块](https://nginx.org/en/docs/http/ngx_http_limit_conn_module.html#limit_conn)。Fail2ban 的机制是扫描日志并修改防火墙封禁 IP，属于事后响应。[官方 README](https://github.com/fail2ban/fail2ban#readme)。Cloudflare 官方说明其边缘系统可自动缓解 L3/L4 和 L7 DDoS；这类源站前防护才有机会在服务器公网链路被占满前过滤流量。[官方概览](https://developers.cloudflare.com/ddos-protection/)、[对应官方文档源码](https://github.com/cloudflare/cloudflare-docs/blob/production/src/content/docs/ddos-protection/index.mdx)。

## 初始额度与口径

以下为小站的初始保护值，并非经过容量压测得到的吞吐上限。所有规则叠加生效；业务组的共享额度覆盖该组全部入口，而非每个 path 单独享有一份。

| 请求组 | 单 IP 持续速率 / burst | 共享持续速率 / burst | 额外限制 |
| --- | --- | --- | --- |
| 全部站点内容（含 `/`、静态资源和下列接口） | 30 r/s / 100 | 200 r/s / 200 | 基线 |
| 电子书 API、RSS 后端及其文档/OpenAPI 入口 | 5 r/s / 15 | 后端组共用 30 r/s / 30 | 同时处理 8 请求/IP、后端组共用 32 请求 |
| Netdata API | 15 r/s / 60 | Netdata API 组共用 60 r/s / 120 | 允许完整仪表板的并发初始化和轮询 |

电子书音频和上传都属于电子书 API，开始请求时计速率，处理期间占用并发名额；传输一个音频文件不会按每秒重复计数。静态页面的多个 CSS、JS、图片各自算一次请求，所以允许较大 burst；`/metric` 聚合页每次轮询的四个指标请求同样需要突发余量。`/me`、`/blog`、`/crabtris`、RSS 前端和索引页共享基线，避免为每个静态项目复制相同配置。

电子书封面 `/ebook/api/v1/books/<id>/cover` 位于 API 前缀下，但实现是读取已有文件的 `FileResponse`，归普通资源额度。仅用 URL 的 API 前缀粗分会误伤书架首屏批量图片；已通过真实浏览器发现并补充批量封面的 Nginx 回归测试。来源：相邻 `navydev.top_ebook/lector/api/books.py` 的 `get_cover`，当前函数第 153–173 行。

`rate` 是漏桶算法的长期平均额度，`burst` 是允许积累的超额量；`nodelay` 让仍有突发余量的请求立即处理，超过余量就拒绝。因此“30 r/s、burst 100”不等于任何固定一秒内严格最多 30 次，也不等于每秒重新赠送 100 次。突发额度按速率恢复。超额响应统一设为 429，代替模块默认的 503。[官方语义](https://nginx.org/en/docs/http/ngx_http_limit_req_module.html#limit_req)、[状态码配置](https://nginx.org/en/docs/http/ngx_http_limit_req_module.html#limit_req_status)。

共享后端额度能阻止多个低频 IP 合计无限进入业务服务，但攻击者也可能占满共享额度，使正常用户同时遇到 429。它是保护源站资源的熔断边界，不是分布式攻击下的公平调度保证。单 IP 额度也会被同一出口下的多个用户共享。

超限响应保留 429：页面使用静态中文提示页，API 使用兼容电子书 `error.message` 和 RSS `detail` 的 JSON，附带 `Retry-After: 5` 与 `Cache-Control: no-store`。提示页只提供手动重试，避免自动重复提交上传等操作；监控轮询按原定间隔恢复。使用 `error_page` 的变量目标在命名 location 中分别渲染 HTML 与 JSON，避免把 HTML 返回给 API 客户端。[Nginx error_page 文档](https://nginx.org/en/docs/http/ngx_http_core_module.html#error_page)。

## 分类、继承和执行阶段

1. 分类使用规范化的 `$uri`。Nginx location 匹配会先进行 `%XX` 解码、相对路径归一化及相邻斜杠合并；`$request_uri` 则保留原始路径和参数。按原始 URI 只匹配 `/ebook/api/` 会漏掉 `/ebook/%61pi/` 或多余斜杠等同义请求，导致实际进入 API 的请求使用静态额度。[location 规则](https://nginx.org/en/docs/http/ngx_http_core_module.html#location)、[变量定义](https://nginx.org/en/docs/http/ngx_http_core_module.html#variables)。现有 RSS `proxy_pass` 的前缀替换发生在转发阶段，限流分类时仍可看到规范化的 `/rss/backend/`。
2. 不属于某组的请求，其限流 key 必须映射为**空字符串**，整条 key 为空才免于该组计数；把空组名拼接 IP 后仍然非空，不会豁免。`limit_req_zone` 和 `limit_conn_zone` 都明确不记录空 key。[请求 key](https://nginx.org/en/docs/http/ngx_http_limit_req_module.html#limit_req_zone)、[并发 key](https://nginx.org/en/docs/http/ngx_http_limit_conn_module.html#limit_conn_zone)。
3. 相关 `limit_req` 全放在同一个 server 层，子 location 沿用；应删除原电子书 location 的旧限制。**子层只要出现任意一条 `limit_req`，就不会继承父层整组 `limit_req`**。`limit_conn` 同理，不能误以为新写的一条会自动与父层叠加。[请求继承](https://nginx.org/en/docs/http/ngx_http_limit_req_module.html#limit_req)、[并发继承](https://nginx.org/en/docs/http/ngx_http_limit_conn_module.html#limit_conn)。
4. `limit_conn` 统计正在处理且已读完请求头的请求，不是所有打开的 TCP 连接数。HTTP/2 下每个并发请求分别计数，不能把 8 个名额理解为允许 8 条 TCP 连接、每条又可无限开流。[官方定义](https://nginx.org/en/docs/http/ngx_http_limit_conn_module.html#limit_conn)。
5. 请求限流和并发处理器挂在 preaccess 阶段。仅 `return 301/302/403` 的入口会在更早的 rewrite 阶段结束，不能宣称其也受这些限流处理器约束；跳转后的实际内容受限。对无需访问后端的重定向保留现状，避免为限跳转引入额外模块。[rewrite 执行及 return](https://nginx.org/en/docs/http/ngx_http_rewrite_module.html#return)、[1.18.0 请求限流注册](https://github.com/nginx/nginx/blob/release-1.18.0/src/http/modules/ngx_http_limit_req_module.c#L1070)、[1.18.0 并发注册](https://github.com/nginx/nginx/blob/release-1.18.0/src/http/modules/ngx_http_limit_conn_module.c#L743)、[处理阶段顺序](https://github.com/nginx/nginx/blob/release-1.18.0/src/http/ngx_http.c#L456)。
6. 同样检查旧子域名。仍代理到业务后端的旧入口必须纳入同组限流，避免绕开主域名的共享总额度；纯 301 旧入口只产生跳转。

## 客户端 IP 与防护边界

当前直接使用连接来源的 `$binary_remote_addr`，不会信任用户自行提交的 `X-Forwarded-For`。未来经过 CDN 或负载均衡时，只有已确认的代理地址/CIDR 可配置进 `set_real_ip_from`，再按供应商协议选择 `real_ip_header`；信任任意来源的转发头会允许攻击者伪造 IP，绕过单 IP 额度。[Nginx Real IP 官方文档](https://nginx.org/en/docs/http/ngx_http_realip_module.html#set_real_ip_from)。

这些限制发生在请求已经到达本机并解析后，可降低后端请求量与在途请求数，无法释放已占满的公网带宽，也不能代替 TCP/SYN 等网络层防护。若出现大量来源的持续攻击，下一步是 CDN/WAF/上游清洗，并按可信代理配置真实 IP 和源站访问边界；继续降低单 IP 额度并不能解决所有分布式流量。

## 验证重点

用真实 Nginx 检查完整配置及 HTTP 行为：正常首页与所有项目入口、静态多资源突发、API 429、不同服务组的共享计数、等待后恢复、HTTP/2 或并发长请求、编码/双斜杠入口、旧子域名入口，以及 `/metric` 完整仪表板初始化和聚合页刷新。阈值首先是保护边界，后续结合 429、源站负载和正常访问行为调整。
