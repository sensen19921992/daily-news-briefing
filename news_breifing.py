import feedparser
import requests
import re
import sys
from datetime import datetime, timezone, timedelta

NTFY_URL = "https://ntfy.sh/frederik_daily_news"

FEEDS = {
    "📺 TV2": [
        "https://feeds.tv2.dk/nyheder/rss",
        "https://tv2.dk/nyheder/rss",
    ],
    "📻 DR": [
        "https://www.dr.dk/nyheder/service/feeds/allenyheder",
    ],
    "💼 Finans": [
        "https://finans.dk/rss",
        "https://finans.dk/feed/",
    ],
    "📈 Børsen": [
        "https://borsen.dk/rss",
        "https://borsen.dk/feed/",
    ],
}

def get_cutoff():
    return datetime.now(timezone.utc) - timedelta(hours=12)

def clean_html(text):
    return re.sub(r"<[^>]+>", "", text or "").strip()

def fetch_top(urls, cutoff, max_items=2):
    for url in urls:
        try:
            feed = feedparser.parse(url)
            if not feed.entries:
                continue
            recent = []
            for e in feed.entries:
                parsed = getattr(e, "published_parsed", None) or getattr(e, "updated_parsed", None)
                if parsed:
                    pub = datetime(*parsed[:6], tzinfo=timezone.utc)
                    if pub >= cutoff:
                        recent.append(e)
            items = recent if recent else feed.entries
            return items[:max_items]
        except Exception:
            continue
    return []

def format_entry(entry, index):
    title = clean_html(entry.get("title", "Ingen titel"))
    summary = clean_html(entry.get("summary", entry.get("description", "")))
    if not summary:
        summary = "Ingen beskrivelse tilgængelig."
    if len(summary) > 500:
        summary = summary[:497] + "..."
    return f"{index}. {title}\n{summary}"

def main():
    now = datetime.now(timezone.utc)
    cutoff = get_cutoff()
    date_str = now.strftime("%d/%m/%Y")
    is_morning = 4 <= now.hour < 14
    title = f"🌅 Morgen-nyheder — {date_str}" if is_morning else f"🌙 Aften-nyheder — {date_str}"

    parts = []
    for source, urls in FEEDS.items():
        entries = fetch_top(urls, cutoff)
        parts.append(source)
        if not entries:
            parts.append("Ingen nyheder fundet.\n")
            continue
        for i, e in enumerate(entries, 1):
            parts.append(format_entry(e, i))
        parts.append("")

    body = "\n".join(parts).strip()

    resp = requests.post(
        NTFY_URL,
        data=body.encode("utf-8"),
        headers={
            "Title": title,
            "Priority": "default",
            "Content-Type": "text/plain; charset=utf-8",
        },
    )

    if resp.status_code == 200:
        print(f"Sendt: {title}")
    else:
        print(f"Fejl: {resp.status_code} — {resp.text}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
