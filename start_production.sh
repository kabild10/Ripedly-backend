#!/bin/bash

# Production startup script for Ripedly Backend
echo "🚀 Starting Ripedly Backend in Production Mode"

# Set environment variables
export FLASK_ENV=production
export PYTHONPATH=/app

# Create necessary directories
mkdir -p temp
mkdir -p logs

# Install/upgrade dependencies
echo "📦 Installing dependencies..."
pip install -r requirements.txt

# Start Gunicorn with configuration
echo "🔥 Starting Gunicorn server..."
gunicorn --config gunicorn.conf.py wsgi:application