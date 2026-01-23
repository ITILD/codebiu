#!/bin/bash
PROJECT_NAME=docker_init_20260121
COMPOSE_FILE=docker-compose.yaml
# 启动 Docker Compose 服务（后台运行）docker compose down
PROJECT_NAME=$PROJECT_NAME docker compose -f $COMPOSE_FILE down