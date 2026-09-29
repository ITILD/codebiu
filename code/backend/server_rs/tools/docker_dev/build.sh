# 后端 server_rs 打包镜像(在 server_rs 目录内执行亦可)
# 定位到 server_rs 根目录作为构建上下文
cd "$(dirname "$0")/../.." || exit 1

PROJECT_NAME=server_rs
# 从 Cargo.toml [workspace.package] 提取版本号, 作为镜像 tag(只取第一个匹配)
PROJECT_VERSION="$(sed -n 's/^version *= *"\(.*\)"/\1/p' Cargo.toml | head -n 1)"
if [ -z "$PROJECT_VERSION" ]; then
  echo "错误：无法从 Cargo.toml 解析出 version" >&2
  exit 1
fi
echo "==> 镜像：${PROJECT_NAME}:${PROJECT_VERSION}"

# 校验 Dockerfile COPY 依赖的 gitignored 层是否齐全(缺失会导致构建失败)
for f in config.yaml config.seed.yaml config.dev.yaml .env rbac_model.conf; do
  if [ ! -f "$f" ]; then
    echo "错误：缺少 $f" >&2
    exit 1
  fi
done

# 先停止容器(如果正在运行)
docker stop "${PROJECT_NAME}_${PROJECT_VERSION}" 2>/dev/null

# 删除旧容器
docker rm -f "${PROJECT_NAME}_${PROJECT_VERSION}" 2>/dev/null

# 构建镜像
docker build -f tools/docker_dev/Dockerfile.dev -t "${PROJECT_NAME}:${PROJECT_VERSION}" .
# # log
# docker logs ${PROJECT_NAME}_${PROJECT_VERSION}
