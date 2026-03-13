#!/bin/bash

# GEM Portal Automation - Start Script
# Run this to start both backend and frontend

echo "🚀 Starting GEM Portal Automation..."
echo ""

# Kill any existing processes
pkill -f "uvicorn app.main:app" 2>/dev/null
pkill -f "next dev" 2>/dev/null

sleep 1

# Start Backend
echo "Starting Backend on port 8000..."
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
cd ..

# Wait for backend to start
sleep 3

# Start Frontend
echo "Starting Frontend on port 3000..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "✅ Application started!"
echo ""
echo "📊 Dashboard: http://localhost:3000"
echo "🔧 API Docs:  http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop both servers"

# Wait for both processes
wait $BACKEND_PID $FRONTEND_PID
