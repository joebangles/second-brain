"""
Second Brain - Integrated Voice Assistant App
Queues spoken prompts and processes them through the AI agent.
"""

import asyncio
import os
import sys
import warnings
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Deque, Optional

from dotenv import load_dotenv

# Suppress library warnings
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", message=".*non-text parts.*")
warnings.filterwarnings("ignore", message=".*there are non-text parts.*")
warnings.filterwarnings("ignore", message=".*concatenated text result.*")

from display import RichDisplay

from speechmatics.rt import (
    AsyncClient,
    ServerMessageType,
    TranscriptionConfig,
    TranscriptResult,
    AudioFormat,
    AudioEncoding,
    Microphone,
    ConversationConfig,
)

load_dotenv()

CHUNK_SIZE = 4096


class PromptStatus(Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class QueuedPrompt:
    """A prompt in the processing queue."""
    id: int
    text: str
    status: PromptStatus
    timestamp: datetime
    tools_used: list = None
    agents_used: list = None
    response: str = None
    error: str = None

    def __post_init__(self):
        if self.tools_used is None:
            self.tools_used = []
        if self.agents_used is None:
            self.agents_used = []


class SecondBrainApp:
    def __init__(self):
        self.client: Optional[AsyncClient] = None
        self.mic: Optional[Microphone] = None
        self.current_utterance: list = []
        self.prompt_queue: Deque[QueuedPrompt] = deque()
        self.completed_prompts: list = []
        self.prompt_counter = 0
        self.is_processing = False
        self.processing_task: Optional[asyncio.Task] = None
        self._agent_module = None
        
        # Session tracking
        self.session_start = datetime.now()
        self.raw_transcript: list = []  # List of (timestamp, text) tuples
        
        # Display
        self.display = RichDisplay()

    def load_agent(self):
        """Load the agent module, capture backend info for display."""
        if self._agent_module is None:
            # Capture stdout to get backend info
            import io
            old_stdout = sys.stdout
            sys.stdout = io.StringIO()
            
            from delegation_agent import process_utterance_with_tools
            self._agent_module = process_utterance_with_tools
            
            # Get captured output and restore stdout
            backend_info = sys.stdout.getvalue().strip()
            sys.stdout = old_stdout
            
            if backend_info:
                self.display.set_backend_info(backend_info)

    def get_agent(self):
        """Get the agent processing function."""
        if self._agent_module is None:
            self.load_agent()
        return self._agent_module

    def log_utterance(self, text: str):
        """Log a raw utterance to the transcript."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.raw_transcript.append((timestamp, text))

    def on_utterance_queued(self, prompt: QueuedPrompt):
        """Called when a new utterance is added to the queue."""
        self.display.add_prompt(prompt.id, prompt.text)

    def on_processing_start(self, prompt: QueuedPrompt):
        """Called when processing starts for a prompt."""
        self.display.update_prompt_status(prompt.id, "processing")

    def on_processing_complete(self, prompt: QueuedPrompt):
        """Called when processing completes for a prompt."""
        if prompt.status == PromptStatus.ERROR:
            self.display.update_prompt_status(prompt.id, "error", error=prompt.error)
        else:
            self.display.update_prompt_status(prompt.id, "completed", tools=prompt.tools_used)

    def add_to_queue(self, text: str):
        """Add a new prompt to the queue."""
        # Log raw utterance to transcript
        self.log_utterance(text)
        
        self.prompt_counter += 1
        prompt = QueuedPrompt(
            id=self.prompt_counter,
            text=text,
            status=PromptStatus.QUEUED,
            timestamp=datetime.now(),
        )
        self.prompt_queue.append(prompt)
        self.on_utterance_queued(prompt)
        
        # Start processing if not already running
        if not self.is_processing:
            self.processing_task = asyncio.create_task(self.process_queue())

    async def generate_session_summary(self) -> str:
        """Generate a high-level summary of the session using AI."""
        if not self.completed_prompts:
            return ""
        
        # Build context for summary
        context_lines = []
        for prompt in self.completed_prompts:
            visible_tools = [t for t in prompt.tools_used if t != "transfer_to_agent"]
            tools_str = f" [{', '.join(visible_tools)}]" if visible_tools else ""
            context_lines.append(f"- {prompt.text}{tools_str}")
        
        context = "\n".join(context_lines)
        
        # Ask the agent to summarize
        try:
            from delegation_agent import process_utterance_with_tools
            summary_prompt = f"""Summarize this voice session in 2-3 sentences. Be concise and focus on the key things the user did or said:

{context}

Write only the summary, no preamble."""
            
            result = await process_utterance_with_tools(summary_prompt)
            return result.response.strip()
        except Exception:
            return "Summary could not be generated."

    async def write_session_output(self) -> Optional[str]:
        """Write combined session output file with transcript, actions, and summary."""
        if not self.raw_transcript and not self.completed_prompts:
            return None
        
        ts = self.session_start.strftime("%Y%m%d_%H%M%S")
        filename = f"session_{ts}.txt"
        
        # Generate AI summary
        summary = await self.generate_session_summary()
        
        with open(filename, "w", encoding="utf-8") as f:
            # Header
            f.write("=" * 50 + "\n")
            f.write("SECOND BRAIN - Session Log\n")
            f.write(f"{self.session_start.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 50 + "\n\n")
            
            # Summary section
            if summary:
                f.write("SUMMARY\n")
                f.write("-" * 50 + "\n")
                f.write(f"{summary}\n\n")
            
            # Raw transcript section
            if self.raw_transcript:
                f.write("RAW TRANSCRIPT\n")
                f.write("-" * 50 + "\n")
                for timestamp, text in self.raw_transcript:
                    f.write(f"[{timestamp}] {text}\n")
                f.write("\n")
            
            # Actions section
            if self.completed_prompts:
                f.write("ACTIONS TAKEN\n")
                f.write("-" * 50 + "\n")
                for prompt in self.completed_prompts:
                    f.write(f"\"{prompt.text}\"\n")
                    
                    if prompt.status == PromptStatus.COMPLETED:
                        visible_tools = [t for t in prompt.tools_used if t != "transfer_to_agent"]
                        if visible_tools:
                            f.write(f"  -> {', '.join(visible_tools)}\n")
                        if prompt.response:
                            f.write(f"  -> {prompt.response.strip()}\n")
                    elif prompt.status == PromptStatus.ERROR:
                        f.write(f"  -> Error: {prompt.error}\n")
                    
                    f.write("\n")
            
            f.write("=" * 50 + "\n")
            f.write(f"Session ended: {datetime.now().strftime('%H:%M:%S')}\n")
        
        return filename

    async def process_queue(self):
        """Process prompts from the queue one by one."""
        self.is_processing = True
        first_item = True
        
        while self.prompt_queue:
            # Delay between requests to avoid rate limits (Gemini free tier is strict)
            if not first_item:
                await asyncio.sleep(4.0)
            first_item = False
            
            # Get next prompt
            prompt = self.prompt_queue[0]
            prompt.status = PromptStatus.PROCESSING
            self.on_processing_start(prompt)
            
            try:
                # Process through agent
                process_fn = self.get_agent()
                result = await process_fn(prompt.text)
                
                # Update prompt with results
                prompt.status = PromptStatus.COMPLETED
                prompt.response = result.response
                prompt.tools_used = result.tools_used
                prompt.agents_used = result.agents_used
                
            except Exception as e:
                prompt.status = PromptStatus.ERROR
                prompt.error = str(e)
            
            # Move to completed
            self.prompt_queue.popleft()
            self.completed_prompts.append(prompt)
            self.on_processing_complete(prompt)
        
        self.is_processing = False

    async def run(self, audio_file: Optional[str] = None):
        """Main run loop."""
        # Load agent first (prints backend info)
        self.load_agent()
        
        self.client = AsyncClient(api_key=os.getenv("SPEECHMATICS_API_KEY"))
        
        if not audio_file:
            self.mic = Microphone(sample_rate=16000, chunk_size=CHUNK_SIZE)
            self.mic.start()

        @self.client.on(ServerMessageType.ADD_TRANSCRIPT)
        def on_final(message):
            result = TranscriptResult.from_message(message)
            if result.metadata.transcript:
                self.current_utterance.append(result.metadata.transcript)

        @self.client.on(ServerMessageType.ADD_PARTIAL_TRANSCRIPT)
        def on_partial(message):
            pass

        @self.client.on(ServerMessageType.END_OF_UTTERANCE)
        def on_end_of_utterance(message):
            if self.current_utterance:
                full_utterance = "".join(self.current_utterance).strip()
                if full_utterance:
                    self.add_to_queue(full_utterance)
                self.current_utterance = []

        try:
            config = TranscriptionConfig(
                language="en",
                enable_partials=True,
                conversation_config=ConversationConfig(end_of_utterance_silence_trigger=1.0),
            )
            
            # We will use PCM_S16LE as the standard format for the RT client.
            # If it's a file, we'll try to treat it as raw PCM.
            encoding = AudioEncoding.PCM_S16LE 
            
            await self.client.start_session(
                transcription_config=config,
                audio_format=AudioFormat(encoding=encoding, sample_rate=16000),
            )
            
            self.display.start()
            
            if audio_file:
                import wave
                import struct
                
                # Read and convert WAV file to 16kHz mono PCM
                with wave.open(audio_file, 'rb') as wav:
                    channels = wav.getnchannels()
                    sample_rate = wav.getframerate()
                    sample_width = wav.getsampwidth()
                    n_frames = wav.getnframes()
                    
                    # Read all audio data
                    raw_data = wav.readframes(n_frames)
                    
                    # Convert to 16-bit samples
                    if sample_width == 2:
                        samples = struct.unpack(f'<{len(raw_data)//2}h', raw_data)
                    else:
                        print(f"Error: Unsupported sample width {sample_width}")
                        return
                    
                    # Convert stereo to mono by averaging channels
                    if channels == 2:
                        mono_samples = []
                        for i in range(0, len(samples), 2):
                            avg = (samples[i] + samples[i+1]) // 2
                            mono_samples.append(avg)
                        samples = mono_samples
                    
                    # Resample to 16kHz if needed
                    if sample_rate != 16000:
                        ratio = 16000 / sample_rate
                        new_length = int(len(samples) * ratio)
                        resampled = []
                        for i in range(new_length):
                            src_idx = i / ratio
                            idx = int(src_idx)
                            if idx + 1 < len(samples):
                                frac = src_idx - idx
                                val = int(samples[idx] * (1 - frac) + samples[idx + 1] * frac)
                            else:
                                val = samples[idx] if idx < len(samples) else 0
                            resampled.append(val)
                        samples = resampled
                    
                    # Convert back to bytes
                    pcm_data = struct.pack(f'<{len(samples)}h', *samples)
                
                # Stream the converted PCM data
                offset = 0
                while offset < len(pcm_data):
                    chunk = pcm_data[offset:offset + CHUNK_SIZE]
                    await self.client.send_audio(chunk)
                    offset += CHUNK_SIZE
                    # Simulate real-time: 4096 bytes at 16kHz 16-bit mono = 0.128s
                    await asyncio.sleep(0.128)
                    
                # Wait for the last utterance to be processed
                await asyncio.sleep(5.0)
            else:
                while True:
                    await self.client.send_audio(await self.mic.read(CHUNK_SIZE))
                
        except (KeyboardInterrupt, asyncio.CancelledError):
            pass
        finally:
            if self.mic:
                self.mic.stop()
            await self.client.close()
            
            # Wait for any pending processing
            if self.processing_task and not self.processing_task.done():
                await self.processing_task
            
            # Write combined session output
            self.display.set_generating_summary(True)
            filename = await self.write_session_output()
            self.display.set_generating_summary(False)
            
            # Stop display and show final message
            self.display.stop()
            if filename:
                self.display.print_final(f"Session saved: {filename}")


async def chat_mode():
    """Interactive chat mode to query your second brain."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.markdown import Markdown
    
    console = Console()
    
    # Load notes
    notes_content = ""
    try:
        with open("notes.txt", "r", encoding="utf-8") as f:
            notes_content = f.read()
    except FileNotFoundError:
        pass
    
    # Load calendar events (upcoming)
    calendar_content = ""
    try:
        from tools.calendar_tools import list_calendar_events
        calendar_content = list_calendar_events(max_results=20)
    except Exception:
        pass
    
    console.print()
    console.print(Panel(
        "[bold]SECOND BRAIN - Chat Mode[/bold]\n\n"
        "Ask questions about your notes, calendar, or anything else.\n"
        "Type 'exit' or 'quit' to leave.",
        border_style="blue"
    ))
    console.print()
    
    # Show what's loaded
    if notes_content:
        note_count = notes_content.count("---")
        console.print(f"[dim]Loaded {note_count} notes[/dim]")
    else:
        console.print("[dim]No notes found[/dim]")
    
    if calendar_content and "No upcoming events" not in calendar_content:
        console.print(f"[dim]Calendar loaded[/dim]")
    console.print()
    
    # Import the agent
    from delegation_agent import process_utterance_with_tools
    
    while True:
        try:
            user_input = console.input("[bold blue]You:[/bold blue] ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() in ("exit", "quit", "q"):
                console.print("\n[dim]Goodbye![/dim]")
                break
            
            # Build context-aware prompt
            context_parts = []
            if notes_content:
                context_parts.append(f"USER'S NOTES:\n{notes_content}")
            if calendar_content:
                context_parts.append(f"USER'S CALENDAR:\n{calendar_content}")
            
            if context_parts:
                context = "\n\n".join(context_parts)
                prompt = f"""You have access to the user's second brain. Use this context to answer their question.

{context}

USER'S QUESTION: {user_input}

Answer based on the context above. If the information isn't in their notes/calendar, say so. Be concise."""
            else:
                prompt = user_input
            
            console.print("[dim]Thinking...[/dim]")
            
            # Get response
            result = await process_utterance_with_tools(prompt)
            
            console.print()
            console.print(f"[bold green]Brain:[/bold green] {result.response}")
            console.print()
            
        except KeyboardInterrupt:
            console.print("\n\n[dim]Goodbye![/dim]")
            break
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Second Brain Voice Assistant")
    parser.add_argument("--file", help="Path to an audio file to process instead of microphone")
    parser.add_argument("--chat", action="store_true", help="Enter chat mode to query your second brain")
    args = parser.parse_args()

    if args.chat:
        asyncio.run(chat_mode())
    else:
        app = SecondBrainApp()
        try:
            asyncio.run(app.run(audio_file=args.file))
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
