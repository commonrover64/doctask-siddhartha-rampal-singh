#!/bin/bash
set -e

echo "== Loan File Intelligence System setup =="

if [ ! -f backend/.env ]; then
  echo "ERROR: backend/.env not found. Copy backend/.env.example to backend/.env"
  echo "and fill in GROQ_API_KEY (from console.groq.com) first."
  exit 1
fi

if [ ! -f frontend/.env ]; then
  echo "ERROR: frontend/.env not found. Copy frontend/.env.example to frontend/.env first."
  exit 1
fi

echo "-- Starting Postgres --"
docker compose up -d postgres
until docker compose exec -T postgres pg_isready -U loanfile > /dev/null 2>&1; do
  sleep 1  # waits for Postgres to actually accept connections, not just for the container to start
done
docker compose exec -T postgres psql -U loanfile -d loanfile -c "CREATE EXTENSION IF NOT EXISTS vector;"

echo "-- Setting up backend --"
cd backend
python3 -m venv venv
source venv/bin/activate
mkdir watched_incoming
pip install -r requirements.txt --quiet
python -m app.migrate

echo "-- Setting up frontend --"
cd ../frontend
npm install --silent

echo "-- Starting both servers --"
cd ../backend
source venv/bin/activate
uvicorn app.main:app --reload &
BACKEND_PID=$!

cd ../frontend
npm run dev &
FRONTEND_PID=$!

echo ""
echo "Backend:  http://127.0.0.1:8000/docs"
echo "Frontend: http://localhost:5173"
echo ""
echo "Press Ctrl+C to stop both (Postgres container keeps running, docker compose down to stop it)."

trap "kill $BACKEND_PID $FRONTEND_PID" EXIT
wait