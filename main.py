import json
import base64
import logging
from fastapi import FastAPI, UploadFile, File, Form, Request, HTTPException
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from config import Config, setup_logging
from services.asr_service import transcribe_audio
from services.llm_service import chat_with_llm
from services.tts_service import text_to_speech_stream
from database import engine, Base
from routers import auth_router, ws_router

# Setup
setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title="Voice Assistant API", version="1.0")

# Rate Limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Static & Templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Include Routers
app.include_router(auth_router.router, prefix="/auth", tags=["auth"])
app.include_router(ws_router.router, tags=["websocket"])

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/api/process_audio")
@limiter.limit("10/minute") # Rate limit
async def process_audio(
    request: Request,
    audio: UploadFile = File(...),
    history: str = Form("[]")
):
    # Input Validation
    if not audio.filename.endswith(('.webm', '.mp3', '.wav', '.ogg')):
         raise HTTPException(status_code=400, detail="Invalid file format. Supported formats: .webm, .mp3, .wav, .ogg")

    # 10MB limit (approx)
    audio_content = await audio.read()
    if len(audio_content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large. Max 10MB.")

    async def event_generator():
        # 1. ASR
        user_text = await transcribe_audio(audio_content)

        if not user_text:
            user_text = ""
            ai_text = "抱歉，我没有听清，请再说一遍。"
            # Send Metadata immediately
            yield json.dumps({
                "type": "meta",
                "user_text": user_text,
                "ai_text": ai_text
            }) + "\n"

            # Stream TTS for error message
            async for chunk in text_to_speech_stream(ai_text):
                 yield json.dumps({
                    "type": "audio",
                    "data": base64.b64encode(chunk).decode('utf-8')
                }) + "\n"
            return

        # 2. LLM
        try:
            history_list = json.loads(history)
        except:
            history_list = []

        ai_text = await chat_with_llm(user_text, history_list)

        # Send Metadata
        yield json.dumps({
            "type": "meta",
            "user_text": user_text,
            "ai_text": ai_text
        }) + "\n"

        # 3. TTS Streaming
        async for chunk in text_to_speech_stream(ai_text):
            yield json.dumps({
                "type": "audio",
                "data": base64.b64encode(chunk).decode('utf-8')
            }) + "\n"

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=Config.HOST, port=Config.PORT)
