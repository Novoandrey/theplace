FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Зависимости и проект ставятся из pyproject (точные пины там).
COPY . /app
RUN pip install --no-cache-dir . \
    && chmod +x docker-entrypoint.sh

ENTRYPOINT ["/app/docker-entrypoint.sh"]
# Phase 1 (T014) ставит сюда боевой запуск. compose в Фазе 0 переопределяет command.
CMD ["python", "-m", "src.bot"]
