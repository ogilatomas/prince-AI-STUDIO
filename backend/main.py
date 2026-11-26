import json
import os
import re
import subprocess
import tempfile
import time
import urllib.error
import urllib.request

import imageio_ffmpeg
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

app = FastAPI(title="Prince AI Studio API", version="0.3.0")

# Allow the live Render website to call this API.
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

CF_ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID", "")
CF_API_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN", "")
CF_TEXT_MODEL = os.getenv("CF_TEXT_MODEL", "@cf/meta/llama-3.1-8b-instruct")
CF_BASE = "https://api.cloudflare.com/client/v4/accounts"
ALLOWED_CAMERA = ["zoom_in", "zoom_out", "pan_left", "pan_right"]


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
    # Validates the request only. Real generation is added in later steps.
    return {
        "status": "backend_connected",
        "message": "Your request reached the Prince AI Studio backend. Video generation is not connected yet.",
        "received": request.model_dump()
    }


@app.get("/api/ffmpeg-check")
def ffmpeg_check():
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


# ---------------------------------------------------------------
# Cloudflare Workers AI
# ---------------------------------------------------------------

def cloudflare_request(path: str, payload: dict = None, timeout: int = 60) -> dict:
    # Sends one request to Cloudflare. The token never leaves the server.
    if not CF_ACCOUNT_ID or not CF_API_TOKEN:
        raise HTTPException(
            status_code=500,
            detail="CLOUDFLARE_ACCOUNT_ID or CLOUDFLARE_API_TOKEN is missing on the server.",
        )
    url = f"{CF_BASE}/{CF_ACCOUNT_ID}/{path}"
    headers = {
        "Authorization": f"Bearer {CF_API_TOKEN}",
        "Content-Type": "application/json",
        "User-Agent": "PrinceAIStudio/0.3",
    }
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    method = "POST" if payload is not None else "GET"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


@app.get("/api/cloudflare-check")
def cloudflare_check():
    # Checks that the Account ID and token exist and work. It never shows them.
    if not CF_ACCOUNT_ID or not CF_API_TOKEN:
        return {
            "account_id_found": bool(CF_ACCOUNT_ID),
            "token_found": bool(CF_API_TOKEN),
            "message": "Add the missing value(s) on the Render Environment page."
        }
    try:
        data = cloudflare_request("ai/models/search?per_page=5")
        return {
            "account_id_found": True,
            "token_found": True,
            "key_works": bool(data.get("success")),
            "text_model_in_use": CF_TEXT_MODEL,
        }
    except urllib.error.HTTPError as error:
        return {"account_id_found": True, "token_found": True, "key_works": False, "http_status": error.code}
    except Exception as error:
        return {"account_id_found": True, "token_found": True, "key_works": False, "error": str(error)}


def extract_json(text: str) -> dict:
    text = text.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON found")
    return json.loads(text[start:end + 1])


def call_ai_for_json(instruction: str) -> dict:
    payload = {
        "messages": [
            {"role": "system", "content": "You are a professional short-video director. You reply with valid JSON only, no extra words."},
            {"role": "user", "content": instruction},
        ],
        "max_tokens": 3000,
        "temperature": 0.7,
    }
    last_problem = "unknown"

    for attempt in range(3):
        try:
            data = cloudflare_request(f"ai/run/{CF_TEXT_MODEL}", payload, timeout=90)
        except urllib.error.HTTPError as error:
            last_problem = f"error {error.code} for model {CF_TEXT_MODEL}"
            if error.code in (429, 500, 502, 503, 504):
                time.sleep(3)
                continue
            raise HTTPException(status_code=502, detail=f"Cloudflare AI returned {last_problem}.")
        except HTTPException:
            raise
        except Exception as error:
            last_problem = f"{error}"
            time.sleep(2)
            continue

        try:
            result = data["result"]
            if isinstance(result.get("response"), dict):
                return result["response"]
            if isinstance(result.get("response"), str):
                return extract_json(result["response"])
            return extract_json(result["choices"][0]["message"]["content"])
        except Exception:
            last_problem = "the AI answered, but not in the expected format"
            continue

    raise HTTPException(
        status_code=502,
        detail=f"Cloudflare AI is busy or unavailable. Last problem: {last_problem}. Please try again in a minute.",
    )


@app.post("/api/plan-scenes")
def plan_scenes(request: PrepareVideoRequest):
    scene_count = max(3, min(30, round(request.duration_seconds / 6)))
    no_narration = request.voice == "No narration"

    instruction = f"""
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
    plan = call_ai_for_json(instruction)

    scenes = plan.get("scenes")
    if not isinstance(scenes, list) or len(scenes) == 0:
        raise HTTPException(status_code=502, detail="The AI did not return any scenes. Please try again.")

    clean_scenes = []
    for number, scene in enumerate(scenes, start=1):
        camera = scene.get("camera", "zoom_in")
        try:
            seconds = float(scene.get("duration_seconds", 5))
        except (TypeError, ValueError):
            seconds = 5.0
        clean_scenes.append({
            "scene_number": number,
            "duration_seconds": max(seconds, 1.0),
            "narration": "" if no_narration else str(scene.get("narration", "")),
            "image_prompt": str(scene.get("image_prompt", "")),
            "camera": camera if camera in ALLOWED_CAMERA else "zoom_in",
        })

    # Make the scene lengths add up to the exact requested duration.
    total = sum(s["duration_seconds"] for s in clean_scenes)
    factor = request.duration_seconds / total
    for s in clean_scenes:
        s["duration_seconds"] = round(s["duration_seconds"] * factor, 1)

    return {
        "status": "scenes_planned",
        "engine": "cloudflare",
        "model": CF_TEXT_MODEL,
        "title": str(plan.get("title", "Untitled video")),
        "total_seconds": round(sum(s["duration_seconds"] for s in clean_scenes), 1),
        "scenes": clean_scenes,
    }


# ---------------------------------------------------------------
# Cloudflare image generation (scene pictures)
# ---------------------------------------------------------------
import base64
from fastapi import Response

CF_IMAGE_MODEL = os.getenv("CF_IMAGE_MODEL", "@cf/black-forest-labs/flux-1-schnell")


def generate_image_bytes(prompt: str) -> bytes:
    # Always ask for a picture without words, because AI image models spell badly.
    full_prompt = prompt[:1900] + ", no text, no letters, no words, no watermark"
    payload = {"prompt": full_prompt, "steps": 4}
    last_problem = "unknown"

    for attempt in range(3):
        try:
            data = cloudflare_request(f"ai/run/{CF_IMAGE_MODEL}", payload, timeout=90)
        except urllib.error.HTTPError as error:
            last_problem = f"error {error.code} for model {CF_IMAGE_MODEL}"
            if error.code in (429, 500, 502, 503, 504):
                time.sleep(3)
                continue
            raise HTTPException(status_code=502, detail=f"Cloudflare image AI returned {last_problem}.")
        except HTTPException:
            raise
        except Exception as error:
            last_problem = str(error)
            time.sleep(2)
            continue

        try:
            return base64.b64decode(data["result"]["image"])
        except Exception:
            last_problem = "the AI answered, but without a picture"
            continue

    raise HTTPException(
        status_code=502,
        detail=f"Image generation failed. Last problem: {last_problem}. Please try again in a minute.",
    )


@app.get("/api/image-test")
def image_test(prompt: str = "A lion walking through a golden savanna at sunset, cinematic lighting"):
    image = generate_image_bytes(prompt)
    media_type = "image/png" if image.startswith(b"\x89PNG") else "image/jpeg"
    return Response(content=image, media_type=media_type)


# ---------------------------------------------------------------
# First real scene clip: AI picture + slow camera zoom
# ---------------------------------------------------------------

@app.get("/api/scene-video-test")
def scene_video_test(prompt: str = "A lion walking through a golden savanna at sunset, cinematic lighting"):
    image = generate_image_bytes(prompt)

    folder = tempfile.mkdtemp()
    image_path = os.path.join(folder, "scene.jpg")
    video_path = os.path.join(folder, "scene.mp4")
    with open(image_path, "wb") as image_file:
        image_file.write(image)

    ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
    # Crop the picture to a tall 9:16 shape, then slowly zoom in for 5 seconds.
    video_filter = (
        "crop=ih*9/16:ih,scale=1080:1920,"
        "zoompan=z='min(zoom+0.0015,1.3)':d=125:"
        "x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=540x960:fps=25,"
        "format=yuv420p"
    )
    command = [
        ffmpeg_path, "-y", "-i", image_path,
        "-vf", video_filter,
        "-frames:v", "125",
        "-c:v", "libx264", "-preset", "ultrafast",
        video_path,
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="FFmpeg took too long.")

    if result.returncode != 0 or not os.path.exists(video_path):
        raise HTTPException(status_code=500, detail=f"FFmpeg failed: {result.stderr[-500:]}")

    return FileResponse(video_path, media_type="video/mp4", filename="scene_test.mp4")


# ---------------------------------------------------------------
# List the AI models available to your Cloudflare account
# ---------------------------------------------------------------
import urllib.parse


@app.get("/api/cloudflare-models")
def cloudflare_models(task: str = "Text-to-Speech"):
    try:
        data = cloudflare_request("ai/models/search?per_page=50&task=" + urllib.parse.quote(task))
    except urllib.error.HTTPError as error:
        return {"task": task, "ok": False, "http_status": error.code}
    except Exception as error:
        return {"task": task, "ok": False, "error": str(error)}

    names = [model.get("name") for model in data.get("result", [])]
    return {"task": task, "ok": True, "models": names}


# ---------------------------------------------------------------
# Cloudflare AI narration (text to speech)
# ---------------------------------------------------------------
CF_VOICE_MODEL = os.getenv("CF_VOICE_MODEL", "@cf/deepgram/aura-1")
ENGLISH_SPEAKERS = [
    "angus", "asteria", "arcas", "orion", "orpheus", "athena",
    "luna", "zeus", "perseus", "helios", "hera", "stella",
]


def cloudflare_raw_request(path: str, payload: dict, timeout: int = 90):
    # Like cloudflare_request, but returns the raw bytes and content type (for audio).
    if not CF_ACCOUNT_ID or not CF_API_TOKEN:
        raise HTTPException(
            status_code=500,
            detail="CLOUDFLARE_ACCOUNT_ID or CLOUDFLARE_API_TOKEN is missing on the server.",
        )
    url = f"{CF_BASE}/{CF_ACCOUNT_ID}/{path}"
    headers = {
        "Authorization": f"Bearer {CF_API_TOKEN}",
        "Content-Type": "application/json",
        "User-Agent": "PrinceAIStudio/0.3",
    }
    request = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST"
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read(), response.headers.get("Content-Type", "")


def generate_voice_bytes(text: str, speaker: str = "angus") -> bytes:
    if speaker not in ENGLISH_SPEAKERS:
        speaker = "angus"
    payload = {"text": text, "speaker": speaker, "encoding": "mp3"}
    last_problem = "unknown"

    for attempt in range(3):
        try:
            body, content_type = cloudflare_raw_request(f"ai/run/{CF_VOICE_MODEL}", payload)
        except urllib.error.HTTPError as error:
            last_problem = f"error {error.code} for model {CF_VOICE_MODEL}"
            if error.code in (429, 500, 502, 503, 504):
                time.sleep(3)
                continue
            raise HTTPException(status_code=502, detail=f"Cloudflare voice AI returned {last_problem}.")
        except HTTPException:
            raise
        except Exception as error:
            last_problem = str(error)
            time.sleep(2)
            continue

        if "json" in content_type.lower():
            try:
                data = json.loads(body.decode("utf-8"))
                audio_b64 = (data.get("result") or {}).get("audio") or data.get("audio")
                return base64.b64decode(audio_b64)
            except Exception:
                last_problem = "the AI answered with JSON, but without audio"
                continue
        if len(body) > 1000:
            return body
        last_problem = "the AI answered with an empty or very short audio file"

    raise HTTPException(
        status_code=502,
        detail=f"Voice generation failed. Last problem: {last_problem}. Please try again in a minute.",
    )


@app.get("/api/voice-test")
def voice_test(
    text: str = "Welcome to Prince AI Studio. This is a test of the AI narration.",
    speaker: str = "angus",
):
    # Short limit on purpose, to protect your free daily allowance while testing.
    audio = generate_voice_bytes(text[:300], speaker)
    return Response(content=audio, media_type="audio/mpeg")
