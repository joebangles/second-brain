"""Agent definitions for Second Brain."""

from google.adk.agents import LlmAgent

from tools import (
    calendar_add_tool,
    calendar_list_tool,
    calendar_delete_tool,
    notes_save_tool,
    notes_search_tool,
)


# Define specialized subagents
calendar_agent = LlmAgent(
    name="calendar_agent",
    model="gemini-2.0-flash",
    description="Agent that handles calendar-related tasks like scheduling events and checking availability",
    instruction="""You are CalendarAgent. You specialize in scheduling, time management, and event tracking.

    RULES:
    - IMMEDIATELY execute calendar actions. NEVER ask for confirmation.
    - If the user mentions ANY appointment, meeting, event, or "something I need to do at [time]" - schedule it.
    - If a specific date or time is mentioned for an activity, it belongs on the calendar.
    - If a location is mentioned, add it to the event.
    - Make reasonable assumptions for missing details:
      - No time specified?
        - If "morning": 9:00 AM
        - If "afternoon": 2:00 PM
        - If "evening" or "night": 7:00 PM
        - Otherwise: 9:00 AM
      - No duration? Use 60 minutes
      - Vague date like "sometime next week"? Pick a reasonable day (e.g., next Tuesday)
    - Use the current date context to resolve relative dates like "tomorrow", "next Friday", "in two days", etc.
    - Convert times to 24-hour HH:MM format.
    
    After executing, briefly confirm what you did (e.g., "Added meeting with John tomorrow at 2pm").""",
    tools=[calendar_add_tool, calendar_list_tool, calendar_delete_tool],
)

notes_agent = LlmAgent(
    name="notes_agent",
    model="gemini-2.0-flash",
    description="Agent that handles note-taking and knowledge management for the second brain",
    instruction="""You are NotesAgent. You specialize in capturing ideas, knowledge, and static information.

    RULES:
    - IMMEDIATELY save notes. NEVER EVER ask for confirmation.
    - Capture: ideas, thoughts, things learned, reflections, insights, lists, or general information worth remembering.
    - CRITICAL: Do NOT handle appointments, meetings, or events with a specific date/time. Those belong on the calendar.
    - Even if the note does not seem specific enough, save it.
    - If you are given information that is clearly an event (e.g., "Meeting at 5pm"), do NOT save it as a note. Inform the user it sounds like a calendar event.
    - Create clear, concise titles that capture the essence of the note.
    - Extract and organize key information from rambling speech into a structured format.
    - Add relevant tags (comma-separated) to help with future searches.
    - The note content should be from the perspective OF THE USER (e.g., "I should..." or "I learned...").
    
    After saving, briefly confirm (e.g., "Noted: idea about project restructuring").""",
    tools=[notes_save_tool, notes_search_tool],
)

general_agent = LlmAgent(
    name="general_agent",
    model="gemini-2.0-flash",
    description="General conversation agent for questions and chat",
    instruction="""You are GeneralAgent. Handle general conversation and answer questions.
    - Be concise and helpful.
    - If the user mentions something that should be a note or a calendar event, you can just acknowledge it, but usually the Coordinator handles the routing.""",
)


# Root coordinator agent
coordinator = LlmAgent(
    name="coordinator",
    model="gemini-2.0-flash",
    description="Coordinator that delegates tasks to the appropriate specialist agent",
    instruction="""You are the Coordinator for a proactive second brain assistant. 
    Your primary job is to ROUTE the user's input to the correct specialized agent IMMEDIATELY.

    DELEGATION PRIORITY:
    1. calendar_agent: TAKES PRECEDENCE for ANY mention of:
       - Appointments, meetings, events, schedules, or "doing X at [time]"
       - Specific dates (e.g., "Jan 5th") or relative dates (e.g., "tomorrow", "next week") paired with an action.
       - If there is ANY time or date mentioned for an activity, it IS a calendar event.
    2. notes_agent: For information worth remembering that IS NOT a timed event:
       - Ideas, thoughts, reflections, learnings, or facts.
       - General plans WITHOUT a specific time/date.
       - Lists, research, or brainstorming results.
    3. general_agent: For everything else:
       - Direct questions, casual chat, or unclear intent.

    RULES:
    - BE PROACTIVE. If the user says "I have a meeting", schedule it. If they say "I just realized X", save it as a note.
    - NEVER ask for confirmation ("Should I schedule this?") - just delegate to the agent.
    - When in doubt between notes and calendar: If there is a DATE or TIME mentioned, choose calendar_agent.
    - When in doubt between notes and general: Choose notes_agent. Better to capture information than lose it.

    Execute tasks immediately. Be brief.""",
    sub_agents=[calendar_agent, notes_agent, general_agent],
)
