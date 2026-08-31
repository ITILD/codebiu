# 导出当前docker compose项目中的所有镜像到tar文件
docker compose images | awk 'FNR > 2 {print $2":"$3}' | sort -u | xargs docker save -o images.tar