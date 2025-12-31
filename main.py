import json
import base64
import logging
from fastapi import FastAPI, UploadFile, File, Form, Request, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from config import Config, setup_logging
from services.asr_service import transcribe_audio
from services.llm_service import chat_with_llm
from services.tts_service import text_to_speech_stream
from services.auth_service import verify_password, get_password_hash, create_access_token, decode_access_token, ACCESS_TOKEN_EXPIRE_MINUTES
from services.audio_service import process_audio_data
from database import get_db
from models import User, ChatHistory
from datetime import timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

# Setup
setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title="Voice Assistant API", version="1.0")

# Rate Limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Auth
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/token")

async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    username = payload.get("sub")
    if username is None:
         raise HTTPException(status_code=401, detail="Invalid token")

    result = await db.execute(select(User).where(User.username == username))
    user = result.scalars().first()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user

# Pydantic models for Auth
class UserCreate(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

@app.post("/api/auth/register", response_model=Token)
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    # Check existing
    result = await db.execute(select(User).where(User.username == user_data.username))
    existing_user = result.scalars().first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already registered")

    hashed_pw = get_password_hash(user_data.password)
    new_user = User(username=user_data.username, hashed_password=hashed_pw)
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": new_user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/api/auth/token", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == form_data.username))
    user = result.scalars().first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

from prometheus_fastapi_instrumentator import Instrumentator

# Instrumentation
Instrumentator().instrument(app).expose(app)

# Static & Templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

async def save_message(db: AsyncSession, user_id: int, role: str, content: str):
    msg = ChatHistory(user_id=user_id, role=role, content=content)
    db.add(msg)
    await db.commit()

async def process_chat_logic(user_text: str, history_list: list, voice_id: str, temperature: float, db: AsyncSession, user: User):
    # Save User Message
    await save_message(db, user.id, "user", user_text)

    # LLM
    ai_text = await chat_with_llm(user_text, history_list, temperature=temperature)

    # Save AI Message
    await save_message(db, user.id, "assistant", ai_text)

    # Yield Metadata
    yield json.dumps({
        "type": "meta",
        "user_text": user_text,
        "ai_text": ai_text
    }) + "\n"

    # Stream TTS
    async for chunk in text_to_speech_stream(ai_text, voice_id=voice_id):
        yield json.dumps({
            "type": "audio",
            "data": base64.b64encode(chunk).decode('utf-8')
        }) + "\n"

@app.post("/api/process_audio")
@limiter.limit("10/minute")
async def process_audio(
    request: Request,
    audio: UploadFile = File(...),
    history: str = Form("[]"),
    voice_id: str = Form("female-shaonv"),
    temperature: float = Form(0.7),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if not audio.filename.endswith(('.webm', '.mp3', '.wav', '.ogg')):
         raise HTTPException(status_code=400, detail="Invalid file format.")

    audio_content = await audio.read()
    if len(audio_content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large.")

    # Audio Preprocessing
    processed_audio = process_audio_data(audio_content)

    async def event_generator():
        # ASR
        user_text = await transcribe_audio(processed_audio)

        if not user_text:
            yield json.dumps({
                "type": "meta",
                "user_text": "",
                "ai_text": "抱歉，我没有听清，请再说一遍。"
            }) + "\n"
            return

        try:
            history_list = json.loads(history)
        except:
            history_list = []

        async for chunk in process_chat_logic(user_text, history_list, voice_id, temperature, db, current_user):
            yield chunk

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")

class TextChatRequest(BaseModel):
    text: str
    history: list = []
    voice_id: str = "female-shaonv"
    temperature: float = 0.7

@app.post("/api/process_text")
@limiter.limit("20/minute")
async def process_text(
    request: Request,
    payload: TextChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    async def event_generator():
        async for chunk in process_chat_logic(payload.text, payload.history, payload.voice_id, payload.temperature, db, current_user):
            yield chunk

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=Config.HOST, port=Config.PORT)
