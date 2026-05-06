# Deploy

`deploy/` 目录存放项目部署相关脚本、Compose 配置和运行时辅助文件。

## 目录说明

- `deploy/deploy.sh`: 统一部署入口，提供 `build`、`switch`、`rebuild` 子命令。
- `deploy/backend/cloud/docker-compose.yml`: 云端部署用 Compose 配置。
- `deploy/backend/cloud/.env`: 基础设施变量，如端口映射、数据目录、MySQL/Redis/RabbitMQ 等。
- `deploy/backend/cloud/.env.server`: `fba_server` 运行时环境变量。
- `deploy/backend/supervisor/`: 容器内进程管理配置。

## 前置条件

- 已安装 Docker。
- 已安装 `docker compose` 或 `docker-compose`，脚本会自动检测。
- 服务器上已准备好 `deploy/backend/cloud/.env` 和 `deploy/backend/cloud/.env.server`。
- 项目根目录下存在 `Dockerfile`。

## deploy.sh 用法

统一入口：

```bash
./deploy/deploy.sh <command> [options]
```

可用子命令：
- `build`: 只构建镜像，不影响当前容器。
- `switch`: 停止当前容器并切换到已构建镜像。
- `rebuild`: 构建镜像、切换容器，并清理旧镜像。

示例：

```bash
./deploy/deploy.sh build -v 1.0.0
./deploy/deploy.sh switch -v 1.0.0
./deploy/deploy.sh rebuild -v 1.0.0
```

## build 子命令

默认使用 `latest` 版本：

```bash
./deploy/deploy.sh build
```

指定镜像版本：

```bash
./deploy/deploy.sh build -v 1.0.0
./deploy/deploy.sh build --version v2.1.3
```

执行流程：
1. 构建 `fba_server:${IMAGE_VERSION}` 和 `fba_server:latest` 两个 tag。
2. 保留当前正在运行的 `fba_server` 容器不变。
3. 不删除旧镜像。

注意：
- 该子命令只构建镜像，不会启动新的 `fba_server` 容器。
- 现有云端 Compose 配置中的 `fba_server` 使用固定 `container_name` 和固定宿主机端口，因此在不停止旧容器的前提下，不能直接再启动一个同名新容器。
- 如果需要切换到新镜像，请后续执行 `./deploy/deploy.sh switch -v <tag>`。

## switch 子命令

默认切换到 `latest` 版本：

```bash
./deploy/deploy.sh switch
```

切换到指定镜像版本：

```bash
./deploy/deploy.sh switch -v 1.0.0
./deploy/deploy.sh switch --version v2.1.3
```

执行流程：
1. 检查 `fba_server:${IMAGE_VERSION}` 是否已存在。
2. 停止并删除当前 `fba_server` 容器。
3. 通过 `deploy/backend/cloud/docker-compose.yml` 启动指定 tag 的 `fba_server`。
4. 校验新容器是否成功启动。

典型流程：

```bash
./deploy/deploy.sh build -v 1.0.0
./deploy/deploy.sh switch -v 1.0.0
```

注意：
- `switch` 不重新构建镜像，只切换到已经构建好的 tag。
- 如果目标镜像不存在，脚本会直接退出，并提示先执行 `./deploy/deploy.sh build -v <tag>`。

## rebuild 子命令

默认使用 `latest` 版本：

```bash
./deploy/deploy.sh rebuild
```

指定镜像版本：

```bash
./deploy/deploy.sh rebuild -v 1.0.0
./deploy/deploy.sh rebuild --version v2.1.3
```

执行流程：
1. 构建 `fba_server:${IMAGE_VERSION}` 和 `fba_server:latest` 两个 tag。
2. 停止并删除当前 `fba_server` 容器。
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
