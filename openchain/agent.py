"""OpenChain agent entry point."""
import os
import click
from dotenv import load_dotenv

load_dotenv()


@click.group()
def cli():
    """OpenChain AI Agent."""
    pass


@cli.command()
@click.option("--workspace", default=".", help="Workspace directory")
def chat(workspace: str):
    """Start interactive CLI chat mode."""
    from openchain.cli import _run_chat
    from openchain.session import SessionManager
    from openchain.model_registry import ModelRegistry
    import asyncio

    mr = ModelRegistry()
    model = mr.get_default_model()
    sm = SessionManager()
    asyncio.run(_run_chat(sm, workspace, model))


@cli.command()
def api():
    """Start FastAPI server."""
    from openchain.api.routes import app
    import uvicorn
    host = os.getenv("OPENCHAIN_API_HOST", "0.0.0.0")
    port = int(os.getenv("OPENCHAIN_API_PORT", "8000"))
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    cli()