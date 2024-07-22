FROM python:3.12-slim
ARG BRANCH_NAME=main
ENV BRANCH_NAME=${BRANCH_NAME}
ENV TINI_VERSION=v0.19.0
ARG CONFIG_DIR=/config
ENV CONFIG_DIR=/config

WORKDIR /app

COPY requirements.txt /

# install packages
RUN echo "**** install system packages ****" \
 && apt-get update \
 && apt-get install -y --no-install-recommends \
    git \
    bash \
    curl \
    wget \
    jq \
    grep \
    sed \
    coreutils \
    findutils \
    gcc \
    libffi-dev \
    rustc \
    cargo \
    tini \
 && pip3 install --no-cache-dir --upgrade pip \
 && pip3 install --no-cache-dir --upgrade --requirement /requirements.txt \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/* /requirements.txt /tmp/* /var/tmp/*

 COPY . .

VOLUME /config

EXPOSE 8000
ENTRYPOINT ["/sbin/tini", "-s", "/app/copy-config.sh", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
