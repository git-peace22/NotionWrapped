"""
Stats computation — pure Python, no LLM needed.
Derives interesting numbers from collected page metadata.
"""

from collections import Counter
from datetime import datetime, timezone


def compute_stats(pages: list[dict]) -> dict:
    if not pages:
        return {}

    total_pages = len(pages)
    total_words = sum(p.get("word_count", 0) for p in pages)

    def parse_date(s: str) -> datetime | None:
        if not s:
            return None
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception:
            return None

    created_dates = [parse_date(p.get("created_time", "")) for p in pages]
    edited_dates = [parse_date(p.get("last_edited_time", "")) for p in pages]

    valid_created = [(d, i) for i, d in enumerate(created_dates) if d]

    oldest_page = "Unknown"
    newest_page = "Unknown"
    if valid_created:
        oldest_idx = min(valid_created, key=lambda x: x[0])[1]
        newest_idx = max(valid_created, key=lambda x: x[0])[1]
        oldest_page = pages[oldest_idx]["title"]
        newest_page = pages[newest_idx]["title"]

    # Pages by month (based on created_time)
    pages_by_month: Counter = Counter()
    for d, _ in valid_created:
        pages_by_month[d.strftime("%B %Y")] += 1

    hottest_month, hottest_count = pages_by_month.most_common(1)[0] if pages_by_month else ("Unknown", 0)

    # Date range string
    date_range_str = "Unknown"
    if valid_created:
        oldest_dt = min(d for d, _ in valid_created)
        newest_dt = max(d for d, _ in valid_created)
        date_range_str = f"{oldest_dt.strftime('%b %Y')} – {newest_dt.strftime('%b %Y')}"

    # Graveyard: created and never meaningfully edited (within 24h), untouched 30+ days
    now = datetime.now(timezone.utc)
    graveyard = []
    for i, page in enumerate(pages):
        cd = created_dates[i]
        ed = edited_dates[i]
        if cd and ed:
            never_revisited = (ed - cd).total_seconds() < 86400
            long_untouched = (now - ed).days > 30
            if never_revisited and long_untouched:
                graveyard.append(page["title"])

    # Longest abandoned: most days since last edit
    abandoned = []
    for i, page in enumerate(pages):
        ed = edited_dates[i]
        if ed:
            abandoned.append(((now - ed).days, page["title"]))
    abandoned.sort(reverse=True)
    longest_abandoned_days, longest_abandoned_title = abandoned[0] if abandoned else (0, "Unknown")

    return {
        "total_pages": total_pages,
        "total_words": total_words,
        "date_range_str": date_range_str,
        "oldest_page": oldest_page,
        "newest_page": newest_page,
        "hottest_month": hottest_month,
        "hottest_month_count": hottest_count,
        "pages_by_month": dict(pages_by_month.most_common(5)),
        "graveyard": graveyard[:5],
        "graveyard_total": len(graveyard),
        "longest_abandoned_title": longest_abandoned_title,
        "longest_abandoned_days": longest_abandoned_days,
    }
