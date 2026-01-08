# 开发环境部署指南

## 概述

本项目提供了一套完整的开发环境 Docker Compose 部署方案，包含代码管理、持续集成、问题跟踪、代码检索和对象存储等开发工具栈。

## 架构设计

```
开发环境 Docker 集群
├── Web 服务层
│   ├─ Gerrit (8081)    - 代码审查与 Git 管理
│   ├─ Jenkins (8082)   - CI/CD 持续集成
│   ├─ Bugzilla (8083)  - 问题跟踪与项目管理
│   ├─ OpenGrok (8084)  - 代码检索与分析
│   └─ MinIO (9090)     - 对象存储服务
├── 认证服务层
│   ├─ LDAP (389)       - 统一认证服务
│   └─ LDAP Admin (6443) - LDAP 管理界面
└── 数据存储层
    ├─ MariaDB (3306)   - 主数据库
    └─ 持久化存储       - 数据持久化
```

## 使用说明

### 1. 修改配置

- 将 10.240.225.34 替换为你的服务器实际IP或域名
- 生产环境请修改所有密码（特别是 root/admin 密码）
- 根据服务器内存大小调整 JVM 参数

### 2. 启动服务

```bash
docker-compose up -d
```

### 3. 访问地址

- Gerrit:    http://10.240.225.34:8081
- Jenkins:   http://10.240.225.34:8082
- Bugzilla:  http://10.240.225.34:8083
- OpenGrok:  http://10.240.225.34:8084
- MinIO:     http://10.240.225.34:9090
- LDAP Admin: https://10.240.225.34:6443

### 4. 默认凭证

- MariaDB root: root / Root_123456
- MariaDB app:  bugzilla / Bugzilla_123456
- LDAP Admin:   cn=admin,dc=jiqid,dc=com / secret
- MinIO:        root / Admin@123
- Bugzilla Admin: admin@jiqid.com / Admin@123

## 快速启动

### 分步启动（推荐）

#### 第一步：只启动数据库

```bash
docker-compose up -d mariadb
```

#### 第二步：启动认证服务

```bash
# 启动 LDAP
docker-compose up -d ldap

# 启动LDAP 管理界面
docker-compose up -d ldap-admin
```

#### 第三步：启动应用服务

```bash
# 启动Gerrit
docker-compose up -d gerrit

# 启动Jenkins
docker-compose up -d jenkins

# 启动Bugzilla
docker-compose up -d bugzilla

# 启动OpenGrok
docker-compose up -d opengrok
```

#### 第四步：检查服务状态

```bash
docker-compose ps
```

## 服务详细配置

### Web 服务

| 服务名称     | 端口   | 访问地址                      | 说明           |
|----------|------|---------------------------|--------------|
| Gerrit   | 8081 | http://10.240.225.34:8081 | 代码审查与 Git 管理 |
| Jenkins  | 8082 | http://10.240.225.34:8082 | CI/CD 持续集成   |
| Bugzilla | 8083 | http://10.240.225.34:8083 | 问题跟踪与项目管理    |
| OpenGrok | 8084 | http://10.240.225.34:8084 | 代码检索与分析      |
| MinIO    | 9090 | http://10.240.225.34:9090 | 对象存储控制台      |

### 数据库服务

| 数据库     | 端口   | 用户名      | 密码              | 数据库名     |
|---------|------|----------|-----------------|----------|
| MariaDB | 3306 | root     | Root_123456     | 所有数据库    |
| MariaDB | 3306 | bugzilla | Bugzilla_123456 | bugzilla |

### 认证服务

| 服务         | 端口      | 访问地址                       | 说明        |
|------------|---------|----------------------------|-----------|
| LDAP       | 389/636 | ldap://10.240.225.34:389   | 统一认证服务    |
| LDAP Admin | 6443    | https://10.240.225.34:6443 | LDAP 管理界面 |

## 服务凭证

### 数据库访问

```bash
# MariaDB Root 用户
主机: 10.240.225.34:3306
用户名: root
密码: Root_123456

# 应用数据库
主机: 10.240.225.34:3306
用户名: bugzilla
密码: Bugzilla_123456
数据库: bugzilla
```

### LDAP 认证

```bash
# LDAP 管理员
主机: ldaps://10.240.225.34:636
DN: cn=admin,dc=jiqid,dc=com
密码: secret

# LDAP 管理界面
URL: https://10.240.225.34:6443
登录: admin (LDAP 认证)
密码: secret
```

### 应用服务访问

```bash
# MinIO 对象存储
URL: http://10.240.225.34:9090
Access Key: root
Secret Key: Admin@123

# Bugzilla 管理
URL: http://10.240.225.34:8083/bugzilla/
邮箱: admin@jiqid.com
密码: Admin@123

# Jenkins 初始化
URL: http://10.240.225.34:8082/jenkins/
首次访问需要获取初始管理员密码
```

## 运维管理

### 服务启停命令

#### 启动服务

```bash
# 启动所有服务
docker-compose up -d

# 启动单个服务
docker-compose up -d mariadb
docker-compose up -d gerrit
docker-compose up -d jenkins
docker-compose up -d bugzilla
docker-compose up -d opengrok
docker-compose up -d minio
```

#### 停止服务

```bash
# 停止所有服务
docker-compose down

# 停止单个服务
docker-compose stop gerrit
docker-compose stop jenkins
```

#### 重启服务

```bash
# 重启所有服务
docker-compose restart

# 重启单个服务
docker-compose restart gerrit
```

### 查看服务状态

```bash
# 查看所有服务状态
docker-compose ps

# 查看服务日志
docker-compose logs -f

# 查看特定服务日志
docker-compose logs -f gerrit
docker-compose logs -f jenkins
docker-compose logs -f bugzilla
```

### 数据备份

#### 数据库备份

```bash
# 备份所有数据库
docker-compose exec mariadb mysqldump -u root -pRoot_123456 --all-databases > backup_$(date +%Y%m%d).sql

# 备份特定数据库
docker-compose exec mariadb mysqldump -u root -pRoot_123456 bugzilla > bugzilla_backup_$(date +%Y%m%d).sql
```

#### 配置文件备份

```bash
# 备份 Gerrit 配置
tar -czf gerrit_config_$(date +%Y%m%d).tar.gz /mnt/data/gerrit/

# 备份 Jenkins 配置
tar -czf jenkins_config_$(date +%Y%m%d).tar.gz /mnt/data/jenkins/

# 备份 Bugzilla 配置
tar -czf bugzilla_config_$(date +%Y%m%d).tar.gz /mnt/data/bugzilla/
```

## 故障排除

### 常见问题解决

#### 1. 端口被占用

```bash
# 检查端口占用情况
netstat -tulpn | grep :8081
netstat -tulpn | grep :8082

# 如果端口被占用，停止相关服务或修改端口
```

#### 2. 服务启动失败

```bash
# 查看服务详细日志
docker-compose logs gerrit
docker-compose logs jenkins

# 重新构建服务
docker-compose up -d --build gerrit
```

#### 3. 数据库连接问题

```bash
# 检查数据库服务状态
docker-compose exec mariadb mysqladmin ping

# 测试数据库连接
docker-compose exec mariadb mysql -u root -pRoot_123456 -e "SHOW DATABASES;"
```

#### 4. 磁盘空间不足

```bash
# 检查磁盘使用情况
df -h

# 清理 Docker 镜像
docker system prune -a

# 清理日志文件
sudo find /var/lib/docker/containers -name "*.log" -exec truncate -s 0 {} \;
```

### 服务健康检查

```bash
#!/bin/bash
# 创建健康检查脚本

echo "=== 检查服务状态 ==="
docker-compose ps

echo "=== 检查端口连通性 ==="
for port in 8081 8082 8083 8084 9090; do
    if nc -z localhost $port 2>/dev/null; then
        echo "Port $port: OK"
    else
        echo "Port $port: FAILED"
    fi
done

echo "=== 检查磁盘空间 ==="
df -h /mnt/data/

echo "=== 检查内存使用 ==="
free -h
```

## 开发工作流

### Gerrit 代码审查

```bash
# 克隆代码仓库
git clone ssh://guhua@10.240.225.34:29418/project

# 配置用户信息
git config user.name "Gu Hua"
git config user.email "guhua@jiqid.com"

# 提交代码审查
git commit -m "Fix bug in authentication module"
git push origin HEAD:refs/for/master

# 删除用户
curl -X DELETE --user "guhua@jiqid.com:123456" "http://10.240.225.34:8081/a/accounts/guhua@jiqid.com"
```

### Jenkins CI/CD

```bash
# 获取 Jenkins 初始管理员密码
docker-compose exec jenkins cat /var/jenkins_home/secrets/initialAdminPassword

# 访问 Jenkins Web 界面
# http://10.240.225.34:8082/jenkins/

# 创建新的 Pipeline 任务
# 配置 Git 仓库和构建脚本
```

### Bugzilla 问题跟踪

```bash
# 访问 Bugzilla 管理界面
# http://10.240.225.34:8083/bugzilla/

# 使用管理员账号登录
# 邮箱: admin@jiqid.com
# 密码: Admin@123

# 配置邮件通知
# 设置 SMTP 服务器和通知规则
```

## 技术支持

### 联系方式

- **技术支持**: guhua@jiqid.com
- **项目地址**: https://github.com/your-org/fbapy-devops

### 相关文档

- **Docker Compose**: https://docs.docker.com/compose/
- **Gerrit**: https://gerrit-review.googlesource.com/
- **Jenkins**: https://www.jenkins.io/doc/
- **Bugzilla**: https://www.bugzilla.org/docs/
- **OpenGrok**: https://github.com/oracle/opengrok/wiki
- **MinIO**: https://docs.min.io/

---

**版本**: 1.0.0
**最后更新**: 2025-11-26
**维护团队**: DevOps Team