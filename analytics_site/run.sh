#!/bin/bash
# Script to run the analytics server
# It runs on port 8001 to avoid conflict with rate_my_course (usually 8000)

cd "$(dirname "$0")"

# Check if venv exists, if not create it
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
    source .venv/bin/activate
    echo "Installing requirements..."
    pip install -r requirements.txt
else
    source .venv/bin/activate
fi

echo "Starting Analytics Server on http://0.0.0.0:5270"
uvicorn main:app --host 0.0.0.0 --port 5270

