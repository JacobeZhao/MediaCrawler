# MediaCrawler — Docker image
# Supports: arm64 (Apple Silicon Mac Mini) and amd64
# Python 3.11 slim base with Playwright Chromium

FROM python:3.11-slim

# ── 系统依赖（Playwright Chromium on Debian Bookworm arm64/amd64）──
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl wget ca-certificates gnupg \
    # Chromium 运行时依赖
    libnss3 libnspr4 \
    libdbus-1-3 \
    libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 libcairo2 \
    libx11-6 libxext6 libxrender1 \
    # 中文字体（防止截图乱码）
    fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Python 依赖（先 copy requirements 利用 layer 缓存）──
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── 安装 Playwright Chromium（arm64 原生支持）──
RUN playwright install chromium

# ── 应用代码 ──
COPY . .

# 数据目录
RUN mkdir -p /app/data /app/browser_data

EXPOSE 8080

# 启动 FastAPI
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
