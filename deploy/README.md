# Deploy

`deploy/` 目录存放项目部署相关脚本、Compose 配置和运行时辅助文件。

## 目录说明

- `deploy/rebuild.sh`: 重新构建并启动 `fba_server` 的部署脚本，支持镜像版本号。
- `deploy/backend/cloud/docker-compose.yml`: 云端部署用 Compose 配置。
- `deploy/backend/cloud/.env`: 基础设施变量，如端口映射、数据目录、MySQL/Redis/RabbitMQ 等。
- `deploy/backend/cloud/.env.server`: `fba_server` 运行时环境变量。
- `deploy/backend/supervisor/`: 容器内进程管理配置。

## 前置条件

- 已安装 Docker。
- 已安装 `docker compose` 或 `docker-compose`，脚本会自动检测。
- 服务器上已准备好 `deploy/backend/cloud/.env` 和 `deploy/backend/cloud/.env.server`。
- 项目根目录下存在 `Dockerfile`。

## rebuild.sh 用法

默认使用 `latest` 版本：

```bash
./deploy/rebuild.sh
```

指定镜像版本：

```bash
./deploy/rebuild.sh -v 1.0.0
./deploy/rebuild.sh --version v2.1.3
```

脚本执行流程：

1. 停止并删除当前 `fba_server` 容器。
2. 构建 `fba_server:${IMAGE_VERSION}` 和 `fba_server:latest` 两个 tag。
3. 通过 `deploy/backend/cloud/docker-compose.yml` 启动 `fba_server`。
4. 校验容器启动状态。
5. 清理旧镜像和悬空镜像。

## Compose 中的版本号机制

`deploy/backend/cloud/docker-compose.yml` 中 `fba_server` 使用下面的镜像定义：

```yaml
image: fba_server:${IMAGE_VERSION:-latest}
```

含义：

- 当脚本传入 `IMAGE_VERSION` 时，Compose 会启动对应版本镜像。
- 没有传入时，Compose 默认回退到 `fba_server:latest`。

如果你需要手动启动指定版本，也可以直接执行：

```bash
cd deploy/backend/cloud
IMAGE_VERSION=1.0.0 docker compose up -d fba_server
```

如果环境里只有旧版命令，也可以改成：

```bash
cd deploy/backend/cloud
IMAGE_VERSION=1.0.0 docker-compose up -d fba_server
```

## 常用命令

查看服务状态：

```bash
cd deploy/backend/cloud
docker compose ps fba_server
```

查看日志：

```bash
cd deploy/backend/cloud
docker compose logs -f fba_server
```

停止服务：

```bash
cd deploy/backend/cloud
docker compose stop fba_server
```

## 注意事项

- `deploy/backend/cloud/.env` 和 `deploy/backend/cloud/.env.server` 通常包含敏感配置，不要提交到版本库。
- 脚本会同时打上版本 tag 和 `latest` tag，便于回滚和兼容现有流程。
- 如果旧镜像仍被其他容器引用，脚本会跳过删除，避免误删正在使用的镜像。
