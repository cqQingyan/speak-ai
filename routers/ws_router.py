import logging
import asyncio
import json
import base64
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from auth import verify_token
from services.volcengine_asr import VolcengineASRService
from services.llm_service import chat_with_llm
from services.tts_service import text_to_speech_stream
from redis.asyncio import Redis
from config import settings
import time

logger = logging.getLogger(__name__)
router = APIRouter()
redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True)

# Rate Limits (Simple Redis Implementation)
# 60 requests per minute per user
RATE_LIMIT = 60
RATE_WINDOW = 60

async def check_rate_limit(user: str):
    key = f"rate_limit:{user}"
    async with redis_client.pipeline(transaction=True) as pipe:
        # Increase and Expire in one transaction-like block (though WATCH/MULTI is real transaction)
        # For rate limit, we just need basic atomicity or at least expiry set
        await pipe.incr(key)
        await pipe.expire(key, RATE_WINDOW, nx=True) # Set expire only if not exists (nx=True for expire is Redis 7.0+, but we use pydantic-redis)
        # Actually 'nx' for expire might not be supported by all redis versions or clients easily.
        # Standard pattern:
        # INCR
        # TTL -> if -1, EXPIRE

        # Simpler robust pipeline:
        # INCR
        # EXPIRE (always reset? No, that extends window).

        # Correct atomic Lua script is best, but Python logical check:
        # 1. INCR
        # 2. If result == 1, EXPIRE

        # But doing it in pipeline:
        # pipe.incr()
        # pipe.ttl()
        # res = execute()
        # if ttl == -1: expire...
        # But that's 2 round trips if we react.

        # Let's stick to the previous logic but use pipeline to ensure connection reuse/grouping
        # The race condition is: INCR happens, script crashes, Key has no TTL -> persists forever.

        await pipe.incr(key)
        # We can unconditionally set expire if we want sliding window (not fixed window), but here we want fixed window starting at 1st req.
        # But safely ensuring cleanup:
        # If we just do:
        # pipe.incr()
        # pipe.expire(key, RATE_WINDOW, nx=True) -- if supported.

        # If nx not supported, we can use Lua.
        pass

    # Let's use a simpler safe approach:
    # Always expire? No.

    # Using Lua script for atomic fixed window
    lua_script = """
    local current = redis.call("INCR", KEYS[1])
    if current == 1 then
        redis.call("EXPIRE", KEYS[1], ARGV[1])
    end
    return current
    """
    current = await redis_client.eval(lua_script, 1, key, RATE_WINDOW)

    if current > RATE_LIMIT:
        return False
    return True

@router.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket, token: str = None):
    # Verify Token
    if not token:
        token = websocket.query_params.get("token")

    user = verify_token(token)
    if not user:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    # Check Rate Limit
    if not await check_rate_limit(user):
        await websocket.close(code=4008, reason="Rate Limit Exceeded")
        return

    await websocket.accept()
    logger.info(f"WebSocket connected: {user}")

    asr_service = VolcengineASRService()

    # Queues
    audio_queue = asyncio.Queue()

    # Max Audio Size in one Session (e.g. 50MB) for safety
    TOTAL_AUDIO_LIMIT = 50 * 1024 * 1024
    received_bytes = 0

    async def receive_audio_from_client():
        nonlocal received_bytes
        try:
            while True:
                data = await websocket.receive()

                if "bytes" in data:
                    chunk_size = len(data["bytes"])

                    # Size Check
                    if chunk_size > 2 * 1024 * 1024: # 2MB chunk limit
                        logger.warning(f"Audio chunk too large from {user}")
                        continue

                    received_bytes += chunk_size
                    if received_bytes > TOTAL_AUDIO_LIMIT:
                        logger.warning(f"Total audio limit exceeded for {user}")
                        await websocket.send_json({"type": "error", "message": "Session limit reached. Please reconnect."})
                        await audio_queue.put(None)
                        break

                    await audio_queue.put(data["bytes"])

                elif "text" in data:
                    try:
                        msg = json.loads(data["text"])
                        if msg.get("action") == "finish_speaking":
                             await audio_queue.put(None)
                    except:
                        pass
        except WebSocketDisconnect:
            logger.info("Client disconnected")
            await audio_queue.put(None)
        except Exception as e:
            logger.error(f"Receive Error: {e}")
            await audio_queue.put(None)

    async def pipeline_worker():
        while True:
            chunk = await audio_queue.get()
            if chunk is None:
                if audio_queue.empty():
                     break
                else:
                     continue

            async def single_turn_gen(first_chunk):
                yield first_chunk
                while True:
                    c = await audio_queue.get()
                    if c is None:
                        break
                    yield c

            # 1. ASR
            user_text = ""
            try:
                async for asr_result in asr_service.transcribe_stream(single_turn_gen(chunk)):
                    if asr_result["type"] == "error":
                        await websocket.send_json({"type": "error", "message": asr_result["text"]})
                        break

                    if asr_result["type"] == "partial":
                         await websocket.send_json({"type": "asr_partial", "text": asr_result["text"]})

                    if asr_result["type"] == "final":
                        user_text = asr_result["text"]
                        await websocket.send_json({"type": "asr_final", "text": user_text})
            except Exception as e:
                logger.error(f"ASR Error: {e}")
                await websocket.send_json({"type": "error", "message": "Speech recognition failed"})
                continue

            if user_text:
                # 2. LLM (Stream)
                async def llm_iterator_wrapper():
                    try:
                        async for token in chat_with_llm(user_text):
                             await websocket.send_json({"type": "llm_token", "text": token})
                             yield token
                    except Exception as e:
                        logger.error(f"LLM Error: {e}")
                        await websocket.send_json({"type": "error", "message": "AI processing failed"})

                # 3. TTS (Stream)
                try:
                    async for audio_chunk in text_to_speech_stream(llm_iterator_wrapper()):
                        await websocket.send_bytes(audio_chunk)
                except Exception as e:
                    logger.error(f"TTS Error: {e}")
                    # TTS error might happen mid-stream, hard to recover gracefully for user except logging

            await websocket.send_json({"type": "turn_end"})

    try:
        await asyncio.gather(
            receive_audio_from_client(),
            pipeline_worker()
        )
    except Exception as e:
        logger.error(f"WS Handler Error: {e}")
