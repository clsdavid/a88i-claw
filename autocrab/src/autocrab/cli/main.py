import typer
import uvicorn
from rich.console import Console
from autocrab.core.models.config import settings

app = typer.Typer(help="AutoCrab AI Agent Platform Framework")
console = Console()

@app.command()
def start(
    port: int = typer.Option(None, help="Port to bind the gateway to"),
    host: str = typer.Option("127.0.0.1", help="Host interface to bind to"),
    reload: bool = typer.Option(False, "--reload", "-r", help="Enable hot reload for development")
):
    """
    Start the AutoCrab API Gateway.
    """
    # Override settings if provided via CLI
    effective_port = port or settings.gateway.port

    console.print(f"[bold green]Starting AutoCrab Gateway on {host}:{effective_port}[/bold green]")
    if settings.features.enable_external_rag:
        console.print(f"[blue]RAG System[/blue]: ENABLED (Target: {settings.features.rag_system_url})")
    
    # Launch Uvicorn Programmatically
    uvicorn.run(
        "autocrab.core.gateway.main:app",
        host=host,
        port=effective_port,
        reload=reload,
        log_level="info"
    )

if __name__ == "__main__":
    app()
