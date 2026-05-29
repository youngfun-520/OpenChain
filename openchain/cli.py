"""CLI implementation for OpenChain."""
import click
from openchain.session import SessionManager
from openchain.agent.graph import build_graph
from openchain.model_registry import ModelRegistry


REPL_COMMANDS = {}


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

    while True:
        user_input = click.prompt("\nYou", type=str, default="")
        if user_input == "/quit":
            break
        elif user_input == "/new":
            session = await sm.create_session(workspace=workspace, model=model)
            session_id = session["session_id"]
            click.echo(f"New session: {session_id}")
            continue
        elif user_input == "/tree":
            nodes = await sm.get_session_tree(session_id)
            for n in nodes:
                click.echo(f"  {n['node_id'][:8]} [{n['role']}] {n['content'][:50]}...")
            continue
        elif user_input.startswith("/fork"):
            parts = user_input.split()
            if len(parts) == 2:
                forked = await sm.fork_session(session_id, parts[1])
                session_id = forked["session_id"]
                click.echo(f"Forked to: {session_id}")
            continue

        # Invoke graph for single turn
        result = await graph.ainvoke({
            "session_id": session_id,
            "workspace": workspace,
            "input_message": user_input,
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