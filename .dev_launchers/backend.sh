#!/usr/bin/env bash
trap 'echo; echo "[Backend exited with code $? — press enter to close]"; read' EXIT
cd "/c/Users/Work/documents/studie/intelligent_filter/building_planning_station/backend"
source "/c/Users/Work/documents/studie/intelligent_filter/building_planning_station/.venv/Scripts/activate"
echo "==> Starting FastAPI on http://localhost:8000"
python -m uvicorn app.main:app --reload --port 8000
