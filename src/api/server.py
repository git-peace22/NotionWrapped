"""
FastAPI server — serves the Notion Wrapped web UI and runs the pipeline.
"""

import base64
from pathlib import Path
from urllib.parse import urlencode, quote

import httpx
from fastapi import FastAPI, Header
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from src.config import settings
from src.mcp.client import notion_mcp
from src.wrapped.collector import WrappedCollector
from src.wrapped.stats import compute_stats
from src.wrapped.analyzer import WrappedAnalyzer
from src.wrapped.writer import WrappedWriter

app = FastAPI(title="Notion Wrapped")

TEMPLATE = Path(__file__).parent.parent.parent / "templates" / "index.html"


# ── Serve UI ─────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index():
    return TEMPLATE.read_text()


# ── OAuth ─────────────────────────────────────────────────────────────────────

@app.get("/auth/login")
async def auth_login():
    """Redirect user to Notion's OAuth authorization page."""
    params = urlencode({
        "client_id": settings.notion_oauth_client_id,
        "redirect_uri": settings.redirect_uri,
        "response_type": "code",
        "owner": "user",
    })
    return RedirectResponse(f"https://api.notion.com/v1/oauth/authorize?{params}")


@app.get("/auth/callback")
async def auth_callback(code: str):
    """Exchange authorization code for access token, then send to frontend."""
    credentials = base64.b64encode(
        f"{settings.notion_oauth_client_id}:{settings.notion_oauth_client_secret}".encode()
    ).decode()

    async with httpx.AsyncClient() as http:
        resp = await http.post(
            "https://api.notion.com/v1/oauth/token",
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/json",
            },
            json={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.redirect_uri,
            },
        )

    data = resp.json()

    if "access_token" not in data:
        error = data.get("error_description", data.get("error", "OAuth failed"))
        return RedirectResponse(f"/?error={quote(error)}")

    access_token = data["access_token"]
    workspace_name = data.get("workspace_name", "your workspace")

    # Pass token + workspace name to frontend via URL; JS stores in localStorage
    return RedirectResponse(
        f"/?token={quote(access_token)}&workspace={quote(workspace_name)}"
    )


# ── Generate ──────────────────────────────────────────────────────────────────

@app.post("/generate")
async def generate(authorization: str | None = Header(default=None)):
    """Run the full Notion Wrapped pipeline using the caller's OAuth token."""
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization[len("Bearer "):]

    if not token:
        return JSONResponse({"error": "Not authenticated. Connect with Notion first."}, status_code=401)

    async with notion_mcp(token=token) as client:
        # Collect
        collector = WrappedCollector(client)
        pages = await collector.collect()

        if not pages:
            return JSONResponse(
                {"error": "No pages found. Make sure you granted access to some pages during authorization."},
                status_code=404,
            )

        # Stats
        stats = compute_stats(pages)

        # LLM analysis
        analyzer = WrappedAnalyzer()
        analysis = await analyzer.analyze(pages)

        # Hidden gem title lookup
        hidden_gem_id = analysis.get("hidden_gem_id", "")
        hidden_gem_title = next(
            (p["title"] for p in pages if p["id"] == hidden_gem_id), "Unknown"
        )

        # Write Notion page
        parent_page_id = pages[0]["id"]
        writer = WrappedWriter(client)
        notion_url = await writer.write(stats, analysis, pages, parent_page_id)

        return {
            "stats": stats,
            "analysis": analysis,
            "hidden_gem_title": hidden_gem_title,
            "notion_url": notion_url,
        }
