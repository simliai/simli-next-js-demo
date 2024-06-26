import asyncio
import logging
import aiohttp
from fastapi import FastAPI , WebSocket, WebSocketDisconnect
import granian
from granian import Granian
from granian.constants import Interfaces

app = FastAPI()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def send(
    websocket, process: asyncio.subprocess.Process
):
    print("SENDING")
    while True:
        if process.stdout is None:
            print("NO STDOUT")
            break
        data = await process.stdout.read(4096)
        print("Sending bytes:",len(data))
        await websocket.send_bytes(data)
    process.kill()
    await process.wait()

# Decode mp3 audio stream to pcm16 and send it to the WebSocket
async def decodeAudio(websocket):
        url = "https://radio.talksport.com/stream"
        ffmpeg = [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-i",
            url,
            "-f",
            "s16le",
            "-acodec",
            "pcm_s16le",
            "-ar",
            "16000",
            "-ac",
            "1",
            "pipe:1",
        ]
        print(" ".join(ffmpeg))
        process = await asyncio.subprocess.create_subprocess_exec(
            *ffmpeg,
            stdout=asyncio.subprocess.PIPE,
        )
        print("FFMPEG STARTED")
        sendTask = asyncio.create_task(send(websocket, process))
        await sendTask

async def stream_audio(websocket: WebSocket, url: str):
    logger.info(f"Streaming audio from: {url}")
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                logger.error(f"Failed to fetch audio from {url}. Status code: {resp.status}")
                return
            while True:
                try:
                    data = await resp.content.read(4000) # custom bytes chunk size
                    logger.info(f"Sent {len(data)} bytes of audio data")
                    if not data:
                        break
                    await websocket.send_bytes(data)
                except Exception as e:
                    logger.exception("Error occurred during audio streaming:")
                    break

@app.websocket("/audio")
async def audio_stream(websocket: WebSocket):
    logger.info("Audio WebSocket connection established")
    await websocket.accept()
    try:
        await decodeAudio(websocket)
    except WebSocketDisconnect:
        logger.info("Audio WebSocket disconnected")
    except Exception as e:
        logger.exception("Unexpected error occurred in audio streaming")

@app.websocket("/echo")
async def echo(websocket: WebSocket):
    logger.info("Echo WebSocket connection established")
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_bytes()
            await websocket.send_bytes(data)
    except WebSocketDisconnect:
        logger.info("Echo WebSocket disconnected")
    except Exception as e:
        logger.exception("Unexpected error occurred in echo WebSocket")

if __name__ == "__main__":
    Granian("app:app",interface=Interfaces.ASGI,port=9000).serve()