#!/bin/bash
set -e

echo "🔧 开始部署 nginx 配置..."

# 定义需要处理的项目列表
# "crabtris.navydev.top"
PROJECTS=("api.rss.navydev.top" "navydev.top" "rss.navydev.top")

# nginx 配置目录
NGINX_CONF_DIR="/etc/nginx/conf.d"

# 遍历每个项目
for project in "${PROJECTS[@]}"; do
  echo "📦 处理项目: $project"

  # 项目配置文件源路径
  PROJECT_CONF_SOURCE="/root/deploy/${project}/config/nginx/conf.d"

  # 检查项目配置目录是否存在
  if [ -d "$PROJECT_CONF_SOURCE" ]; then
    echo "  ✓ 找到配置目录: $PROJECT_CONF_SOURCE"

    # 复制配置文件到 nginx 配置目录
    if [ -n "$(ls -A "$PROJECT_CONF_SOURCE/*.conf" 2>/dev/null)" ]; then
      cp -v "$PROJECT_CONF_SOURCE"/*.conf "$NGINX_CONF_DIR/"
      echo "  ✓ 已复制 $project 的配置文件"
    else
      echo "  ⚠ 警告: $PROJECT_CONF_SOURCE 中没有找到 .conf 文件"
    fi
  else
    echo "  ⚠ 警告: 配置目录不存在 $PROJECT_CONF_SOURCE"
  fi
done

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
