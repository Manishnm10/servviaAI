#!/bin/bash
echo "🏥 Starting ServVia on Port 8001..."
cd /Users/ayaanm/projects/DG_Open-SEVA/farmer-chat
source .myenv/bin/activate
export PYTHONWARNINGS="ignore"
echo "📱 Open: http://127.0.0.1:8001/"
python manage.py runserver 8001
