# 后端 server_rs(Rust) 打包镜像
# 定位到脚本所在目录，保证相对路径稳定
cd "$(dirname "$0")"

# ---------- 后端：构建镜像（tag 用 Cargo.toml 的版本号） ----------
BACKEND_DIR="../../code/backend/server_rs"
# Dockerfile 在后端目录的 tools/docker_dev/ 子目录下，需用 -f 显式指定 code/backend/server_rs/tools/docker_dev/Dockerfile.dev
DOCKERFILE="$BACKEND_DIR/tools/docker_dev/Dockerfile.dev"
# 从 Cargo.toml [workspace.package] 提取版本号，作为后端镜像 tag(只取第一个匹配)
BACKEND_VERSION="$(sed -n 's/^version *= *"\(.*\)"/\1/p' "$BACKEND_DIR/Cargo.toml" | head -n 1)"
if [ -z "$BACKEND_VERSION" ]; then
  echo "错误：无法从 $BACKEND_DIR/Cargo.toml 解析出 version" >&2
  exit 1
fi
echo "==> 后端版本号：$BACKEND_VERSION"
# 镜像名与主二进制同名(app crate 的 [[bin]] name)
BACKEND_NAME="server_rs"
echo "==> 后端名称：$BACKEND_NAME"

# 校验 Dockerfile COPY 依赖的 gitignored 层是否齐全(缺失会导致构建失败)
for f in config.yaml config.seed.yaml config.dev.yaml .env rbac_model.conf; do
  if [ ! -f "$BACKEND_DIR/$f" ]; then
    echo "错误：缺少 $BACKEND_DIR/$f" >&2
    exit 1
  fi
done

# 构建镜像（使用 BACKEND_DIR 作为构建上下文，因为 Cargo.toml 在该目录）
docker build -f "$DOCKERFILE" -t "${BACKEND_NAME}:${BACKEND_VERSION}" "$BACKEND_DIR"
echo "==> 构建完成：${BACKEND_NAME}:${BACKEND_VERSION}"

# ---------- 可选：外挂目录/文件同步 ----------
# 如需与 docker-compose volumes 挂载方式部署(参考 build_docker_server.sh),
# 将 config*.yaml / .env / public / rbac_model.conf / temp_source 同步到部署目录即可
