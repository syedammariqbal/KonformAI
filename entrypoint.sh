#!/bin/bash
set -e

echo "=== Initializing KonformAI Knowledge Base & DB ==="
python scripts/ingest_kb.py || echo "Warning: KB ingestion encountered non-fatal notice, continuing..."
python scripts/seed_demo_data.py || echo "Warning: Demo data already seeded, continuing..."

echo "=== Starting FastAPI Backend on :8000 ==="
uvicorn backend.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

echo "=== Starting Streamlit Frontend on :8501 ==="
streamlit run frontend/streamlit_app.py --server.port 8501 --server.address 0.0.0.0 &
FRONTEND_PID=$!

# Trap signals and terminate both background services gracefully
trap "kill $BACKEND_PID $FRONTEND_PID" SIGINT SIGTERM

# Wait for both processes
wait $BACKEND_PID $FRONTEND_PID
