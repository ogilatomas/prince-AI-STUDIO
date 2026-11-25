import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(title="Prince AI Studio API", version="0.1.0")

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
