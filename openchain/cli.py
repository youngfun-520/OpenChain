"""CLI implementation for OpenChain."""
import asyncio
import re
import click
from openchain.session import SessionManager
from openchain.agent.graph import build_graph
from openchain.model_registry import ModelRegistry


REPL_COMMANDS = {}
REPL_COMMANDS_LIST = ["/quit", "/new", "/tree", "/fork", "/compact", "/help"]


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
@click.option("--verbose", is_flag=True, help="Show debug information")
def chat(workspace: str, verbose: bool = False):
    """Start interactive chat mode."""
    click.echo(f"OpenChain Chat - Workspace: {workspace}")
    click.echo("Type /help for commands, /quit to exit")

    mr = ModelRegistry()
    model = mr.get_default_model()

    sm = SessionManager()
    import asyncio
    asyncio.run(_run_chat(sm, workspace, model, verbose=verbose))


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


async def _run_chat(sm: SessionManager, workspace: str, model: str, verbose: bool = False):
    await sm.initialize()
    session = await sm.create_session(workspace=workspace, model=model)
    session_id = session["session_id"]
    click.echo(f"Session: {session_id}")

    graph = build_graph()
    ih = InputHelper()
    buffer = []
    final_input = ""

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
                click.echo(f"  {n['node_id']} [{n['role']}] {n['content'][:60]}...")
            continue
        elif final_input.startswith("/fork"):
            parts = final_input.split()
            if len(parts) == 2:
                try:
                    forked = await sm.fork_session(session_id, parts[1])
                    session_id = forked["session_id"]
                    click.echo(f"Forked to: {session_id}")
                except Exception as e:
                    click.echo(f"Error: {e}")
            continue
        elif final_input == "/help":
            click.echo("\nAvailable commands:")
            for cmd in REPL_COMMANDS_LIST:
                click.echo(f"  {cmd}")
            click.echo()
            continue
        elif final_input.startswith("/"):
            # Check registered REPL commands (like /compact)
            base_cmd = final_input.split()[0] if " " in final_input else final_input
            handler = REPL_COMMANDS.get(base_cmd)
            if handler:
                session_id = await handler(sm, session_id) or session_id
                continue
            else:
                click.echo(f"Unknown command: {final_input}")
                continue

        # Invoke graph for single turn
        import time
        t0 = time.time()
        if verbose:
            click.echo("[DEBUG] calling graph.ainvoke()...")
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
        elapsed = time.time() - t0
        num_messages = len(result.get("messages", []))
        tool_results = result.get("tool_results", [])
        error = result.get("error")
        if verbose:
            click.echo(f"[DEBUG] done in {elapsed:.1f}s | messages={num_messages} tool_results={len(tool_results)} error={error}")
        response = result["messages"][-1].content if result["messages"] else ""
        response_text = response

        # Parse <think> tags — show thinking in dim style, rest as response
        think_content = ""
        import re as _re
        m = _re.match(r"<think>(.*?)</think>\s*(.*)", response, re.DOTALL)
        if m:
            think_content = m.group(1).strip()
            response_text = m.group(2).strip()
        elif response.startswith("<think>"):
            think_content = response[len("<think>"):].strip()
            response_text = ""

        if think_content:
            click.echo(f"\n┌─ Thinking ──────────────────────────────")
            for line in think_content.split("\n"):
                click.echo(f"│ {line}")
            click.echo(f"└─────────────────────────────────────────")

        # Show tool results clearly
        if tool_results:
            for tr in tool_results:
                name = tr.get("tool_name", "?")
                res = tr.get("result", {})
                if res.get("status") == "success" and "items" in res:
                    items = res["items"]
                    click.echo(f"\n[{name}] {len(items)} items: {', '.join(items[:5])}{'...' if len(items) > 5 else ''}")
                elif res.get("status") == "success" and "content" in res:
                    click.echo(f"\n[{name}] {res['content'][:200]}")
                elif res.get("status") == "error":
                    click.echo(f"\n[{name}] Error: {res.get('message', 'unknown')}")
                elif tr.get("result"):
                    click.echo(f"\n[{name}] {str(res)[:300]}")
        if response_text:
            click.echo(f"\nAssistant: {response_text}")


    await sm.close()
    click.echo("Goodbye!")