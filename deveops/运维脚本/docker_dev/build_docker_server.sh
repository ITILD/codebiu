# 后端打包镜像
# 测试环境
# DOCKER_DIR = "docker_rag_server_test_20260820"
# 生产环境
DOCKER_DIR="docker_milvus_20260707"

SERVER_DIR_BASE="/home/here/D/a_apps/$DOCKER_DIR/"
SERVER_DIR_APP="$SERVER_DIR_BASE/rag_server"
# 定位到脚本所在目录，保证相对路径稳定
cd "$(dirname "$0")"


# # ---------- 2. 后端：构建镜像（tag 用 pyproject.toml 的版本号） ----------
BACKEND_DIR="../../code/backend/rag_server"
# # Dockerfile 在后端目录的 tools/docker_dev/ 子目录下，需用 -f 显式指定 code/backend/rag_server/tools/docker_dev/Dockerfile.dev
# DOCKERFILE="$BACKEND_DIR/tools/docker_dev/Dockerfile.dev"
# # 从 backend/pyproject.toml 提取版本号，作为后端镜像 tag
# BACKEND_VERSION="$(sed -n 's/^version *= *"\(.*\)"/\1/p' "$BACKEND_DIR/pyproject.toml")"
# if [ -z "$BACKEND_VERSION" ]; then
#   echo "错误：无法从 $BACKEND_DIR/pyproject.toml 解析出 version" >&2
#   exit 1
# fi
# echo "==> 后端版本号：$BACKEND_VERSION"
# # 注意：[[tool.uv.index]] 段也有行首 name，故只取第一个匹配（即 [project] 段的项目名）
# BACKEND_NAME="$(sed -n 's/^name *= *"\(.*\)"/\1/p' "$BACKEND_DIR/pyproject.toml" | head -n 1)"
# if [ -z "$BACKEND_NAME" ]; then
#   echo "错误：无法从 $BACKEND_DIR/pyproject.toml 解析出 name" >&2
#   exit 1
# fi
# echo "==> 后端名称：$BACKEND_NAME"
# # 构建镜像（使用 BACKEND_DIR 作为构建上下文，因为 pyproject.toml 在该目录）
# docker build -f ${DOCKERFILE} -t ${BACKEND_NAME}:${BACKEND_VERSION} "$BACKEND_DIR"
# echo "==> 构建完成：$BACKEND_NAME:$BACKEND_VERSION"

# 将BACKEND_DIR下外挂的目录/文件复制到SERVER_DIR下
# 外挂项与 devops/rag_server_dev/docker-compose.yaml 中 volumes 挂载保持一致
mkdir -p "$SERVER_DIR_APP"
cp -r "$BACKEND_DIR/config.yaml" "$SERVER_DIR_APP/"
cp -r "$BACKEND_DIR/config.docker.yaml" "$SERVER_DIR_APP/"
mkdir -p "$SERVER_DIR_APP/temp_source/"
cp -r "$BACKEND_DIR/temp_source/model" "$SERVER_DIR_APP/temp_source/"
cp -r "$BACKEND_DIR/public" "$SERVER_DIR_APP/"
cp -r "$BACKEND_DIR/rbac_model.conf" "$SERVER_DIR_APP/"
cp -r "$BACKEND_DIR/src" "$SERVER_DIR_APP/"
