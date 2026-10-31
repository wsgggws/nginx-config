"""真实 Nginx 验证；所有请求只打本机临时站点和模拟后端。"""

from concurrent.futures import ThreadPoolExecutor
import http.client
import http.server
import json
from pathlib import Path
import re
import shutil
import socket
import ssl
import subprocess
import tempfile
import threading
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class Backend(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self):
        if "slow-test" in self.path:
            with self.server.condition:
                self.server.active += 1
                self.server.condition.notify_all()
            self.server.release.wait(6)
            with self.server.condition:
                self.server.active -= 1
        body = json.dumps({"path": self.path}).encode()
        try:
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass  # 临时 Nginx 退出时可能关闭仍在收尾的上游连接。

    def log_message(self, *args):
        pass


class BackendServer(http.server.ThreadingHTTPServer):
    request_queue_size = 128


@unittest.skipUnless(shutil.which("nginx") and shutil.which("openssl"), "需要 nginx 和 openssl")
class RateLimitTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="navydev-nginx-", dir="/tmp")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.conf = self.root / "nginx"
        shutil.copytree(ROOT / "config/nginx", self.conf)
        self.backend = BackendServer(("127.0.0.1", 0), Backend)
        self.backend.release = threading.Event()
        self.backend.condition = threading.Condition()
        self.backend.active = 0
        self.addCleanup(self.backend.server_close)
        self.addCleanup(self.backend.shutdown)
        self.addCleanup(self.backend.release.set)
        threading.Thread(target=self.backend.serve_forever, daemon=True).start()
        self.http_port, self.https_port = free_port(), free_port()
        for name in ["log/nginx", "cache/nginx/proxy", "www/navydev/help", "www/certbot/.well-known/acme-challenge",
                     "www/crabtris.navydev.top", "metric/web", "metric/config", "lib/navydev-metric"]:
            (self.root / name).mkdir(parents=True)
        for site in ["me", "blog", "rss"]:
            target = self.root / "www/navydev.top" / site
            (target / "assets").mkdir(parents=True)
            (target / "index.html").write_text(site)
            (target / "assets/test.js").write_text("asset-ok")
        (self.root / "www/crabtris.navydev.top/index.html").write_text("crabtris")
        shutil.copytree(self.conf / "help", self.root / "www/navydev/help", dirs_exist_ok=True)
        (self.root / "www/certbot/.well-known/acme-challenge/test").write_text("acme-ok")
        (self.root / "metric/web/index.html").write_text("metric-ok")
        (self.root / "metric/config/dashboard.json").write_text('{"config":true}')
        (self.root / "lib/navydev-metric/summary.json").write_text('{"summary":true}')
        (self.root / "lib/navydev-metric/report.html").write_text("report-ok")
        cert, key = self.root / "cert.pem", self.root / "key.pem"
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
                        "-subj", "/CN=navydev.top", "-keyout", str(key), "-out", str(cert)],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        mime = next(path for path in [Path("/etc/nginx/mime.types"), Path("/opt/homebrew/etc/nginx/mime.types")]
                    if path.exists())
        shutil.copy(mime, self.conf / "mime.types")
        for file in self.conf.rglob("*.conf"):
            text = file.read_text().replace("/etc/nginx", str(self.conf)).replace("/var/", str(self.root) + "/")
            text = text.replace("/opt/navydev.top_metric", str(self.root / "metric"))
            text = re.sub(r"/etc/letsencrypt/live/[^;]+/fullchain.pem", str(cert), text)
            text = re.sub(r"/etc/letsencrypt/live/[^;]+/privkey.pem", str(key), text)
            text = re.sub(r"127\.0\.0\.1:(8000|8010|19999)", f"127.0.0.1:{self.backend.server_port}", text)
            text = re.sub(r"listen \[::\]:[^;]+;", "", text)
            text = text.replace("listen 443 ", f"listen 127.0.0.1:{self.https_port} ")
            text = re.sub(r"listen 80([ ;])", f"listen 127.0.0.1:{self.http_port}" + r"\1", text)
            text = text.replace("use epoll;", "").replace("worker_processes auto;", "worker_processes 2;")
            # 仅本机临时配置用独立测试头模拟多个来源 IP；生产配置不信任转发头。
            text = text.replace("server_name navydev.top;", "server_name navydev.top;\n"
                                "set_real_ip_from 127.0.0.1; real_ip_header X-Test-IP;")
            file.write_text(text)
        main = self.conf / "nginx.conf"
        text = main.read_text().replace("http {", "http {\n" + "\n".join(
            f"{module}_temp_path {self.root}/{module};"
            for module in ["client_body", "proxy", "fastcgi", "uwsgi", "scgi"]))
        main.write_text(f"pid {self.root}/nginx.pid;\nerror_log {self.root}/startup.log;\n" + text)
        command = ["nginx", "-p", str(self.conf) + "/", "-c", str(main)]
        result = subprocess.run(command + ["-t"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.process = subprocess.Popen(command + ["-g", "daemon off;"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.addCleanup(self.stop)
        self.context = ssl._create_unverified_context()
        for _ in range(100):
            try:
                with socket.create_connection(("127.0.0.1", self.https_port), .1):
                    break
            except OSError:
                time.sleep(.02)
        else:
            self.fail("临时 Nginx 未启动")

    def stop(self):
        if self.process.poll() is None:
            self.process.terminate()
            self.process.wait(timeout=5)

    def request(self, path, ip=None, host="navydev.top", connection=None, extra=None, response_headers=None):
        conn = connection or http.client.HTTPSConnection("127.0.0.1", self.https_port, context=self.context, timeout=10)
        headers = {"Host": host, "User-Agent": "Mozilla/5.0 local verification"}
        if ip:
            headers["X-Test-IP"] = ip
        headers.update(extra or {})
        conn.request("GET", path, headers=headers)
        response = conn.getresponse()
        if response_headers is not None:
            response_headers.update(dict(response.getheaders()))
        result = response.status, response.read()
        if connection is None:
            conn.close()
        return result

    def flood(self, path, count, distributed=False, extra=None):
        # 每个线程复用连接，使流量足够密集来验证真实限流，不依赖公网速度。
        def batch(worker):
            conn = http.client.HTTPSConnection("127.0.0.1", self.https_port, context=self.context, timeout=10)
            try:
                return [self.request(path, f"192.0.{worker}.{index + 1}" if distributed else None,
                                     connection=conn, extra=extra)[0] for index in range(count // 8)]
            finally:
                conn.close()
        with ThreadPoolExecutor(max_workers=8) as pool:
            return [status for batch_results in pool.map(batch, range(8)) for status in batch_results]

    def errors(self):
        return (self.root / "log/nginx/error.log").read_text()

    def test_routes_directory_and_log(self):
        html = self.request("/")[1].decode()
        self.assertEqual(re.findall(r'<li><a href="([^"]+)"', html),
                         ["/me", "/ebook", "/blog", "/rss", "/crabtris", "/metric"])
        for path in ["/", "/help", "/me", "/me/assets/test.js", "/ebook", "/ebook/js/app.js",
                     "/blog", "/rss", "/rss/assets/test.js", "/crabtris", "/metric/",
                     "/metric/dashboard.json", "/metric/access/summary.json", "/metric/access/",
                     "/metric/system/api/v1/info"]:
            self.assertEqual(self.request(path)[0], 200, path)
        for path, forwarded in [("/ebook/api/v1/health", "/ebook/api/v1/health"),
                                ("/ebook/api/v1/books/1/audio/0", "/ebook/api/v1/books/1/audio/0"),
                                ("/rss/backend/api/v1/rss/articles", "/api/v1/rss/articles"),
                                ("/rss/openapi.json", "/openapi.json"), ("/openapi.json", "/openapi.json")]:
            status, body = self.request(path)
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(body)["path"], forwarded)
        self.assertEqual(self.request("/metric")[0], 302)
        conn = http.client.HTTPConnection("127.0.0.1", self.http_port)
        conn.request("GET", "/.well-known/acme-challenge/test", headers={"Host": "navydev.top"})
        response = conn.getresponse()
        self.assertEqual((response.status, response.read()), (200, b"acme-ok"))
        conn.close()
        self.stop()
        log = (self.root / "log/nginx/navydev-metric.access.log").read_text()
        self.assertIn('GET / HTTP/', log)
        self.assertIn('GET /rss/assets/test.js HTTP/', log)

    def test_backend_rate_recovery_and_cannot_bypass(self):
        statuses = self.flood("/ebook/api/v1/books?one=1", 40)
        self.assertIn(200, statuses)
        self.assertIn(429, statuses)
        for index, path in enumerate(["/rss/backend/test", "/ebook/api/v1/test?two=2", "/ebook/%61pi/v1/test", "/ebook//api/v1/test"]):
            self.assertEqual(self.request(path, extra={"X-Forwarded-For": f"198.51.100.{index + 1}"})[0], 429, path)
        self.assertIn('zone "navydev_backend_ip"', self.errors())
        self.assertEqual(self.request("/test", host="obz.navydev.top")[0], 429)
        self.assertEqual(self.request("/me/assets/test.js")[0], 200)
        time.sleep(.3)
        self.assertEqual(self.request("/rss/backend/test")[0], 200)
        self.assertIn('lr="REJECTED"', self.flush_access())

    def flush_access(self):
        self.stop()
        return (self.root / "log/nginx/access.log").read_text()

    def test_static_shared_rate(self):
        statuses = self.flood("/me/assets/test.js", 240)
        self.assertIn(200, statuses)
        self.assertIn(429, statuses)
        self.assertIn('zone "navydev_site_ip"', self.errors())
        self.assertEqual(self.request("/blog")[0], 429)

    def test_friendly_page_and_api_response(self):
        self.flood("/me/assets/test.js", 240)
        headers = {}
        status, body = self.request("/", response_headers=headers)
        self.assertEqual(status, 429)
        self.assertIn("请稍后再试", body.decode())
        self.assertIn('href=""', body.decode())
        self.assertIn("text/html", headers["Content-Type"])
        self.assertEqual(headers["Retry-After"], "5")
        self.assertEqual(headers["Cache-Control"], "no-store")
        headers = {}
        # 用新的 IP 耗尽自身 API 突发，避免前一组静态限流掩盖 API 响应。
        # 校验实际收到的第一个拒绝响应，而非额度恢复后可能成功的最后一次请求。
        for _ in range(40):
            status, body = self.request("/ebook/api/test", ip="203.0.113.1", response_headers=headers)
            if status == 429:
                break
        self.assertEqual(status, 429)
        self.assertEqual(json.loads(body)["error"]["code"], "RATE_LIMITED")
        self.assertIn("请稍等", json.loads(body)["detail"])
        self.assertIn("application/json", headers["Content-Type"])
        self.assertEqual(headers["Retry-After"], "5")

    def test_netdata_initial_burst_then_limit(self):
        for _ in range(35):
            self.assertEqual(self.request("/metric/system/api/v1/data?chart=system.cpu")[0], 200)
        self.assertEqual(self.request("/metric/access/summary.json")[0], 200)
        self.assertIn(429, self.flood("/metric/system/api/v1/info", 120))
        self.assertIn('zone "navydev_metric_ip"', self.errors())

    def test_distributed_backend_and_site_limits(self):
        self.assertIn(429, self.flood("/rss/backend/test", 128, distributed=True))
        errors = self.errors()
        self.assertIn('zone "navydev_backend_total"', errors)
        self.assertNotIn('zone "navydev_backend_ip"', errors)
        self.assertIn(429, self.flood("/me/assets/test.js", 1200, distributed=True))
        self.assertIn('zone "navydev_site_total"', self.errors())

    def test_distributed_netdata_limit(self):
        self.assertIn(429, self.flood("/metric/system/api/v1/info", 256, distributed=True))
        self.assertIn('zone "navydev_metric_total"', self.errors())

    def test_slow_backend_concurrency(self):
        with ThreadPoolExecutor(max_workers=9) as pool:
            futures = [pool.submit(self.request, "/ebook/api/slow-test") for _ in range(8)]
            try:
                with self.backend.condition:
                    self.assertTrue(self.backend.condition.wait_for(lambda: self.backend.active == 8, timeout=3))
                self.assertEqual(self.request("/rss/backend/test")[0], 429)
                self.assertIn('zone "navydev_backend_conn_ip"', self.errors())
            finally:
                self.backend.release.set()
            self.assertTrue(all(future.result()[0] == 200 for future in futures))

    def test_distributed_slow_backend_concurrency(self):
        with ThreadPoolExecutor(max_workers=32) as pool:
            futures = []
            try:
                for index in range(32):
                    futures.append(pool.submit(self.request, "/rss/backend/slow-test", f"192.0.2.{index + 1}"))
                    time.sleep(.04)  # 慢请求保持在途，同时避免先碰到请求速率上限。
                with self.backend.condition:
                    self.assertTrue(self.backend.condition.wait_for(lambda: self.backend.active == 32, timeout=3))
                self.assertEqual(self.request("/ebook/api/test", ip="198.51.100.1")[0], 429)
                self.assertIn('zone "navydev_backend_conn_total"', self.errors())
            finally:
                self.backend.release.set()
            self.assertTrue(all(future.result()[0] == 200 for future in futures))


if __name__ == "__main__":
    unittest.main()
