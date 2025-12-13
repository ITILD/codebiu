
PROJECT_NAME=base_server_bin
PROJECT_VERSION_OLD=0.0.0
PROJECT_VERSION=0.0.1
# 先停止容器(如果正在运行) docker stop knowledge_1.0.1
docker stop ${PROJECT_NAME}_${PROJECT_VERSION_OLD}

# 删除旧容器
docker rm -f ${PROJECT_NAME}_${PROJECT_VERSION_OLD}

# 删除镜像
docker rmi ${PROJECT_NAME}:${PROJECT_VERSION_OLD}

# 构建镜像
docker build -f tools/docker_build/Dockerfile.dist -t ${PROJECT_NAME}:${PROJECT_VERSION} .

# 构建容器
# docker run -d -p 8600:8600 --name ${PROJECT_NAME}_${PROJECT_VERSION} ${PROJECT_NAME}:${PROJECT_VERSION}
# # log
# docker logs ${PROJECT_NAME}_${PROJECT_VERSION}