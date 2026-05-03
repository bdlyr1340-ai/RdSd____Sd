FROM python:3.11-slim

WORKDIR /app

# System libs required by Camoufox (Firefox) + Playwright Chromium + image rendering.
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget gnupg ca-certificates curl unzip xz-utils \
    fonts-liberation fonts-noto-color-emoji fonts-dejavu-core \
    libasound2 libatk-bridge2.0-0 libatk1.0-0 libatspi2.0-0 \
    libcups2 libdbus-1-3 libdrm2 libgbm1 libgtk-3-0 \
    libnspr4 libnss3 libwayland-client0 libxcomposite1 libxdamage1 \
    libxfixes3 libxkbcommon0 libxrandr2 xdg-utils libx11-xcb1 \
    libdbus-glib-1-2 libxt6 libpci3 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download Camoufox's anti-detection Firefox build (preferred).
RUN python -m camoufox fetch || echo "Camoufox fetch failed — will fall back to Playwright."

# Also download Chromium so Playwright works as a fallback engine.
RUN playwright install --with-deps chromium

COPY . .

RUN find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV HEADLESS=1
ENV BROWSER_ENGINE=auto

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD pgrep -f "python.*main" || exit 1

CMD ["python", "-m", "bot.main"]
