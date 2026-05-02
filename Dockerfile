FROM python:3.11-slim

WORKDIR /app

# System libs required by Playwright Chromium + image rendering.
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget gnupg ca-certificates curl \
    fonts-liberation fonts-noto-color-emoji fonts-dejavu-core \
    libasound2 libatk-bridge2.0-0 libatk1.0-0 libatspi2.0-0 \
    libcups2 libdbus-1-3 libdrm2 libgbm1 libgtk-3-0 \
    libnspr4 libnss3 libwayland-client0 libxcomposite1 libxdamage1 \
    libxfixes3 libxkbcommon0 libxrandr2 xdg-utils libx11-xcb1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download Chromium for Playwright (REQUIRED).
RUN playwright install --with-deps chromium

COPY . .

RUN find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV HEADLESS=1

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD pgrep -f "python.*main" || exit 1

CMD ["python", "-m", "bot.main"]
