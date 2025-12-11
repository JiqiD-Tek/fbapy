FROM ubuntu:20.04

ENV DEBIAN_FRONTEND=noninteractive \
    TZ=Asia/Shanghai

# ---------------------
# 使用国内 APT 镜像
# ---------------------
RUN sed -i 's/archive.ubuntu.com/mirrors.ustc.edu.cn/g' /etc/apt/sources.list && \
    sed -i 's/security.ubuntu.com/mirrors.ustc.edu.cn/g' /etc/apt/sources.list

# ---------------------
# 基础依赖（基础编译工具、压缩与归档工具、网络和编辑器、内核/Android工具、Python、Java、SSH）
# ---------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc-multilib g++-multilib \
    libc6-dev-i386 lib32z1-dev lib32ncurses5-dev libncurses5-dev \
    flex bison \
    zip unzip tar cpio lz4 liblz4-dev liblz4-tool \
    curl wget git vim gnupg \
    zlib1g-dev libssl-dev libelf-dev device-tree-compiler dwarves bc \
    python3 python3-dev python3-pip python3-setuptools \
    python2.7 python2-dev \
    openjdk-8-jdk \
    openssh-server \
    && mkdir /var/run/sshd \
    && rm -rf /var/lib/apt/lists/*

# ---------------------
# 设置 root 密码（默认 root:root）
# ---------------------
RUN echo "root:root" | chpasswd

# ---------------------
# pip2 安装（手动）
# ---------------------
RUN curl -sSL https://bootstrap.pypa.io/pip/2.7/get-pip.py -o get-pip.py && \
    python2.7 get-pip.py && \
    pip2 install setuptools==44.1.1 wheel==0.34.2 && \
    rm get-pip.py

# ---------------------
# repo 工具（国内镜像）
# ---------------------
RUN wget -O /usr/local/bin/repo https://mirrors.tuna.tsinghua.edu.cn/git/git-repo \
    && chmod a+x /usr/local/bin/repo

# ---------------------
# Java 环境
# ---------------------
ENV JAVA_HOME=/usr/lib/jvm/java-8-openjdk-amd64
ENV PATH=$JAVA_HOME/bin:$PATH

# ---------------------
# Python 默认使用 python2.7
# ---------------------
RUN ln -sf /usr/bin/python2.7 /usr/bin/python

# ---------------------
# SSH 配置：允许 root 登录，跳过 PAM
# ---------------------
RUN sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config && \
    sed -i 's@session\s*required\s*pam_loginuid.so@#session required pam_loginuid.so@g' /etc/ssh/sshd_config

# ---------------------
# 工作目录
# ---------------------
WORKDIR /aosp

# ---------------------
# SSH 端口
# ---------------------
EXPOSE 22

# ---------------------
# 启动 SSH 并保持容器运行
# ---------------------
CMD ["/usr/sbin/sshd", "-D"]
