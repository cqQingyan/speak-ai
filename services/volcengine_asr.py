import json
import logging
import websockets
import uuid
import gzip
import struct
import asyncio
from config import settings

logger = logging.getLogger(__name__)

class VolcengineASRService:
    def __init__(self):
        self.url = "wss://openspeech.bytedance.com/api/v3/sauc/bigmodel"
        self.app_id = settings.VOLC_APPID
        self.access_token = settings.VOLC_TOKEN
        # Resource ID for streaming ASR
        self.resource_id = "volc.bigasr.sauc.duration" # Using duration based billing resource id

    async def transcribe_stream(self, audio_generator):
        """
        Connects to Volcengine WebSocket and yields transcribed text.
        audio_generator: An async generator yielding audio bytes (chunks).
        """
        headers = {
            "X-Api-App-Key": self.app_id,
            "X-Api-Access-Key": self.access_token,
            "X-Api-Resource-Id": self.resource_id,
            "X-Api-Connect-Id": str(uuid.uuid4())
        }

        try:
            async with websockets.connect(self.url, additional_headers=headers) as ws:
                # 1. Send Full Client Request (Handshake)
                req_id = str(uuid.uuid4())
                payload = {
                    "user": {
                        "uid": "user_1" # In production, use actual user ID
                    },
                    "audio": {
                        "format": "webm", # Frontend sends webm
                        "rate": 16000,
                        "bits": 16,
                        "channel": 1,
                        "language": "zh-CN",
                        "codec": "opus" # WebM usually contains Opus
                    },
                    "request": {
                        "model_name": "bigmodel",
                        "enable_itn": True,
                        "enable_punc": True,
                        "result_type": "full"
                    }
                }

                # Protocol construction
                # Version(4bit) | HeaderSize(4bit) | MessageType(4bit) | Flags(4bit) | SerialMethod(4bit) | Compression(4bit) | Reserved(8bit)
                # 0x1110 -> Version=1(0001), HeaderSize=1(0001) -> 0x11
                # MessageType=FullClientRequest(0001), Flags=None(0000) -> 0x10
                # Serial=JSON(0001), Comp=Gzip(0001) -> 0x11
                # Reserved -> 0x00
                header_byte = b'\x11\x10\x11\x00'

                json_data = json.dumps(payload).encode('utf-8')
                compressed_data = gzip.compress(json_data)
                payload_size = len(compressed_data)

                # Header + Payload Size (4 bytes big-endian) + Payload
                full_msg = header_byte + struct.pack('>I', payload_size) + compressed_data
                await ws.send(full_msg)

                # Start a task to receive responses
                async def receive_loop():
                    full_text = ""
                    try:
                        async for message in ws:
                            # Parse Message
                            # Header is 4 bytes
                            if len(message) < 8:
                                continue

                            header = message[:4]
                            # Parse specific flags to check if it's error or response
                            # Byte 1: Ver(4)|HSize(4) -> 0x11
                            # Byte 2: MsgType(4)|Flags(4)
                            msg_type = (header[1] >> 4) & 0x0F
                            msg_flags = header[1] & 0x0F

                            if msg_type == 0b1111: # Error
                                logger.error("Volcengine Error Response")
                                continue

                            payload_size = struct.unpack('>I', message[4:8])[0]
                            payload = message[8:8+payload_size]

                            # Decompress if Gzip (0x.. .. .1 ..)
                            compression = header[2] & 0x0F
                            if compression == 0b0001:
                                try:
                                    payload = gzip.decompress(payload)
                                except Exception as e:
                                    logger.error(f"Gzip Decompress Error: {e}")
                                    continue

                            try:
                                resp_json = json.loads(payload.decode('utf-8'))
                                if 'result' in resp_json:
                                    # For full result type, text is the full text so far?
                                    # Or we check 'result_type' in request.
                                    # Documentation says "full" returns full text.
                                    # "single" returns incremental.
                                    # We requested "full", so we just update current state.
                                    current_text = resp_json['result'][0]['text']
                                    # We yield the DIFF or just the full text?
                                    # For ASR->LLM, we usually wait for "definite" sentence or end of speech.
                                    # But for now, let's just yield the final text at the end for simplicity in Phase 1,
                                    # OR yield partials if we want real-time display.
                                    # Let's yield partials with a flag.
                                    yield {"type": "partial", "text": current_text}
                                    full_text = current_text
                            except Exception as e:
                                logger.error(f"JSON Parse Error: {e}")

                    except Exception as e:
                        logger.error(f"Receive Loop Error: {e}")
                    yield {"type": "final", "text": full_text}

                # Start sending audio in background
                async def send_loop():
                    try:
                        async for chunk in audio_generator:
                            if not chunk:
                                continue

                            # Audio Only Request
                            # MsgType=AudioOnly(0010), Flags=Seq(0001) -> 0x21
                            # (Wait, user guide says 0000 for flags if not seq, let's use 0x20)
                            # Serial=None(0000), Comp=Gzip(0001) -> 0x01

                            # However, we are sending raw bytes (WebM), compressing it again with Gzip is okay.
                            comp_chunk = gzip.compress(chunk)

                            header_b = b'\x11\x20\x01\x00'
                            size_b = struct.pack('>I', len(comp_chunk))

                            await ws.send(header_b + size_b + comp_chunk)

                        # Send Last Packet (Negative Sequence / Flag indicating end)
                        # MsgType=AudioOnly(0010), Flags=LastPacket(0010) -> 0x22
                        header_end = b'\x11\x22\x01\x00'
                        empty_gz = gzip.compress(b'')
                        await ws.send(header_end + struct.pack('>I', len(empty_gz)) + empty_gz)

                    except Exception as e:
                        logger.error(f"Send Loop Error: {e}")

                # Run send loop as task
                send_task = asyncio.create_task(send_loop())

                # Yield results from receive loop
                async for result in receive_loop():
                    yield result

                await send_task

        except Exception as e:
            logger.error(f"Volcengine WS connection failed: {e}")
            yield {"type": "error", "text": str(e)}
