#!/usr/bin/env sh
# Миграции на старте, затем команда сервиса (конституция §3, plan §12).
# Сейчас ревизий нет (T009 ещё впереди) — `alembic upgrade head` это no-op.
set -e

echo "[entrypoint] alembic upgrade head"
alembic upgrade head

exec "$@"
