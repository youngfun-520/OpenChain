"""CLI entry point for OpenChain agent."""

import click
from dotenv import load_dotenv

load_dotenv()


@click.group()
def cli():
    """OpenChain - A LangGraph-based AI coding agent."""
    pass


@cli.command()
def chat():
    """Start an interactive chat session."""
    click.echo("Chat mode not yet implemented")


@cli.command()
def api():
    """Start the API server."""
    click.echo("API mode not yet implemented")


if __name__ == "__main__":
    cli()