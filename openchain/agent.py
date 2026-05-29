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
def chat():
    """Start interactive CLI chat mode."""
    from openchain.cli import chat
    chat()


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