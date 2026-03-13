#!/bin/bash

# Navigate to project directory
cd ~/projects/DG_Open-SEVA/farmer-chat

# Activate virtual environment
source .myenv/bin/activate

# Start Django server in background
echo "🚀 Starting MediCare Assistant server..."
python3 manage.py runserver > /dev/null 2>&1 &

# Store the server process ID
SERVER_PID=$!
echo "✅ Server started with PID: $SERVER_PID"

# Wait for server to start
echo "⏳ Waiting for server to initialize..."
sleep 3

# Open the webpage in browser
echo "🌐 Opening MediCare Assistant in browser..."
open file:///Users/ayaanm/projects/DG_Open-SEVA/farmer-chat/index.html

echo "✨ MediCare Assistant is ready!"
echo "📍 Server running at: http://127.0.0.1:8000/"
echo "🛑 To stop server, run: kill $SERVER_PID"
