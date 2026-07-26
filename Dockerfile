FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt /app/requirements.txt
ARG PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple
RUN python -m pip install --no-cache-dir --upgrade pip \
        --index-url "$PIP_INDEX_URL" \
    && python -m pip install --no-cache-dir \
        --index-url "$PIP_INDEX_URL" \
        -r /app/requirements.txt

COPY . /app

EXPOSE 8000
