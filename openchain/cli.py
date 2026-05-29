"""CLI implementation for OpenChain."""
import asyncio
import re
import click
from openchain.session import SessionManager
from openchain.agent.graph import build_graph
from openchain.model_registry import ModelRegistry


REPL_COMMANDS = {}
REPL_COMMANDS_LIST = ["/quit", "/new", "/tree", "/fork", "/compact"]


class InputHelper:
    """Detects whether a partial input line is complete or still expecting more."""
    BRACKET_PAIRS = {"(": ")", "[": "]", "{": "}"}
    QUOTE_CHARS = {'"', "'"}

    def is_complete(self, line: str) -> bool:
        """Return True if line has all brackets/quotes closed."""
        if not line.strip():
            return True
        stack = []
        in_quote = None
        i = 0
        while i < len(line):
            c = line[i]
            if in_quote:
                if c == in_quote:
                    in_quote = None
                i += 1
                continue
            if c in self.QUOTE_CHARS:
                in_quote = c
            elif c == "\\" and i + 1 < len(line):
                i += 2
                continue
            elif c in self.BRACKET_PAIRS:
                stack.append(self.BRACKET_PAIRS[c])
            elif c in self.BRACKET_PAIRS.values():
                if not stack or stack[-1] != c:
                    return False
                stack.pop()
            i += 1
        return not stack and in_quote is None

    def clear_buffer(self):
        """Clear accumulated lines (called on Ctrl+C)."""
        self._buffer = []

    def __init__(self):
        self._buffer = []


def get_completions(word: str) -> list[str]:
    """Return list of completions for the given word prefix."""
    if not word.startswith("/"):
        return []
    return [cmd for cmd in REPL_COMMANDS_LIST if cmd.startswith(word)]


@click.command()
@click.option("--workspace", default=".", help="Workspace directory")
def chat(workspace: str):
    """Start interactive chat mode."""
    click.echo(f"OpenChain Chat - Workspace: {workspace}")
    click.echo("Type /help for commands, /quit to exit")

    mr = ModelRegistry()
    model = mr.get_default_model()

    sm = SessionManager()
    import asyncio
    asyncio.run(_run_chat(sm, workspace, model))


async def cmd_compact(sm, session_id):
    """Handle /compact command."""
    result = await sm.compact_session(session_id)
    if result["status"] == "success":
        print(f"✓ Compacted {result['messages_before']} messages — summary: {result['summary'][:80]}...")
    elif result["status"] == "skipped":
        print(f"Skipped: {result['reason']}")
    else:
        print(f"Error: {result}")
    return session_id


REPL_COMMANDS["/compact"] = cmd_compact


async def _run_chat(sm: SessionManager, workspace: str, model: str):
    await sm.initialize()
    session = await sm.create_session(workspace=workspace, model=model)
    session_id = session["session_id"]
    click.echo(f"Session: {session_id}")

    graph = build_graph()
    ih = InputHelper()
    buffer = []

    print("Welcome! Type /quit to exit.\n")
    while True:
        try:
            # Use run_in_executor to make sync input() work in async context
            # This preserves pipe/non-interactive input() behavior
            user_input = await asyncio.to_thread(input, "... " if buffer else "> ")
            buffer.append(user_input)
            full_input = "\n".join(buffer)
            if ih.is_complete(full_input):
                final_input = full_input.strip()
                buffer.clear()
            else:
                continue
        except KeyboardInterrupt:
            buffer.clear()
            ih.clear_buffer()
            print("^C")
            continue

        if final_input == "/quit":
            break
        elif final_input == "/new":
            session = await sm.create_session(workspace=workspace, model=model)
            session_id = session["session_id"]
            click.echo(f"New session: {session_id}")
            continue
        elif final_input == "/tree":
            nodes = await sm.get_session_tree(session_id)
            for n in nodes:
                click.echo(f"  {n['node_id'][:8]} [{n['role']}] {n['content'][:50]}...")
            continue
        elif final_input.startswith("/fork"):
            parts = final_input.split()
            if len(parts) == 2:
                forked = await sm.fork_session(session_id, parts[1])
                session_id = forked["session_id"]
                click.echo(f"Forked to: {session_id}")
            continue

        # Invoke graph for single turn
        result = await graph.ainvoke({
            "session_id": session_id,
            "workspace": workspace,
            "input_message": final_input,
            "parent_node_id": None,
            "model": model,
            "messages": [],
            "tool_calls": [],
            "tool_results": [],
            "current_tool_call_index": 0,
            "error": None,
            "retry_count": 0,
            "security_context": {"workspace_root": workspace}
        })
        response = result["messages"][-1].content if result["messages"] else ""
        click.echo(f"\nAssistant: {response}")

    await sm.close()
    click.echo("Goodbye!")