# Second Brain

An integrated voice assistant that processes spoken prompts through a multi-agent AI system with semantic memory.

## Features

- Real-time voice transcription using Speechmatics RT
- Multi-agent system (Google ADK + Gemini 2.0 Flash) routing to calendar, notes, and general agents
- Semantic memory system with hybrid search (keyword + vector similarity)
- Automatic context injection from stored memories into agent prompts
- Google Calendar integration (add, list, delete events)
- Note saving with local embeddings and full-text search
- Text chat mode with semantic memory recall
- React web UI with live transcription and recording controls
- WebSocket API for browser-based clients
- Rich terminal display interface
- Queue-based prompt processing
- Docker Compose deployment
- Session log consolidation via Gemini AI

## Quick Start

### Option 1: Local Development

**Backend Setup:**
```bash
# Install Python dependencies
pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env
# Edit .env with your API keys

# Start the backend server
uvicorn server:app --host 0.0.0.0 --port 8000 --reload
```

**Frontend Setup:**
```bash
cd frontend

# Install dependencies
npm install

# Start the dev server
npm run dev
```

Then open http://localhost:5173 in your browser.

### Option 2: Docker Compose

```bash
# Copy and configure environment
cp .env.example .env
# Edit .env with your API keys

# Start both services
docker-compose up
```

- Frontend: http://localhost:5173
- Backend: http://localhost:8000

## Usage Modes

### Web UI (Recommended)

1. Start the backend: `uvicorn server:app --host 0.0.0.0 --port 8000 --reload`
2. Start the frontend: `cd frontend && npm run dev`
3. Open http://localhost:5173
4. Click "Start Listening" and speak, or switch to Chat mode for text queries

### Terminal Mode (Direct Microphone)

```bash
python app.py
```

### Other Terminal Options

```bash
# Process an audio file
python app.py --file path/to/audio.wav

# Interactive chat mode (text only, uses semantic memory recall)
python app.py --chat
```

## Memory System

The application includes an advanced semantic memory system that enhances agent responses with relevant context from past interactions.

- **Hybrid search**: Combines FTS5 keyword matching (30%), vector similarity via sentence-transformers (50%), recency (10%), and importance scoring (10%)
- **Context injection**: Before processing any query, the top 5 relevant memories are automatically retrieved and injected into the agent prompt
- **Local embeddings**: Uses `all-MiniLM-L6-v2` (384 dimensions) locally with no API costs
- **Backward compatible**: Notes are saved to both the memory database and `notes.txt`

The memory system works transparently in both voice and chat modes, including via the web UI.

See [MEMORY_SETUP.md](MEMORY_SETUP.md) for detailed setup, usage, and architecture documentation.

## Project Structure

```
.
├── frontend/                    # React web UI
│   ├── src/
│   │   ├── components/          # Controls, StatusIndicator, TranscriptDisplay
│   │   ├── hooks/               # useWebSocket, useAudioCapture
│   │   ├── App.tsx              # Main app component (voice + chat modes)
│   │   └── main.tsx             # Entry point
│   ├── public/
│   │   ├── audio-processor.js   # AudioWorklet for mic capture
│   │   └── brain.svg
│   ├── Dockerfile
│   └── package.json
├── memory/                      # Semantic memory system
│   ├── types.py                 # Memory and SearchResult data classes
│   ├── storage.py               # SQLite + FTS5 database layer
│   ├── embeddings.py            # sentence-transformers integration
│   ├── retrieval.py             # Hybrid search + reranking
│   └── consolidation.py         # Session log analysis
├── agents/
│   └── agents.py                # Calendar, notes, general, and coordinator agents
├── tools/
│   ├── calendar_tools.py        # Google Calendar integration (OAuth2)
│   ├── notes_tools.py           # Note saving (memory DB + notes.txt)
│   └── memory_tools.py          # Memory admin tools (stats, rebuild, migrate)
├── app.py                       # Terminal application (voice, file, chat modes)
├── server.py                    # FastAPI WebSocket server
├── delegation_agent.py          # Agent orchestration + memory context injection
├── display.py                   # Rich terminal display
├── test_memory.py               # Memory system tests
├── test_websocket.py            # WebSocket connectivity tests
├── docker-compose.yml           # Docker orchestration (backend + frontend)
├── Dockerfile.backend           # Backend container (Python 3.11)
├── requirements.txt             # Python dependencies
└── .env.example                 # Environment template
```

## Configuration

### Backend (.env)

| Variable | Description |
|----------|-------------|
| `SPEECHMATICS_API_KEY` | Speechmatics RT API key |
| `TIMEZONE` | Timezone for date/time context (e.g., `America/Los_Angeles`) |
| `GOOGLE_API_KEY` | Google AI Studio API key (free tier) |
| `GOOGLE_CLOUD_PROJECT` | Vertex AI project (alternative to AI Studio) |
| `HOST` | Server host (default: 0.0.0.0) |
| `PORT` | Server port (default: 8000) |
| `ALLOWED_ORIGINS` | CORS origins for web clients |

### Frontend (frontend/.env)

| Variable | Description |
|----------|-------------|
| `VITE_BACKEND_WS_URL` | WebSocket URL (default: ws://localhost:8000/ws/transcribe) |

## WebSocket Protocol

Connect to `ws://localhost:8000/ws/transcribe`:

### Lifecycle

1. Connect WebSocket
2. Send `start` → Begin recording
3. Send binary audio frames
4. Send `stop` → Stop recording, wait for processing
5. Repeat from step 2 (connection stays open)
6. Or send `chat` messages at any time for text queries
7. Close WebSocket when done

### Client → Server Messages

```json
{"type": "start", "sampleRate": 16000, "language": "en"}  // Start recording
{"type": "stop"}                                            // Stop recording (waits for processing)
{"type": "chat", "text": "Where did I eat Thai food?"}     // Text chat query (semantic memory recall)
```
Plus binary PCM s16le audio frames while recording.

### Server → Client Messages

```json
{"type": "started"}  // Recording started
{"type": "stopped"}  // Recording stopped, all processing complete
{"type": "recording_state", "state": "idle|recording|stopping"}  // State updates
{"type": "partial", "text": "..."}  // Partial transcript (live)
{"type": "final", "text": "..."}  // Final transcript segment
{"type": "end_of_utterance", "text": "..."}  // Complete utterance, queued for processing
{"type": "agent_response", "text": "...", "tools_used": [...], "prompt": "..."}  // AI response
{"type": "agent_error", "message": "...", "prompt": "..."}  // Processing error
{"type": "error", "message": "..."}  // General error
```

### Key Behaviors

- **Stop waits for processing**: When you stop, pending utterances continue processing and responses are delivered before `stopped` is sent
- **Multiple record cycles**: Stop and start multiple times without reconnecting
- **Partial text flush**: If you stop mid-utterance, any pending partial text is automatically enqueued for processing
- **Chat queries**: Send text queries at any time; they use semantic memory retrieval and bypass the transcription pipeline

## Development

### Prerequisites

- Python 3.11+
- Node.js 18+
- Speechmatics API key
- Google AI API key (AI Studio or Vertex AI)

### Google API Credentials

<<<<<<< Updated upstream
For calendar/notes tools, place `credentials.json` in the project root. The app generates `token.json` on first run.

## License

[Add your license here]
=======
For calendar tools, place `credentials.json` in the project root. The app generates `token.json` on first run via OAuth2 flow.

### Testing

```bash
# Memory system tests
python test_memory.py

# WebSocket connectivity test
python test_websocket.py
```

## Future Work

- Container-level caching layer (e.g., Redis) for embedding and search results
- FAISS index for faster vector search at scale (10k+ memories)
- Cloud embeddings option (Gemini) for higher quality
- Memory clustering and graph relations between notes
- Multi-modal memory (images, audio, documents)
>>>>>>> Stashed changes
