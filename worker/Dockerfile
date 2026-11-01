FROM mcr.microsoft.com/playwright/python:v1.48.0-jammy
WORKDIR /app
COPY pyproject.toml sources.yaml ./
COPY openpath ./openpath
RUN pip install --no-cache-dir . && playwright install chromium
USER pwuser
CMD ["celery", "-A", "openpath.tasks", "worker", "--loglevel=INFO", "--concurrency=2"]
