"""
Delegation Agent for Second Brain
A coordinator agent that delegates tasks to specialized subagents.
"""

import asyncio
import io
import os
import sys
import warnings
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from dotenv import load_dotenv

# Suppress library warnings
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", message=".*non-text parts.*")
warnings.filterwarnings("ignore", message=".*there are non-text parts.*")
warnings.filterwarnings("ignore", message=".*concatenated text result.*")


from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from agents import coordinator

load_dotenv()

# Configure Google AI backend
# Priority: Vertex AI (if project set) > Google AI Studio (if API key set)
if os.getenv("GOOGLE_CLOUD_PROJECT"):
    # Use Vertex AI - ADK reads from GOOGLE_CLOUD_PROJECT and GOOGLE_CLOUD_LOCATION env vars
    # Also need to set GOOGLE_GENAI_USE_VERTEXAI=true for the genai module
    os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "true"
    print("Using Vertex AI backend")
elif os.getenv("GOOGLE_API_KEY"):
    # Fall back to Google AI Studio (free tier)
    if not os.getenv("GOOGLE_GENAI_API_KEY"):
        os.environ["GOOGLE_GENAI_API_KEY"] = os.getenv("GOOGLE_API_KEY")
    print("Using Google AI Studio backend")


@dataclass
class ProcessingResult:
    """Result from processing an utterance, including tool usage info."""
    response: str
    tools_used: List[str] = field(default_factory=list)
    agents_used: List[str] = field(default_factory=list)


def get_current_datetime_context() -> str:
    """Get current date/time context string for the agent."""
    tz_name = os.getenv('TIMEZONE', 'UTC')
    now = datetime.now()
    return f"[Current date/time: {now.strftime('%A, %B %d, %Y at %H:%M')} ({tz_name})]"


# Create session service and runner for executing the agent
APP_NAME = "second_brain"
USER_ID = "user"

session_service = InMemorySessionService()
runner = Runner(
    agent=coordinator,
    app_name=APP_NAME,
    session_service=session_service,
)

# Counter for unique session IDs
_session_counter = 0


async def create_fresh_session() -> str:
    """Create a fresh session for each utterance to ensure coordinator routing."""
    global _session_counter
    _session_counter += 1
    session_id = f"session_{_session_counter}_{int(datetime.now().timestamp())}"
    await session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=session_id,
    )
    return session_id


async def _process_utterance_internal(text: str) -> ProcessingResult:
    """Internal processing function (no retry logic)."""
    # Create a fresh session for each utterance to ensure proper coordinator routing
    session_id = await create_fresh_session()
    
    # Include current date/time context with the user's message
    context = get_current_datetime_context()
    message_with_context = f"{context}\n\nUser: {text}"
    
    # Create the user message in the correct format
    user_message = types.Content(
        role="user",
        parts=[types.Part(text=message_with_context)]
    )
    
    # Track tools and agents used
    tools_used = []
    agents_used = []
    all_text_responses = []
    
    # Suppress google.genai warnings printed to stdout/stderr
    old_stdout, old_stderr = sys.stdout, sys.stderr
    sys.stdout = io.StringIO()
    sys.stderr = io.StringIO()
    
    try:
        # Run through the runner with proper session management
        async for event in runner.run_async(
            user_id=USER_ID,
            session_id=session_id,
            new_message=user_message,
        ):
            # Track agent transfers
            if hasattr(event, 'author') and event.author:
                agent_name = event.author
                if agent_name not in agents_used and agent_name != "coordinator":
                    agents_used.append(agent_name)
            
            # Track function/tool calls and text responses
            if hasattr(event, 'content') and event.content:
                if hasattr(event.content, 'parts'):
                    for part in event.content.parts:
                        # Check for function calls
                        if hasattr(part, 'function_call') and part.function_call:
                            tool_name = part.function_call.name
                            if tool_name and tool_name not in tools_used:
                                tools_used.append(tool_name)
                        # Collect all text responses
                        if hasattr(part, 'text') and part.text:
                            all_text_responses.append(part.text)
            
            # Also check for direct text attribute on event
            if hasattr(event, 'text') and event.text:
                all_text_responses.append(event.text)
    finally:
        sys.stdout, sys.stderr = old_stdout, old_stderr
    
    # Use the last non-empty text response (usually the final agent response)
    final_response = ""
    for resp in reversed(all_text_responses):
        if resp and resp.strip():
            final_response = resp.strip()
            break
    
    # Filter out internal routing tools
    visible_tools = [t for t in tools_used if t != "transfer_to_agent"]
    
    # If no visible tools but we have a response, infer tool from response text
    if not visible_tools and final_response:
        response_lower = final_response.lower()
        if any(phrase in response_lower for phrase in ["added", "scheduled", "calendar", "event created", "meeting"]):
            visible_tools = ["add_calendar_event"]
        elif any(phrase in response_lower for phrase in ["noted", "saved", "remembered", "note"]):
            visible_tools = ["save_note"]
    
    return ProcessingResult(
        response=final_response if final_response else "No response generated",
        tools_used=visible_tools,
        agents_used=agents_used,
    )


async def process_utterance_with_tools(text: str, max_retries: int = 5) -> ProcessingResult:
    """Process a single utterance with automatic retry on rate limit errors."""
    import random
    
    last_error = None
    for attempt in range(max_retries):
        try:
            # Add delay between attempts with exponential backoff
            if attempt > 0:
                # Start at 5s, then 10s, 20s, 40s...
                wait_time = (5 * (2 ** (attempt - 1))) + random.uniform(0, 2)
                print(f"  [Retry {attempt + 1}/{max_retries}] waiting {wait_time:.0f}s...")
                await asyncio.sleep(wait_time)
            
            return await _process_utterance_internal(text)
            
        except Exception as e:
            error_str = str(e)
            # Check for rate limit errors
            if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                last_error = e
                continue
            else:
                # Re-raise non-rate-limit errors immediately
                raise
    
    # All retries exhausted
    return ProcessingResult(
        response=f"Rate limit exceeded after {max_retries} retries.",
        tools_used=[],
        agents_used=[],
    )


async def process_utterance_async(text: str) -> str:
    """Process a single utterance and return the agent's response (legacy interface)."""
    result = await process_utterance_with_tools(text)
    return result.response


def process_utterance(text: str) -> str:
    """Synchronous wrapper for process_utterance_async."""
    import asyncio
    return asyncio.run(process_utterance_async(text))


def main():
    """Interactive console mode for testing."""
    print("Second Brain Delegation Agent")
    print("=" * 40)
    print("Subagents: calendar, notes, general")
    print("Type 'exit' to quit\n")
    
    while True:
        try:
            user_input = input("You: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit"):
                print("Goodbye!")
                break
            
            response = process_utterance(user_input)
            print(f"Agent: {response}\n")
            
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break


if __name__ == "__main__":
    main()
