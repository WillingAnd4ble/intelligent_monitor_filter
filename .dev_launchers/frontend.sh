#!/usr/bin/env bash
trap 'echo; echo "[Frontend exited with code $? — press enter to close]"; read' EXIT
cd "/c/Users/Work/documents/studie/intelligent_filter/building_planning_station/web_ui"
echo "==> Starting Next.js dev server on http://localhost:3000"
npm run dev
