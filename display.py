"""Rich-based terminal display for Second Brain."""

from typing import List, Optional
from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.text import Text


class PromptDisplay:
    """Represents a single prompt in the display."""
    def __init__(self, id: int, text: str):
        self.id = id
        self.text = text
        self.status = "queued"
        self.tools: List[str] = []
        self.error: Optional[str] = None

    def get_status_display(self) -> Text:
        """Get the formatted status text."""
        if self.status == "queued":
            return Text("queued", style="dim")
        elif self.status == "processing":
            return Text("processing", style="yellow")
        elif self.status == "completed":
            if self.tools:
                tools_str = ", ".join(self.tools)
                return Text(tools_str, style="green")
            return Text("processed", style="green")
        elif self.status == "error":
            return Text("error", style="red")
        return Text(self.status)

    def get_text_display(self, max_width: int = 60) -> str:
        """Get truncated text for display."""
        if len(self.text) > max_width:
            return self.text[:max_width - 3] + "..."
        return self.text


class RichDisplay:
    """Terminal UI using rich library."""
    
    def __init__(self):
        self.console = Console()
        self.prompts: List[PromptDisplay] = []
        self.live: Optional[Live] = None
        self.backend_info: str = ""
        self._generating_summary = False
    
    def set_backend_info(self, info: str):
        """Set the backend info string."""
        self.backend_info = info
    
    def _build_display(self) -> Panel:
        """Build the display panel."""
        # Create table for prompts
        table = Table(
            show_header=False,
            box=None,
            padding=(0, 1),
            expand=True,
        )
        table.add_column("text", ratio=3)
        table.add_column("status", ratio=1, justify="right")
        
        if not self.prompts:
            table.add_row(
                Text("Listening...", style="dim italic"),
                Text("")
            )
        else:
            for prompt in self.prompts:
                table.add_row(
                    prompt.get_text_display(),
                    prompt.get_status_display()
                )
        
        # Build subtitle
        subtitle = None
        if self._generating_summary:
            subtitle = "[dim]Generating summary...[/dim]"
        
        return Panel(
            table,
            title="[bold]SECOND BRAIN[/bold]",
            subtitle=subtitle,
            border_style="blue",
            padding=(1, 2),
        )
    
    def start(self):
        """Start the live display."""
        if self.backend_info:
            self.console.print(f"[dim]{self.backend_info}[/dim]")
        self.live = Live(
            self._build_display(),
            console=self.console,
            refresh_per_second=4,
            transient=False,
        )
        self.live.start()
    
    def stop(self):
        """Stop the live display."""
        if self.live:
            self.live.stop()
            self.live = None
    
    def refresh(self):
        """Refresh the display."""
        if self.live:
            self.live.update(self._build_display())
    
    def add_prompt(self, id: int, text: str):
        """Add a new prompt to the display."""
        prompt = PromptDisplay(id, text)
        self.prompts.append(prompt)
        self.refresh()
    
    def update_prompt_status(self, id: int, status: str, tools: List[str] = None, error: str = None):
        """Update a prompt's status."""
        for prompt in self.prompts:
            if prompt.id == id:
                prompt.status = status
                if tools:
                    # Filter out internal tools
                    prompt.tools = [t for t in tools if t != "transfer_to_agent"]
                if error:
                    prompt.error = error
                break
        self.refresh()
    
    def set_generating_summary(self, generating: bool):
        """Set whether we're generating a summary."""
        self._generating_summary = generating
        self.refresh()
    
    def print_final(self, message: str):
        """Print a final message after display stops."""
        self.console.print(f"\n{message}")
