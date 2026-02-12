# Second Brain

An integrated voice assistant application that processes spoken prompts through an AI agent system.

## Features

- Real-time voice transcription using Speechmatics
- AI agent system for processing prompts
- Calendar and notes management tools
- Queue-based prompt processing
- Rich terminal display interface
- React web UI with live transcription
- WebSocket API for browser-based clients
- Docker support for easy deployment

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
4. Click "Start Listening" and speak

### Terminal Mode (Direct Microphone)

```bash
python app.py
```

### Other Terminal Options

```bash
# Process an audio file
python app.py --file path/to/audio.wav

# Interactive chat mode (text only)
python app.py --chat
```

## Project Structure

```
.
├── frontend/                # React web UI
│   ├── src/
│   │   ├── components/      # UI components
│   │   ├── hooks/           # React hooks (WebSocket, audio)
│   │   └── App.tsx          # Main app component
│   └── public/
│       └── audio-processor.js  # AudioWorklet for mic capture
├── agents/                  # AI agent implementations
├── tools/                   # Tool modules (calendar, notes)
├── app.py                   # Terminal application
├── server.py                # FastAPI WebSocket server
├── delegation_agent.py      # Agent orchestration
├── docker-compose.yml       # Docker orchestration
└── requirements.txt         # Python dependencies
```

## Configuration

### Backend (.env)

| Variable | Description |
|----------|-------------|
| `SPEECHMATICS_API_KEY` | Speechmatics RT API key |
| `GOOGLE_API_KEY` | Google AI Studio API key (free tier) |
| `GOOGLE_CLOUD_PROJECT` | Vertex AI project (alternative) |
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
6. Close WebSocket when done

### Client → Server Messages

```json
{"type": "start", "sampleRate": 16000, "language": "en"}  // Start recording
{"type": "stop"}  // Stop recording (waits for processing to complete)
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

## Development

### Prerequisites

- Python 3.11+
- Node.js 18+
- Speechmatics API key
- Google AI API key (AI Studio or Vertex AI)

### Google API Credentials

For calendar/notes tools, place `credentials.json` in the project root. The app generates `token.json` on first run.
