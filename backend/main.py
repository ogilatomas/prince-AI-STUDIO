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


import json
import urllib.request
import urllib.error


@app.get("/api/gemini-check")
def gemini_check():
    # Checks that the secret key exists and works. It never shows the key.
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        return {
            "key_found": False,
            "message": "GEMINI_API_KEY was not found. Check the Environment page on Render."
        }

    request = urllib.request.Request(
        "https://generativelanguage.googleapis.com/v1beta/models?pageSize=100",
        headers={"x-goog-api-key": key},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        return {"key_found": True, "key_works": False, "http_status": error.code}
    except Exception as error:
        return {"key_found": True, "key_works": False, "error": str(error)}

    names = []
    for model in data.get("models", []):
        methods = model.get("supportedGenerationMethods", [])
        name = model.get("name", "")
        if "generateContent" in methods and "flash" in name:
            names.append(name.replace("models/", ""))

    return {"key_found": True, "key_works": True, "flash_models": names[:15]}


import re

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
ALLOWED_CAMERA = ["zoom_in", "zoom_out", "pan_left", "pan_right"]


def call_gemini_for_json(instruction: str) -> dict:
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY is missing on the server.")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
    body = json.dumps({
        "contents": [{"parts": [{"text": instruction}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.8},
    }).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"x-goog-api-key": key, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        if error.code == 429:
            raise HTTPException(status_code=429, detail="The free AI limit was reached. Please wait a while and try again.")
        raise HTTPException(status_code=502, detail=f"Gemini returned error {error.code} for model {GEMINI_MODEL}.")
    except Exception as error:
        raise HTTPException(status_code=502, detail=f"Could not reach Gemini: {error}")

    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
        return json.loads(text)
    except Exception:
        raise HTTPException(status_code=502, detail="Gemini answered, but not in the format we expected. Please try again.")


@app.post("/api/plan-scenes")
def plan_scenes(request: PrepareVideoRequest):
    scene_count = max(3, min(30, round(request.duration_seconds / 6)))
    no_narration = request.voice == "No narration"

    instruction = f"""
You are a professional short-video director.
Plan a video of exactly {request.duration_seconds} seconds with exactly {scene_count} scenes.

Video idea: {request.prompt}
Visual style: {request.style}
Aspect ratio: {request.aspect_ratio}
Narration voice style: {request.voice}

Rules:
- Write the narration in the same language as the video idea.
- Narration must be honest and not misleading. Do not invent fake facts.
- Each scene's narration must be short enough to speak within that scene's duration (about 2 words per second).
- {"Leave narration as an empty string because there is no narration." if no_narration else "Every scene needs narration."}
- image_prompt must be a detailed English description of ONE still picture for that scene, matching the visual style. Do not include text or words inside the picture.
- camera must be one of: {", ".join(ALLOWED_CAMERA)}.
- The scene durations must add up to {request.duration_seconds} seconds.

Return ONLY JSON in exactly this shape:
{{"title": "short video title", "scenes": [{{"scene_number": 1, "duration_seconds": 5, "narration": "text", "image_prompt": "description", "camera": "zoom_in"}}]}}
"""
    plan = call_gemini_for_json(instruction)

    scenes = plan.get("scenes")
    if not isinstance(scenes, list) or len(scenes) == 0:
        raise HTTPException(status_code=502, detail="The AI did not return any scenes. Please try again.")

    clean_scenes = []
    for number, scene in enumerate(scenes, start=1):
        camera = scene.get("camera", "zoom_in")
        clean_scenes.append({
            "scene_number": number,
            "duration_seconds": float(scene.get("duration_seconds", 5)),
            "narration": "" if no_narration else str(scene.get("narration", "")),
            "image_prompt": str(scene.get("image_prompt", "")),
            "camera": camera if camera in ALLOWED_CAMERA else "zoom_in",
        })

    return {
        "status": "scenes_planned",
        "model": GEMINI_MODEL,
        "title": str(plan.get("title", "Untitled video")),
        "total_seconds": sum(s["duration_seconds"] for s in clean_scenes),
        "scenes": clean_scenes,
    }


import time

FALLBACK_MODELS = ["gemini-3.5-flash", "gemini-3.5-flash-lite"]


def call_gemini_for_json(instruction: str) -> dict:
    # This newer version replaces the older one above. It retries when Google is busy
    # and switches to backup models if needed.
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY is missing on the server.")

    body = json.dumps({
        "contents": [{"parts": [{"text": instruction}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.8},
    }).encode("utf-8")

    models_to_try = [GEMINI_MODEL] + [m for m in FALLBACK_MODELS if m != GEMINI_MODEL]
    last_problem = "unknown"

    for model_name in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
        for attempt in range(2):
            request = urllib.request.Request(
                url,
                data=body,
                headers={"x-goog-api-key": key, "Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(request, timeout=40) as response:
                    data = json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as error:
                last_problem = f"error {error.code} for model {model_name}"
                if error.code in (429, 500, 503):
                    time.sleep(3)
                    continue
                break
            except Exception as error:
                last_problem = f"{error} for model {model_name}"
                time.sleep(2)
                continue

            try:
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
                return json.loads(text)
            except Exception:
                last_problem = f"unexpected answer format from model {model_name}"
                break

    raise HTTPException(
        status_code=502,
        detail=f"Gemini is busy or unavailable right now. Last problem: {last_problem}. Please try again in a minute.",
    )
