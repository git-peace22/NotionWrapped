"""
Wrapped runner — orchestrates the full Notion Wrapped pipeline:
  collect → compute stats → LLM analysis → write Notion page
"""

from src.mcp.client import NotionMCPClient
from src.wrapped.collector import WrappedCollector
from src.wrapped.stats import compute_stats
from src.wrapped.analyzer import WrappedAnalyzer
from src.wrapped.writer import WrappedWriter


async def run_wrapped(mcp_client: NotionMCPClient) -> str:
    """
    Full pipeline. Returns the URL of the generated Notion Wrapped page.
    """
    print("\n🎉 Starting Notion Wrapped...\n")

    # Step 1: Collect data from all pages
    collector = WrappedCollector(mcp_client)
    pages = await collector.collect()

    if not pages:
        print("[wrapped] No pages found. Make sure your integration is connected to some Notion pages.")
        return ""

    print(f"\n[wrapped] Collected data from {len(pages)} pages.")

    # Step 2: Compute stats (pure Python, no LLM)
    print("[wrapped] Computing stats...")
    stats = compute_stats(pages)
    print(f"[wrapped] {stats['total_pages']} pages · {stats['total_words']:,} words · hottest month: {stats['hottest_month']}")

    # Step 3: LLM analysis — one call for the whole workspace
    print("[wrapped] Asking AI to analyze your brain... 🧠")
    analyzer = WrappedAnalyzer()
    analysis = await analyzer.analyze(pages)
    print(f"[wrapped] Top obsessions: {', '.join(analysis.get('top_obsessions', []))}")
    print(f"[wrapped] One-word summary: {analysis.get('one_word_summary', '?')}")
    print(f"[wrapped] Roast lines ready: {len(analysis.get('roast_lines', []))}")

    # Step 4: Write Notion page (child of first accessible page)
    print("[wrapped] Writing your Notion Wrapped page...")
    parent_page_id = pages[0]["id"]
    writer = WrappedWriter(mcp_client)
    url = await writer.write(stats, analysis, pages, parent_page_id)

    return url
