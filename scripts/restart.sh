#!/bin/bash
set -e

echo "🔧 检查并重载中央 nginx 配置..."

# 站点配置只由 nginx-config 仓库发布。不要在这里回读各业务项目里的旧
# conf.d，否则 navydev.top / rss.navydev.top 的旧配置会覆盖中央路由。

echo ""
echo "🔍 测试 nginx 配置..."
if nginx -t; then
  echo "✅ nginx 配置测试通过"
  echo ""
  echo "🔄 重载 nginx..."
  systemctl reload nginx
  echo "✅ nginx 重载完成"
else
  echo "❌ nginx 配置测试失败，请检查配置文件"
  exit 1
fi

echo ""
echo "🎉 部署完成！"
