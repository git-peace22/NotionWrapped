"""
Second Brain Autopilot — CLI entry point.

Usage:
  python main.py run                      # process all pages
  python main.py run --page-id <id>      # process one page
  python main.py run --dry-run           # preview without writing
  python main.py wrapped                 # generate Notion Wrapped
"""

import asyncio
import typer
from typing import Optional

from src.mcp.client import notion_mcp
from src.agent.core import OrganizationAgent
from src.pipeline.organizer import WorkspaceOrganizer
from src.wrapped.runner import run_wrapped

app = typer.Typer(help="Second Brain Autopilot — AI-powered Notion organizer")


@app.command()
def run(
    page_id: Optional[str] = typer.Option(None, "--page-id", help="Process a single page by ID"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Discover pages but don't write"),
):
    """Scan and organize your Notion workspace."""
    asyncio.run(_run(page_id=page_id, dry_run=dry_run))


async def _run(page_id: Optional[str], dry_run: bool):
    async with notion_mcp() as client:
        if page_id:
            # Single page mode
            agent = OrganizationAgent(client)
            result = await agent.process_page(page_id)
            _print_summary([{"page_id": page_id, "title": page_id, "status": "done", "analysis": result}])
        else:
            # Full workspace scan
            organizer = WorkspaceOrganizer(client)
            results = await organizer.run(dry_run=dry_run)
            _print_summary(results)


def _print_summary(results: list[dict]):
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    done = [r for r in results if r["status"] == "done"]
    skipped = [r for r in results if r["status"] == "skipped"]
    errors = [r for r in results if r["status"] == "error"]

    print(f"  Processed : {len(done)}")
    print(f"  Skipped   : {len(skipped)}  (already had Second Brain Index)")
    print(f"  Errors    : {len(errors)}")

    if done:
        print("\nProcessed pages:")
        for r in done:
            a = r.get("analysis", {})
            print(f"  • {r['title']}")
            print(f"      Category : {a.get('category', '-')}")
            print(f"      Tags     : {', '.join(a.get('tags', []))}")

    if errors:
        print("\nErrors:")
        for r in errors:
            print(f"  • {r['title']}: {r.get('error', '')}")


@app.command()
def wrapped():
    """Generate your Notion Wrapped — a fun AI-powered summary of your entire brain."""
    asyncio.run(_run_wrapped())


async def _run_wrapped():
    async with notion_mcp() as client:
        url = await run_wrapped(client)
        if url:
            print(f"\n{'=' * 50}")
            print("✅  Notion Wrapped generated!")
            print(f"    Open it here: {url}")
            print("=" * 50)
        else:
            print("\n❌  Failed to generate Notion Wrapped.")


@app.command()
def serve(
    port: int = typer.Option(None, "--port", help="Port to run on"),
):
    """Launch the Notion Wrapped web UI in your browser."""
    import os
    import uvicorn
    actual_port = port or int(os.environ.get("PORT", 8000))
    print(f"\n🎉 Notion Wrapped UI → http://localhost:{actual_port}\n")
    uvicorn.run("src.api.server:app", host="0.0.0.0", port=actual_port)


if __name__ == "__main__":
    app()
