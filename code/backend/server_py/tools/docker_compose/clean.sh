#!/bin/bash
echo "正在清理悬空镜像..."
docker image prune -f
echo "清理完成！当前镜像列表："
docker images

# 彻底清理（包括未使用的镜像和缓存）​​
# docker system prune -f