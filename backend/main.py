import os
import subprocess
import tempfile

import imageio_ffmpeg
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

app = FastAPI(title="Prince AI Studio API", version="0.2.0")

# Allow the live Render website to call this API.
# Add your exact frontend URL to FRONTEND_ORIGIN in Render environment variables
# if you later change the website address.
frontend_origin = os.getenv(
    "FRONTEND_ORIGIN",
    "https://prince-ai-studio.onrender.com"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_origin],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


class PrepareVideoRequest(BaseModel):
    prompt: str = Field(min_length=5, max_length=5000)
    style: str = "Cinematic"
    aspect_ratio: str = "9:16"
    duration_seconds: int = Field(default=60, ge=15, le=180)
    voice: str = "Natural voice"
    audio: str = "Voice + music + sound effects"


@app.get("/")
def root():
    return {
        "name": "Prince AI Studio API",
        "status": "running",
        "message": "Backend is online. AI generation is not connected yet."
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/prepare-video")
def prepare_video(request: PrepareVideoRequest):
    # This endpoint validates the request only.
    # A real job queue and AI/video providers will be connected in later steps.
    return {
        "status": "backend_connected",
        "message": "Your request reached the Prince AI Studio backend. Video generation is not connected yet.",
        "received": request.model_dump()
    }


@app.get("/api/ffmpeg-check")
def ffmpeg_check():
    # Tells us whether FFmpeg is available on this server.
    try:
        ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
        result = subprocess.run(
            [ffmpeg_path, "-version"],
            capture_output=True, text=True, timeout=30
        )
        first_line = result.stdout.splitlines()[0] if result.stdout else "unknown"
        return {"ffmpeg_available": True, "version": first_line}
    except Exception as error:
        return {"ffmpeg_available": False, "error": str(error)}


@app.get("/api/ffmpeg-test")
def ffmpeg_test():
    # Makes a 5-second test video with FFmpeg so we can prove the server can create videos.
    try:
        ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"FFmpeg not found: {error}")

    output_path = os.path.join(tempfile.gettempdir(), "prince_test.mp4")
    command = [
        ffmpeg_path, "-y",
        "-f", "lavfi", "-i", "testsrc2=size=360x640:rate=24",
        "-t", "5",
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        output_path,
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=90)
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="FFmpeg took too long.")

    if result.returncode != 0 or not os.path.exists(output_path):
        raise HTTPException(status_code=500, detail=f"FFmpeg failed: {result.stderr[-500:]}")

    return FileResponse(output_path, media_type="video/mp4", filename="prince_test.mp4")
