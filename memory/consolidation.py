"""
Memory consolidation - Extract insights from session logs.
"""

import argparse
import json
import re
from pathlib import Path
from typing import List, Dict, Optional

from .storage import MemoryDatabase
from .retrieval import MemoryRetrieval


class SessionConsolidator:
    """Extracts insights from session logs and adds them to memory."""

    def __init__(self, db: MemoryDatabase, retrieval: MemoryRetrieval):
        """Initialize consolidator with database and retrieval system."""
        self.db = db
        self.retrieval = retrieval

    def consolidate_session(self, session_file: str) -> int:
        """
        Consolidate a single session log file.

        Returns:
            Number of insights extracted
        """
        session_path = Path(session_file)
        if not session_path.exists():
            print(f"Session file not found: {session_file}")
            return 0

        # Parse session log
        parsed = self._parse_session_log(session_path)
        if not parsed:
            print(f"Failed to parse session file: {session_file}")
            return 0

        # Extract insights using AI
        insights = self._extract_insights(parsed)

        if not insights:
            print(f"No insights extracted from: {session_file}")
            return 0

        # Save insights to database
        count = self._save_insights(insights, session_path.name)

        print(f"Extracted {count} insights from {session_path.name}")
        return count

    def consolidate_all_sessions(self, directory: str = ".") -> int:
        """
        Consolidate all session log files in a directory.

        Returns:
            Total number of insights extracted
        """
        dir_path = Path(directory)
        session_files = list(dir_path.glob("session_*.txt"))

        if not session_files:
            print(f"No session files found in {directory}")
            return 0

        total_count = 0
        for session_file in session_files:
            count = self.consolidate_session(str(session_file))
            total_count += count

        print(f"\nTotal: {total_count} insights from {len(session_files)} sessions")
        return total_count

    def _parse_session_log(self, session_path: Path) -> Optional[Dict[str, str]]:
        """Parse a session log file into sections."""
        try:
            with open(session_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Extract sections
            sections = {}

            # Summary section
            summary_match = re.search(
                r'SUMMARY\s*-+\s*(.+?)\n\n',
                content,
                re.DOTALL
            )
            if summary_match:
                sections['summary'] = summary_match.group(1).strip()

            # Raw transcript section
            transcript_match = re.search(
                r'RAW TRANSCRIPT\s*-+\s*(.+?)(?:\n\nACTIONS|\n\n=+)',
                content,
                re.DOTALL
            )
            if transcript_match:
                sections['transcript'] = transcript_match.group(1).strip()

            # Actions section
            actions_match = re.search(
                r'ACTIONS TAKEN\s*-+\s*(.+?)(?:\n\n=+)',
                content,
                re.DOTALL
            )
            if actions_match:
                sections['actions'] = actions_match.group(1).strip()

            return sections if sections else None

        except Exception as e:
            print(f"Error parsing {session_path}: {e}")
            return None

    def _extract_insights(self, parsed: Dict[str, str]) -> List[Dict[str, str]]:
        """
        Extract insights from parsed session content using AI.

        Returns:
            List of insights with title, content, and type
        """
        # Build analysis prompt
        prompt_parts = []

        if 'summary' in parsed:
            prompt_parts.append(f"Session Summary:\n{parsed['summary']}")

        if 'transcript' in parsed:
            # Limit transcript to avoid huge prompts
            transcript = parsed['transcript']
            if len(transcript) > 2000:
                transcript = transcript[:2000] + "..."
            prompt_parts.append(f"\nTranscript:\n{transcript}")

        if 'actions' in parsed:
            prompt_parts.append(f"\nActions:\n{parsed['actions']}")

        if not prompt_parts:
            return []

        content = "\n".join(prompt_parts)

        # Use Gemini to extract insights
        try:
            from google import genai
            from google.genai import types
            import os

            # Configure client
            if os.getenv("GOOGLE_CLOUD_PROJECT"):
                client = genai.Client(
                    vertexai=True,
                    project=os.getenv("GOOGLE_CLOUD_PROJECT"),
                    location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
                )
            else:
                api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GOOGLE_GENAI_API_KEY")
                client = genai.Client(api_key=api_key)

            # Extraction prompt
            extraction_prompt = f"""Analyze this session log and extract key information worth remembering.

{content}

Extract:
1. Important facts the user mentioned
2. Preferences or decisions made
3. Recurring topics or themes
4. People, places, or things mentioned

Return ONLY a JSON array of insights with this exact format:
[{{"title": "short title", "content": "detailed content", "type": "fact|preference|topic"}}]

If no insights are found, return an empty array: []

Do not include any other text or explanation."""

            response = client.models.generate_content(
                model="gemini-2.0-flash-exp",
                contents=extraction_prompt,
                config=types.GenerateContentConfig(
                    temperature=0.3,
                    max_output_tokens=1000,
                )
            )

            # Parse JSON response
            response_text = response.text.strip()

            # Try to extract JSON if wrapped in markdown
            json_match = re.search(r'```(?:json)?\s*(\[.+?\])\s*```', response_text, re.DOTALL)
            if json_match:
                response_text = json_match.group(1)

            # Clean up common issues
            response_text = response_text.strip()
            if not response_text.startswith('['):
                # Try to find the JSON array
                start = response_text.find('[')
                end = response_text.rfind(']')
                if start >= 0 and end > start:
                    response_text = response_text[start:end+1]

            insights = json.loads(response_text)

            # Validate structure
            valid_insights = []
            for insight in insights:
                if isinstance(insight, dict) and 'title' in insight and 'content' in insight:
                    valid_insights.append({
                        'title': insight['title'],
                        'content': insight['content'],
                        'type': insight.get('type', 'fact')
                    })

            return valid_insights

        except Exception as e:
            print(f"Error extracting insights: {e}")
            return []

    def _save_insights(self, insights: List[Dict[str, str]], source_id: str) -> int:
        """
        Save extracted insights to the database.

        Returns:
            Number of insights saved
        """
        count = 0
        for insight in insights:
            try:
                # Determine memory type from insight type
                memory_type_map = {
                    'fact': 'fact',
                    'preference': 'insight',
                    'topic': 'insight',
                }
                memory_type = memory_type_map.get(insight['type'], 'insight')

                # Add to database with embedding
                self.retrieval.add_memory_with_embedding(
                    title=insight['title'],
                    content=insight['content'],
                    memory_type=memory_type,
                    source_type='consolidated',
                    source_id=source_id,
                )
                count += 1

            except Exception as e:
                print(f"Error saving insight '{insight.get('title')}': {e}")

        return count


def main():
    """CLI interface for consolidation."""
    parser = argparse.ArgumentParser(
        description="Extract insights from session logs into memory"
    )
    parser.add_argument(
        "--session",
        help="Path to a single session file to consolidate"
    )
    parser.add_argument(
        "--import-all",
        metavar="DIR",
        help="Import all session files from directory"
    )

    args = parser.parse_args()

    # Initialize memory system
    try:
        db = MemoryDatabase("memory.db")
        retrieval = MemoryRetrieval(db)
        consolidator = SessionConsolidator(db, retrieval)
    except Exception as e:
        print(f"Error initializing memory system: {e}")
        return 1

    if args.session:
        consolidator.consolidate_session(args.session)
    elif args.import_all:
        consolidator.consolidate_all_sessions(args.import_all)
    else:
        print("Please specify --session FILE or --import-all DIR")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
