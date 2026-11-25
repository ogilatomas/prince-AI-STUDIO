PRINCE AI STUDIO - PYTHON BACKEND STARTER

This is the first backend milestone. It provides:
- GET /health to check whether the API is online
- POST /api/prepare-video to validate and receive a video request
- CORS configured for https://prince-ai-studio.onrender.com

IMPORTANT:
This starter does NOT generate videos yet. It does not call an AI provider,
create images, synthesize speech, or run FFmpeg. Those will be added in later
steps after the backend is deployed and tested.

ADD TO YOUR EXISTING GITHUB REPOSITORY:
1. Open your prince-AI-STUDIO repository.
2. Create a folder named backend.
3. Add main.py, requirements.txt, and README.txt inside backend.

RENDER BACKEND SERVICE SETTINGS:
- New + > Web Service
- Connect the same GitHub repository
- Root Directory: backend
- Runtime: Python 3
- Build Command: pip install -r requirements.txt
- Start Command: uvicorn main:app --host 0.0.0.0 --port $PORT
- Environment variable:
  FRONTEND_ORIGIN = https://prince-ai-studio.onrender.com

After deployment, test:
https://YOUR-BACKEND-URL.onrender.com/health
Expected response: {"status":"ok"}

Do not add API keys yet. Never put secret API keys in frontend files or GitHub.
