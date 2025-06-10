#!/bin/bash

# Development startup script for Ripedly Backend
echo "🚀 Starting Ripedly Backend in Development Mode"

# Set environment variables
export FLASK_ENV=development
export ENABLE_UPDATER=true

# Create necessary directories
mkdir -p temp

# Install/upgrade dependencies
echo "📦 Installing dependencies..."
pip install -r requirements.txt

# Start Flask development server
echo "🔥 Starting Flask development server..."
python app.py