#!/bin/bash

echo "🚀 Starting Ripedly Backend in WebContainer Environment"

# Create necessary directories
mkdir -p temp
mkdir -p logs

# Install Python dependencies (if available)
echo "📦 Installing Python dependencies..."
if command -v python3 &> /dev/null; then
    python3 -m pip install --user -r requirements.txt 2>/dev/null || echo "⚠️ Python dependencies installation failed or not available"
else
    echo "⚠️ Python3 not available in WebContainer"
fi

# Install Node.js dependencies
echo "📦 Installing Node.js dependencies..."
npm install

# Start the Node.js server (which will proxy to Python if available)
echo "🔥 Starting Node.js server..."
npm run dev