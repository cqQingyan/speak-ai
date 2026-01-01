import logging
import asyncio
import json
import base64
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from auth import verify_token
from services.volcengine_asr import VolcengineASRService
from services.llm_service import chat_with_llm
from services.tts_service import text_to_speech_stream

logger = logging.getLogger(__name__)
router = APIRouter()

@router.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket, token: str = None):
    # Verify Token (Query param usually or header if client supports)
    # WebSocket standard doesn't support custom headers in JS easily, usually query param.
    if not token:
        # Try query params manually if not auto-parsed (FastAPI does auto-parse query params)
        token = websocket.query_params.get("token")

    user = verify_token(token)
    if not user:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    await websocket.accept()
    logger.info(f"WebSocket connected: {user}")

    asr_service = VolcengineASRService()

    # Queues for Pipeline
    # Client Audio -> audio_queue -> ASR
    audio_queue = asyncio.Queue()

    # State flags
    is_processing = False

    async def receive_audio_from_client():
        try:
            while True:
                data = await websocket.receive()
                if "bytes" in data:
                    # Binary Audio Data
                    await audio_queue.put(data["bytes"])
                elif "text" in data:
                    # Text Control Message (e.g., {"action": "stop"})
                    try:
                        msg = json.loads(data["text"])
                        if msg.get("action") == "finish_speaking":
                             await audio_queue.put(None) # Signal End of Stream for this turn
                    except:
                        pass
        except WebSocketDisconnect:
            logger.info("Client disconnected")
            await audio_queue.put(None) # Ensure loops break
        except Exception as e:
            logger.error(f"Receive Error: {e}")
            await audio_queue.put(None)

    async def pipeline_worker():
        nonlocal is_processing
        while True:
            # Wait for some audio to start a turn
            # In a real continuous streaming, this is complex.
            # Simplified: We treat the connection as a continuous session.
            # But Volcengine ASR expects a stream.

            # We create an async generator wrapper for the queue
            async def audio_gen():
                while True:
                    chunk = await audio_queue.get()
                    if chunk is None:
                        break # End of turn or connection
                    yield chunk

            # Start ASR
            # NOTE: Volcengine needs a new connection for new request/turn usually?
            # Or one long connection? Docs say "Full Client Request" starts a session.
            # Let's assume one turn per "Press to Talk" for now, or we re-init for continuous.
            # If we want continuous, we just run this once.

            # Since the user requested "VAD" and "Model Plug-in", continuous is better.
            # But `VolcengineASRService` implementation closes after one session currently.
            # Let's run it once for the lifecycle if possible, or loop it.
            # Given `transcribe_stream` design, it runs once.
            # So we will run one ASR session per "Speech Segment" (detected by VAD on client).
            # Client sends audio, then sends "finish_speaking" (or we rely on backend VAD, but client VAD was requested).

            # Actually, `audio_queue.get()` blocks.
            # If we loop `pipeline_worker`, we need to know when a turn ends.
            # Let's assume the Client sends `null` (None) to signal end of utterance.

            chunk = await audio_queue.get()
            if chunk is None:
                # Connection likely closed or empty turn
                if audio_queue.empty(): # really done
                     break
                else:
                     continue

            # Push back the first chunk for generator
            # (Queue doesn't support peek easily, so we just yield it first)

            async def single_turn_gen(first_chunk):
                yield first_chunk
                while True:
                    c = await audio_queue.get()
                    if c is None:
                        break
                    yield c

            is_processing = True

            # 1. ASR
            user_text = ""
            async for asr_result in asr_service.transcribe_stream(single_turn_gen(chunk)):
                if asr_result["type"] == "error":
                    await websocket.send_json({"type": "error", "message": asr_result["text"]})
                    break

                if asr_result["type"] == "partial":
                     await websocket.send_json({"type": "asr_partial", "text": asr_result["text"]})

                if asr_result["type"] == "final":
                    user_text = asr_result["text"]
                    await websocket.send_json({"type": "asr_final", "text": user_text})

            if user_text:
                # 2. LLM (Stream)
                # We need to wrap LLM output into an async iterator for TTS

                # We also want to send text to client
                async def llm_iterator_wrapper():
                    async for token in chat_with_llm(user_text):
                         await websocket.send_json({"type": "llm_token", "text": token})
                         yield token

                # 3. TTS (Stream)
                async for audio_chunk in text_to_speech_stream(llm_iterator_wrapper()):
                    await websocket.send_bytes(audio_chunk)

            await websocket.send_json({"type": "turn_end"})
            is_processing = False

    # Run tasks
    try:
        await asyncio.gather(
            receive_audio_from_client(),
            pipeline_worker()
        )
    except Exception as e:
        logger.error(f"WS Handler Error: {e}")
