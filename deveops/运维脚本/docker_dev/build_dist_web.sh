# nginx 静态文件目录：前端构建产物(index.html 等)最终落这里
# 测试环境
# DOCKER_DIR = "docker_rag_server_test_20260820"
# 生产环境
DOCKER_DIR="docker_milvus_20260707"

DOCKER_NAME="$DOCKER_DIR-nginx"
NGINX_DIST_DIR_BASE="/home/here/D/a_apps/$DOCKER_DIR/nginx"


NGINX_DIST_DIR_HTML_INDEX="$NGINX_DIST_DIR_BASE/html/index/"
NGINX_DIST_DIR_CONFIG="$NGINX_DIST_DIR_BASE/conf/conf.d/"
# 状态设置：覆盖 = 新 dist 直接覆盖原 index 目录；备份 = 原 index 目录改名为 index_当前时间，新 dist 写入新的 index 目录
# DIST_MODE="备份"
DIST_MODE="备份"
# 定位到脚本所在目录，保证相对路径稳定(脚本在 devops/docker_dev/，前端在 code/frontend/web/)
cd "$(dirname "$0")"

# ---------- 1. 前端：容器内构建 dist 并直接导出到 nginx 目录(不产生镜像) ----------
FRONTEND_DIR="../../code/frontend/web"
# Dockerfile 在前端目录的 tools/docker_dev/ 子目录下，需用 -f 显式指定
DOCKERFILE="$FRONTEND_DIR/tools/docker_dev/Dockerfile.dev"

echo "==> [1/2] 构建前端 dist(Dockerfile：$DOCKERFILE)..."

# 备份模式：原 index 目录改名为 index_当前时间；覆盖模式：直接写入原目录
if [ "$DIST_MODE" = "备份" ] && [ -d "$NGINX_DIST_DIR_HTML_INDEX" ]; then
    BACKUP_DIR="${NGINX_DIST_DIR_HTML_INDEX%/}_$(date +%Y%m%d_%H%M%S)"
    echo "==> 备份原目录：${NGINX_DIST_DIR_HTML_INDEX%/} -> $BACKUP_DIR"
    mv "${NGINX_DIST_DIR_HTML_INDEX%/}" "$BACKUP_DIR"
fi
mkdir -p "$NGINX_DIST_DIR_HTML_INDEX"

echo "==> 导出 dist 内容到 $NGINX_DIST_DIR_HTML_INDEX ..."
# BuildKit --output 直接把最终阶段(scratch，仅含 dist 内容)写到宿主机目录
docker build -f "$DOCKERFILE" --output="$NGINX_DIST_DIR_HTML_INDEX" "$FRONTEND_DIR"

echo "==> 构建完成：$NGINX_DIST_DIR_HTML_INDEX"

# ---------- 2. nginx 配置：复制 default.conf 到 nginx 目录 docker_milvus_20260707/nginx/conf/conf.d/
mkdir -p "$NGINX_DIST_DIR_BASE/conf/conf.d/"
cp default.conf "$NGINX_DIST_DIR_BASE/conf/conf.d/"
echo "==> nginx 配置完成：$NGINX_DIST_DIR_BASE/conf/conf.d/default.conf"

# ---------- 3. 热更新docker内nginx配置 ----------
docker exec -it "$DOCKER_NAME" nginx -s reload
echo "==> nginx 配置热更新完成：$DOCKER_NAME"