const express = require('express');
const cors = require('cors');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

const app = express();
const PORT = process.env.PORT || 5000;

// Middleware
app.use(cors());
app.use(express.json());

// Health check endpoint
app.get('/api/health', (req, res) => {
  res.json({
    status: 'ok',
    message: 'Ripedly Backend is running',
    timestamp: new Date().toISOString()
  });
});

// Proxy endpoint for video trimming
app.post('/api/trim', async (req, res) => {
  console.log('🔧 /api/trim called via Node.js proxy');
  
  try {
    // Start Python Flask server if not running
    const pythonProcess = spawn('python3', ['app.py'], {
      stdio: 'pipe',
      cwd: __dirname
    });

    // Wait a moment for Python server to start
    await new Promise(resolve => setTimeout(resolve, 2000));

    // Forward request to Python Flask server
    const axios = require('axios');
    
    try {
      const response = await axios.post('http://localhost:5001/api/trim', req.body, {
        timeout: 600000, // 10 minutes
        responseType: 'stream'
      });

      // Forward the response
      response.data.pipe(res);
      
    } catch (error) {
      console.error('Error forwarding to Python server:', error.message);
      res.status(500).json({ 
        error: 'Failed to process video',
        details: error.message 
      });
    }

  } catch (error) {
    console.error('Error in trim endpoint:', error);
    res.status(500).json({ 
      error: 'Internal server error',
      details: error.message 
    });
  }
});

// Serve static files from temp directory
app.use('/temp', express.static(path.join(__dirname, 'temp')));

// Start server
app.listen(PORT, '0.0.0.0', () => {
  console.log(`🚀 Ripedly Backend running on http://localhost:${PORT}`);
  console.log('✨ Node.js proxy server with Python Flask backend');
  
  // Create temp directory if it doesn't exist
  const tempDir = path.join(__dirname, 'temp');
  if (!fs.existsSync(tempDir)) {
    fs.mkdirSync(tempDir, { recursive: true });
    console.log('📁 Created temp directory');
  }
});

// Graceful shutdown
process.on('SIGTERM', () => {
  console.log('🛑 Received SIGTERM, shutting down gracefully');
  process.exit(0);
});

process.on('SIGINT', () => {
  console.log('🛑 Received SIGINT, shutting down gracefully');
  process.exit(0);
});