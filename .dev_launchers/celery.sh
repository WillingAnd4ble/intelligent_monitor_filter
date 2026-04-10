#!/usr/bin/env bash
# Always pause on exit so we can read errors
trap 'echo; echo "[Celery exited with code $? — press enter to close]"; read' EXIT

cd "/c/Users/Work/Documents/Studie/Intelligent_filter/Building_planning_station/backend"
source "/c/Users/Work/Documents/Studie/Intelligent_filter/Building_planning_station/.venv/Scripts/activate"

# CRITICAL Windows fix: without this, Celery 5+ silently dies on Python 3.8+
# because billiard's spawn-based multiprocessing fails to reinitialize.
export FORKED_BY_MULTIPROCESSING=1

# Wait for Redis to be reachable (docker-compose may still be warming up)
echo "==> Waiting for Redis on localhost:6379..."
for i in {1..15}; do
    if (echo > /dev/tcp/localhost/6379) 2>/dev/null; then
        echo "    Redis is up."
        break
    fi
    if [[ $i -eq 15 ]]; then
        echo "    ERROR: Redis not reachable after 15s. Is docker-compose running?"
        exit 1
    fi
    sleep 1
done

echo "==> Starting Celery worker (solo pool for Windows)"
# Use 'python -m celery' instead of bare 'celery' — Git Bash can't execute
# the venv's entry-point wrapper script (no .exe extension), but python -m
# works identically on every platform.
python -m celery -A app.worker.celery_app worker --pool=solo --loglevel=info --concurrency=1
