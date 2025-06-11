
import { useState } from 'react';
import Header from "./Header";
import Section from "./Section";
import { motion } from "framer-motion";

const YouTubeTrimmer = () => {
  const [url, setUrl] = useState("");
  const [videoId, setVideoId] = useState("");
  const [startTime, setStartTime] = useState("");
  const [endTime, setEndTime] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [showVideo, setShowVideo] = useState(false);
  const [progress, setProgress] = useState(0);
  const [statusMessage, setStatusMessage] = useState("");
  const [isLongWait, setIsLongWait] = useState(false);

  const BACKEND_URL = "https://e019527c-39c7-4ae5-a975-3183ed37f1eb-00-12fctld4jpitj.sisko.replit.dev";

  const validateYouTubeUrl = (url) => {
    if (!url) return "Please enter a URL";
    
    const regExp = /^(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})/;
    const match = url.match(regExp);
    
    if (!match || match[1].length !== 11) {
      return "Please enter a valid YouTube URL";
    }

    return true;
  };

  const handleUrlSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    
    const validation = validateYouTubeUrl(url);
    if (validation !== true) {
      setError(validation);
      return;
    }

    setIsLoading(true);

    try {
      const regExp = /^(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})/;
      const match = url.match(regExp);
      const id = match[1];
      
      setVideoId(id);
      setShowVideo(true);
      // setSuccess("Video loaded successfully!");

    } catch (err) {
      console.error('Error:', err);
      setError(err.message || 'Failed to load video. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleTrim = async (e) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    setIsLoading(true);
    setIsLongWait(false);
    setProgress(0);
    setStatusMessage("Initializing trim process...");

    try {
      // Stage 1: Backend health check (0-10%)
      setStatusMessage("Checking backend connection...");
      setProgress(5);
      
      console.log("Testing backend connection to:", BACKEND_URL);
      
      const healthCheck = await fetch(`${BACKEND_URL}/api/health`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        mode: 'cors'
      });
      
      console.log("Health check response:", healthCheck.status, healthCheck.ok);
      
      if (!healthCheck.ok) {
        throw new Error(`Backend unavailable (${healthCheck.status})`);
      }

      const healthData = await healthCheck.json();
      console.log("Backend health data:", healthData);
      
      setStatusMessage("Backend connected! Validating input...");
      setProgress(10);

      // Stage 2: Time validation (10-15%)
      setStatusMessage("Validating timestamps...");
      setProgress(15);
      if (!startTime || !endTime) {
        throw new Error('Start and end times are required');
      }

      // Stage 3: Preparing request (15-20%)
      setStatusMessage("Preparing trim request...");
      setProgress(20);

      // Stage 4: Sending request with wait indicators (20-30%)
      setStatusMessage("Processing your video...");
      setProgress(25);
      
      // Set up wait time indicators
      const waitTimer = setTimeout(() => {
        setIsLongWait(true);
        setStatusMessage("This may take a moment - processing video...");
      }, 10000); // Show after 10 seconds

      const veryLongWaitTimer = setTimeout(() => {
        setStatusMessage("Still processing... Almost done!");
      }, 30000); // Show after 30 seconds

      console.log("Sending trim request to:", `${BACKEND_URL}/api/trim`);
      
      const response = await fetch(`${BACKEND_URL}/api/trim`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        mode: 'cors',
        body: JSON.stringify({ 
          url,
          startTime,
          endTime 
        })
      });

      console.log("Trim response:", response.status, response.ok);

      // Clear timers
      clearTimeout(waitTimer);
      clearTimeout(veryLongWaitTimer);
      setIsLongWait(false);

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        console.error("Trim error response:", errorData);
        throw new Error(errorData.error || `Request failed (${response.status})`);
      }

      // Stage 5: Processing response (30-50%)
      setStatusMessage("Processing video data...");
      setProgress(50);

      // Stage 6: FFmpeg processing (50-90%)
      setStatusMessage("Trimming video content...");
      // Simulate progress during processing
      for (let i = 60; i <= 90; i += 10) {
        await new Promise(resolve => setTimeout(resolve, 500));
        setProgress(i);
      }

      // Stage 7: Finalizing (90-100%)
      setStatusMessage("Preparing your download...");
      setProgress(95);
      
      const blob = await response.blob();
      console.log("Downloaded blob size:", blob.size);
      
      if (blob.size < 1000) {
        throw new Error("Downloaded file appears to be invalid or too small");
      }
      
      setStatusMessage("Finalizing...");
      setProgress(100);
      
      const contentDisposition = response.headers.get('content-disposition');
      let filename = `Ripedly_${startTime.replace(/:/g, '_')}_to_${endTime.replace(/:/g, '_')}.mp4`;
      
      // If server provides a filename, use that instead
      if (contentDisposition) {
        const filenameMatch = contentDisposition.match(/filename="(.+?)"/);
        if (filenameMatch && filenameMatch[1]) {
          filename = filenameMatch[1];
        }
      }

      const downloadUrl = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = downloadUrl;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(downloadUrl);
      
      setStatusMessage("Download complete!");
      setSuccess(`Smooth cut! Like butter 🧈🍿`);

    } catch (err) {
      console.error('Trim error:', err);
      setError(`Connection failed: ${err.message}`);
      setProgress(0);
    } finally {
      setIsLoading(false);
      setIsLongWait(false);
      setStatusMessage("");
    }
  };

  const testConnection = async () => {
    try {
      console.log("Testing connection to:", BACKEND_URL);
      const response = await fetch(`${BACKEND_URL}/api/test-connection`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        mode: 'cors'
      });
      
      if (response.ok) {
        const data = await response.json();
        console.log("Connection test successful:", data);
        setSuccess("Backend connection test successful!");
      } else {
        console.error("Connection test failed:", response.status);
        setError(`Connection test failed (${response.status})`);
      }
    } catch (err) {
      console.error("Connection test error:", err);
      setError(`Connection test failed: ${err.message}`);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-900 via-blue-900 to-indigo-900">
      <Header />
      
      <main className="container mx-auto px-4 py-8">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="max-w-4xl mx-auto"
        >
          <div className="text-center mb-8">
            <h1 className="text-4xl md:text-6xl font-bold text-white mb-4">
              YouTube Trimmer
            </h1>
            <p className="text-xl text-gray-300">
              Trim YouTube videos with precision
            </p>
            <button
              onClick={testConnection}
              className="mt-4 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
            >
              Test Backend Connection
            </button>
          </div>

          <Section title="Enter YouTube URL">
            <form onSubmit={handleUrlSubmit} className="space-y-4">
              <div>
                <input
                  type="text"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="Paste YouTube URL here..."
                  className="w-full px-4 py-3 rounded-lg border border-gray-300 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  disabled={isLoading}
                />
              </div>
              <button
                type="submit"
                disabled={isLoading || !url}
                className="w-full bg-red-600 hover:bg-red-700 disabled:bg-gray-400 text-white font-bold py-3 px-6 rounded-lg transition-colors"
              >
                {isLoading ? "Loading..." : "Load Video"}
              </button>
            </form>
          </Section>

          {showVideo && videoId && (
            <Section title="Preview & Trim">
              <div className="space-y-6">
                <div className="aspect-video bg-black rounded-lg overflow-hidden">
                  <iframe
                    width="100%"
                    height="100%"
                    src={`https://www.youtube.com/embed/${videoId}`}
                    title="YouTube video player"
                    frameBorder="0"
                    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                    allowFullScreen
                  ></iframe>
                </div>

                <form onSubmit={handleTrim} className="space-y-4">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-300 mb-2">
                        Start Time (mm:ss or hh:mm:ss)
                      </label>
                      <input
                        type="text"
                        value={startTime}
                        onChange={(e) => setStartTime(e.target.value)}
                        placeholder="00:30"
                        className="w-full px-4 py-3 rounded-lg border border-gray-300 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                        disabled={isLoading}
                        pattern="^(\d{1,2}:\d{2}(:\d{2})?)$"
                        title="Format: mm:ss or hh:mm:ss"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-300 mb-2">
                        End Time (mm:ss or hh:mm:ss)
                      </label>
                      <input
                        type="text"
                        value={endTime}
                        onChange={(e) => setEndTime(e.target.value)}
                        placeholder="01:30"
                        className="w-full px-4 py-3 rounded-lg border border-gray-300 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                        disabled={isLoading}
                        pattern="^(\d{1,2}:\d{2}(:\d{2})?)$"
                        title="Format: mm:ss or hh:mm:ss"
                      />
                    </div>
                  </div>

                  {isLoading && (
                    <div className="space-y-4">
                      <div className="bg-gray-200 rounded-full h-2">
                        <div
                          className="bg-blue-600 h-2 rounded-full transition-all duration-500"
                          style={{ width: `${progress}%` }}
                        ></div>
                      </div>
                      <p className="text-center text-gray-300">
                        {statusMessage} {progress > 0 && `(${progress}%)`}
                      </p>
                      {isLongWait && (
                        <div className="text-center">
                          <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
                          <p className="text-sm text-gray-400 mt-2">
                            Processing large video files can take some time...
                          </p>
                        </div>
                      )}
                    </div>
                  )}

                  <button
                    type="submit"
                    disabled={isLoading || !startTime || !endTime}
                    className="w-full bg-green-600 hover:bg-green-700 disabled:bg-gray-400 text-white font-bold py-3 px-6 rounded-lg transition-colors"
                  >
                    {isLoading ? "Processing..." : "Trim & Download"}
                  </button>
                </form>
              </div>
            </Section>
          )}

          {error && (
            <div className="mt-4 p-4 bg-red-100 border border-red-400 text-red-700 rounded-lg">
              <p className="font-semibold">Error:</p>
              <p>{error}</p>
              <details className="mt-2">
                <summary className="cursor-pointer text-sm">Troubleshooting</summary>
                <div className="mt-2 text-sm space-y-1">
                  <p>• Check that the backend is running</p>
                  <p>• Verify the YouTube URL is valid</p>
                  <p>• Ensure times are in correct format (mm:ss or hh:mm:ss)</p>
                  <p>• Try refreshing the page</p>
                </div>
              </details>
            </div>
          )}

          {success && (
            <div className="mt-4 p-4 bg-green-100 border border-green-400 text-green-700 rounded-lg">
              <p className="font-semibold">Success!</p>
              <p>{success}</p>
            </div>
          )}
        </motion.div>
      </main>
    </div>
  );
};

export default YouTubeTrimmer;
