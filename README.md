# Second Brain

An integrated voice assistant application that processes spoken prompts through an AI agent system.

## Features

- Real-time voice transcription using Speechmatics
- AI agent system for processing prompts
- Calendar and notes management tools
- Queue-based prompt processing
- Rich terminal display interface

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up environment variables:
   - Copy `.ENV` to `.env` (or create `.env` from template)
   - Configure your API keys and credentials

3. Set up Google API credentials:
   - Place your `credentials.json` file in the project root
   - The application will generate `token.json` on first run

## Usage

Run the application:
```bash
python app.py
```

## Project Structure

```
.
├── agents/          # AI agent implementations
├── tools/           # Tool modules (calendar, notes)
├── app.py           # Main application entry point
├── display.py       # Rich display interface
└── requirements.txt # Python dependencies
```

## Development

### Planned Features

- Docker/cloud deployment with docker-compose
- Configurable frontend/backend connection (local vs cloud)
- Three-container caching setup
- UI implementation
- Improved memory system

## License

[Add your license here]
