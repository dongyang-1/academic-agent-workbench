# 学术全流程智能体 · 云端部署镜像
# 构建：docker build -t aca-web .
# 运行：docker run -d -p 8088:8088 --env-file .env aca-web

FROM python:3.12-slim

# 系统依赖：matplotlib 中文字体 + 编译类依赖的兜底
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=Asia/Shanghai

RUN apt-get update && apt-get install -y --no-install-recommends \
        fonts-noto-cjk \
        tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先装依赖（利用构建缓存：改代码不会重装依赖）
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir python-docx

# 再拷代码
COPY . /app

# 运行期需要可写的目录（SQLite 状态库 / 上传数据 / 产出物）
RUN mkdir -p /app/data \
             /app/part2-empirical-research/data/uploads \
             /app/part2-empirical-research/data/library_uploads \
             /app/part2-empirical-research/deliverables

EXPOSE 8088

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8088/api/health', timeout=4)"

# 单进程即可（计量内核是 CPU 密集），如需并发可调 --workers
CMD ["python", "-m", "uvicorn", "web_platform.app:app", \
     "--host", "0.0.0.0", "--port", "8088", "--log-level", "warning"]
