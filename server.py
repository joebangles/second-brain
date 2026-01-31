"""
Second Brain - FastAPI WebSocket Server
Proxies audio to Speechmatics RT and streams transcripts back to the client.
"""

import asyncio
import json
import os
import warnings
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Callable, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from speechmatics.rt import (
    AsyncClient,
    ServerMessageType,
    TranscriptionConfig,
    TranscriptResult,
    AudioFormat,
    AudioEncoding,
    ConversationConfig,
)

# Suppress library warnings
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", message=".*non-text parts.*")
warnings.filterwarnings("ignore", message=".*there are non-text parts.*")
warnings.filterwarnings("ignore", message=".*concatenated text result.*")

load_dotenv()


# =============================================================================
# Enums and Data Classes
# =============================================================================

class SessionState(Enum):
    """State of a Speechmatics session."""
    CREATED = "created"
    STARTING = "starting"
    RUNNING = "running"
    CLOSING = "closing"
    CLOSED = "closed"
    ERROR = "error"


class RecordingState(Enum):
    """Recording state for the client session."""
    IDLE = "idle"
    RECORDING = "recording"
    STOPPING = "stopping"


@dataclass
class TranscriptEvent:
    """A transcript event from Speechmatics."""
    type: str  # "partial", "final", "end_of_utterance"
    text: str = ""
    is_final: bool = False


# =============================================================================
# Speechmatics Session Class
# =============================================================================

class SpeechmaticsSession:
    """
    Manages a single Speechmatics RT session.
    """
    
    def __init__(
        self,
        api_key: str,
        on_partial: Optional[Callable[[str], None]] = None,
        on_final: Optional[Callable[[str], None]] = None,
        on_end_of_utterance: Optional[Callable[[str], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
    ):
        self.api_key = api_key
        self.on_partial = on_partial
        self.on_final = on_final
        self.on_end_of_utterance = on_end_of_utterance
        self.on_error = on_error
        
        self.client: Optional[AsyncClient] = None
        self.state = SessionState.CREATED
        self.current_utterance: list[str] = []
        self.last_partial: str = ""  # Track last partial for flushing on stop
        self._session_task: Optional[asyncio.Task] = None
    
    async def start(
        self,
        sample_rate: int = 16000,
        language: str = "en",
        end_of_utterance_silence: float = 1.0,
    ) -> bool:
        """Start the Speechmatics session."""
        if self.state != SessionState.CREATED:
            return False
        
        self.state = SessionState.STARTING
        
        try:
            self.client = AsyncClient(api_key=self.api_key)
            
            # Register event handlers
            @self.client.on(ServerMessageType.ADD_TRANSCRIPT)
            def handle_final(message):
                result = TranscriptResult.from_message(message)
                if result.metadata.transcript:
                    text = result.metadata.transcript
                    self.current_utterance.append(text)
                    self.last_partial = ""  # Clear partial on final
                    if self.on_final:
                        self.on_final(text)
            
            @self.client.on(ServerMessageType.ADD_PARTIAL_TRANSCRIPT)
            def handle_partial(message):
                result = TranscriptResult.from_message(message)
                if result.metadata.transcript:
                    self.last_partial = result.metadata.transcript
                    if self.on_partial:
                        self.on_partial(result.metadata.transcript)
            
            @self.client.on(ServerMessageType.END_OF_UTTERANCE)
            def handle_end_of_utterance(message):
                if self.current_utterance:
                    full_utterance = "".join(self.current_utterance).strip()
                    self.current_utterance = []
                    self.last_partial = ""
                    if full_utterance and self.on_end_of_utterance:
                        self.on_end_of_utterance(full_utterance)
            
            # Configure transcription
            config = TranscriptionConfig(
                language=language,
                enable_partials=True,
                conversation_config=ConversationConfig(
                    end_of_utterance_silence_trigger=end_of_utterance_silence
                ),
            )
            
            # Start session
            await self.client.start_session(
                transcription_config=config,
                audio_format=AudioFormat(
                    encoding=AudioEncoding.PCM_S16LE,
                    sample_rate=sample_rate,
                ),
            )
            
            self.state = SessionState.RUNNING
            return True
            
        except Exception as e:
            self.state = SessionState.ERROR
            if self.on_error:
                self.on_error(str(e))
            return False
    
    async def send_audio(self, audio_bytes: bytes) -> bool:
        """Send audio data to Speechmatics."""
        if self.state != SessionState.RUNNING or not self.client:
            return False
        
        try:
            await self.client.send_audio(audio_bytes)
            return True
        except Exception as e:
            if self.on_error:
                self.on_error(f"Error sending audio: {e}")
            return False
    
    def get_pending_text(self) -> Optional[str]:
        """Get any pending text (current utterance or last partial) for flushing."""
        if self.current_utterance:
            return "".join(self.current_utterance).strip()
        elif self.last_partial:
            return self.last_partial.strip()
        return None
    
    def clear_pending(self):
        """Clear pending utterance data."""
        self.current_utterance = []
        self.last_partial = ""
    
    async def close(self):
        """Close the Speechmatics session."""
        if self.state in (SessionState.CLOSED, SessionState.CLOSING):
            return
        
        self.state = SessionState.CLOSING
        
        if self.client:
            try:
                await self.client.close()
            except Exception:
                pass
        
        self.state = SessionState.CLOSED


# =============================================================================
# FastAPI Application
# =============================================================================

app = FastAPI(
    title="Second Brain API",
    description="WebSocket API for real-time voice transcription and AI agent processing",
    version="1.0.0",
)

# CORS configuration
allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Store active sessions for cleanup
active_sessions: dict[str, "ClientSession"] = {}


def build_chat_prompt(user_input: str) -> str:
    """Build a context-aware prompt using notes and calendar data."""
    notes_content = ""
    try:
        with open("notes.txt", "r", encoding="utf-8") as f:
            notes_content = f.read()
    except FileNotFoundError:
        notes_content = ""

    calendar_content = ""
    try:
        from tools.calendar_tools import list_calendar_events
        calendar_content = list_calendar_events(max_results=20)
    except Exception:
        calendar_content = ""

    context_parts = []
    if notes_content:
        context_parts.append(f"USER'S NOTES:\n{notes_content}")
    if calendar_content:
        context_parts.append(f"USER'S CALENDAR:\n{calendar_content}")

    if context_parts:
        context = "\n\n".join(context_parts)
        return f"""You have access to the user's second brain. Use this context to answer their question.

{context}

USER'S QUESTION: {user_input}

Answer based on the context above. If the information isn't in their notes/calendar, say so. Be concise."""

    return user_input


class ClientSession:
    """Manages a single client WebSocket connection and its Speechmatics session."""
    
    def __init__(self, websocket: WebSocket, session_id: str):
        self.websocket = websocket
        self.session_id = session_id
        self.speechmatics: Optional[SpeechmaticsSession] = None
        
        # Split state: recording vs connection
        self.recording_state = RecordingState.IDLE
        self.ws_connected = True  # Track WebSocket connection status
        
        self._agent_module = None
        self._pending_utterances: list[tuple[str, str, str]] = []
        self._processing_task: Optional[asyncio.Task] = None
        self._stop_event: Optional[asyncio.Event] = None
    
    def _get_agent(self):
        """Lazy-load the agent module."""
        if self._agent_module is None:
            from delegation_agent import process_utterance_with_tools
            self._agent_module = process_utterance_with_tools
        return self._agent_module
    
    async def send_json(self, data: dict) -> bool:
        """Send JSON message to the client. Returns False if send failed."""
        if not self.ws_connected:
            return False
        try:
            await self.websocket.send_json(data)
            return True
        except Exception:
            self.ws_connected = False
            return False
    
    async def handle_start(self, message: dict) -> bool:
        """Handle the 'start' message from the client."""
        # Idempotent: if already recording, just acknowledge
        if self.recording_state == RecordingState.RECORDING:
            await self.send_json({"type": "started"})
            return True
        
        # If stopping, wait for it to complete first
        if self.recording_state == RecordingState.STOPPING:
            await self.send_json({
                "type": "error",
                "message": "Please wait for stop to complete"
            })
            return False
        
        sample_rate = message.get("sampleRate", 16000)
        language = message.get("language", "en")
        
        api_key = os.getenv("SPEECHMATICS_API_KEY")
        if not api_key:
            await self.send_json({
                "type": "error",
                "message": "Speechmatics API key not configured"
            })
            return False
        
        # Create new Speechmatics session
        self.speechmatics = SpeechmaticsSession(
            api_key=api_key,
            on_partial=lambda text: asyncio.create_task(
                self.send_json({"type": "partial", "text": text})
            ),
            on_final=lambda text: asyncio.create_task(
                self.send_json({"type": "final", "text": text})
            ),
            on_end_of_utterance=lambda text: asyncio.create_task(
                self._handle_end_of_utterance(text)
            ),
            on_error=lambda msg: asyncio.create_task(
                self.send_json({"type": "error", "message": msg})
            ),
        )
        
        success = await self.speechmatics.start(
            sample_rate=sample_rate,
            language=language,
        )
        
        if success:
            self.recording_state = RecordingState.RECORDING
            await self.send_json({"type": "started"})
            await self.send_json({
                "type": "recording_state",
                "state": "recording"
            })
        else:
            await self.send_json({
                "type": "error",
                "message": "Failed to start Speechmatics session"
            })
        
        return success
    
    async def handle_stop(self) -> bool:
        """Handle the 'stop' message - stop recording immediately.
        
        Processing continues in the background. User can start recording again
        immediately without waiting for processing to complete.
        """
        if self.recording_state != RecordingState.RECORDING:
            # Already stopped or idle
            await self.send_json({"type": "stopped"})
            return True
        
        # Close Speechmatics session immediately
        if self.speechmatics:
            # Check for pending text before closing
            pending_text = self.speechmatics.get_pending_text()
            
            # Close Speechmatics
            await self.speechmatics.close()
            
            # If there was pending text, enqueue it for processing
            if pending_text:
                await self._handle_end_of_utterance(pending_text)
            
            self.speechmatics = None
        
        # Immediately return to idle - DON'T wait for processing
        # Processing continues in background, user can start new recording
        self.recording_state = RecordingState.IDLE
        await self.send_json({"type": "stopped"})
        await self.send_json({
            "type": "recording_state",
            "state": "idle"
        })
        
        return True

    async def handle_chat(self, message: dict) -> bool:
        """Handle a text chat message."""
        text = (message.get("text") or "").strip()
        if not text:
            await self.send_json({"type": "error", "message": "Chat text is required"})
            return False
        
        prompt = build_chat_prompt(text)
        self._enqueue_prompt(text, prompt, "chat")
        return True
    
    async def _handle_end_of_utterance(self, text: str):
        """Handle end of utterance - queue for agent processing."""
        await self.send_json({"type": "end_of_utterance", "text": text})
        
        self._enqueue_prompt(text, text, "voice")

    def _enqueue_prompt(self, raw_text: str, prompt_text: str, mode: str):
        """Queue a prompt for agent processing."""
        self._pending_utterances.append((raw_text, prompt_text, mode))

        if self._processing_task is None or self._processing_task.done():
            self._processing_task = asyncio.create_task(self._process_utterances())
    
    async def _process_utterances(self):
        """Process pending utterances through the agent.
        
        This drains the queue regardless of recording state.
        Only stops if WebSocket is disconnected.
        """
        while self._pending_utterances:
            # Check if WebSocket is still connected
            if not self.ws_connected:
                break
            
            raw_text, prompt_text, mode = self._pending_utterances.pop(0)
            
            try:
                if mode == "chat":
                    from delegation_agent import process_recall_query
                    result = await process_recall_query(prompt_text)
                else:
                    process_fn = self._get_agent()
                    result = await process_fn(prompt_text)
                
                await self.send_json({
                    "type": "agent_response",
                    "text": result.response,
                    "tools_used": result.tools_used,
                    "agents_used": result.agents_used,
                    "prompt": raw_text,
                })
            except Exception as e:
                await self.send_json({
                    "type": "agent_error",
                    "message": str(e),
                    "prompt": raw_text,
                })
            
            # Small delay between processing to avoid rate limits
            if self._pending_utterances:
                await asyncio.sleep(2.0)
    
    async def handle_audio(self, audio_bytes: bytes):
        """Handle binary audio data from the client."""
        if (self.recording_state == RecordingState.RECORDING and 
            self.speechmatics and 
            self.speechmatics.state == SessionState.RUNNING):
            await self.speechmatics.send_audio(audio_bytes)
    
    async def close(self):
        """Clean up the session on WebSocket disconnect."""
        self.ws_connected = False
        
        if self.speechmatics:
            await self.speechmatics.close()
            self.speechmatics = None
        
        # Cancel any pending processing (WebSocket is gone, can't send responses)
        if self._processing_task and not self._processing_task.done():
            self._processing_task.cancel()
            try:
                await self._processing_task
            except asyncio.CancelledError:
                pass


@app.websocket("/ws/transcribe")
async def websocket_transcribe(websocket: WebSocket):
    """
    WebSocket endpoint for real-time transcription.
    
    Protocol:
    - Client sends JSON: {"type": "start", ...} - Start recording
    - Client sends JSON: {"type": "stop"} - Stop recording (keeps connection open)
    - Client sends binary: raw PCM s16le audio frames
    - Server sends JSON: {"type": "started"} - Recording started
    - Server sends JSON: {"type": "stopped"} - Recording stopped, processing complete
    - Server sends JSON: {"type": "recording_state", "state": "idle|recording|stopping"}
    - Server sends JSON: {"type": "partial", "text": "..."}
    - Server sends JSON: {"type": "final", "text": "..."}
    - Server sends JSON: {"type": "end_of_utterance", "text": "..."}
    - Server sends JSON: {"type": "agent_response", "text": "...", "tools_used": [...]}
    """
    await websocket.accept()
    
    session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{id(websocket)}"
    session = ClientSession(websocket, session_id)
    active_sessions[session_id] = session
    
    try:
        while True:
            message = await websocket.receive()
            
            if message["type"] == "websocket.disconnect":
                break
            
            if "text" in message:
                # JSON message
                try:
                    data = json.loads(message["text"])
                    msg_type = data.get("type")
                    
                    if msg_type == "start":
                        await session.handle_start(data)
                    elif msg_type == "stop":
                        await session.handle_stop()
                        # Don't break - keep connection open for re-recording
                    elif msg_type == "chat":
                        await session.handle_chat(data)
                    else:
                        await session.send_json({
                            "type": "error",
                            "message": f"Unknown message type: {msg_type}"
                        })
                except json.JSONDecodeError:
                    await session.send_json({
                        "type": "error",
                        "message": "Invalid JSON message"
                    })
            
            elif "bytes" in message:
                # Binary audio data
                await session.handle_audio(message["bytes"])
    
    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await session.send_json({
                "type": "error",
                "message": f"Server error: {e}"
            })
        except Exception:
            pass
    finally:
        await session.close()
        active_sessions.pop(session_id, None)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "active_sessions": len(active_sessions),
        "timestamp": datetime.now().isoformat(),
    }


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up all active sessions on shutdown."""
    for session_id, session in list(active_sessions.items()):
        await session.close()
    active_sessions.clear()


# =============================================================================
# Main Entry Point
# =============================================================================

def main():
    """Run the server with uvicorn."""
    import uvicorn
    
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    
    print(f"Starting Second Brain API server on {host}:{port}")
    print(f"WebSocket endpoint: ws://{host}:{port}/ws/transcribe")
    print(f"Health check: http://{host}:{port}/health")
    
    uvicorn.run(
        "server:app",
        host=host,
        port=port,
        reload=True,
        log_level="info",
    )


if __name__ == "__main__":
    main()
