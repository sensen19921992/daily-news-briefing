import feedparser
import requests
import re
import sys
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup

NTFY_URL = "https://ntfy.sh/frederik_daily_news"

RSS_FEEDS = {
    "DR": [
        "https://www.dr.dk/nyheder/service/feeds/allenyheder",
    ],
    "Politiken": [
        "https://politiken.dk/rss/",
        "https://politiken.dk/feed/",
    ],
    "Berlingske": [
        "https://www.berlingske.dk/rss/allenyheder",
        "https://www.berlingske.dk/rss/",
        "https://www.berlingske.dk/feed/",
    ],
    "Borsen": [
        "https://borsen.dk/rss",
        "https://borsen.dk/feed/",
        "https://borsen.dk/rss/nyheder",
    ],
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; NewsBot/1.0)"
}

def get_cutoff():
    return datetime.now(timezone.utc) - timedelta(hours=12)

def clean_html(text):
    return re.sub(r"<[^>]+>", "", text or "").strip()

def fetch_rss(urls, cutoff, max_items=2):
    for url in urls:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=10)
            if resp.status_code != 200:
                continue
            feed = feedparser.parse(resp.content)
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

def fetch_tv2(cutoff, max_items=2):
    try:
        resp = requests.get("https://nyheder.tv2.dk", headers=HEADERS, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        articles = []
        for tag in soup.find_all(["h2", "h3"], limit=30):
            text = tag.get_text(strip=True)
            if len(text) > 20:
                articles.append(text)
        articles = list(dict.fromkeys(articles))  # deduplicate
        return [{"title": t, "summary": ""} for t in articles[:max_items]]
    except Exception:
        return []

def format_rss_entry(entry, index):
    title = clean_html(entry.get("title", "Ingen titel"))
    summary = clean_html(entry.get("summary", entry.get("description", "")))
    if not summary:
        summary = "Ingen beskrivelse tilgaengelig."
    if len(summary) > 400:
        summary = summary[:397] + "..."
    return f"{index}. {title}\n{summary}"

def format_scraped_entry(entry, index):
    return f"{index}. {entry['title']}\nLaes mere pa nyheder.tv2.dk"

def main():
    now = datetime.now(timezone.utc)
    cutoff = get_cutoff()
    date_str = now.strftime("%d/%m/%Y")
    is_morning = 4 <= now.hour < 14
    title = f"Morgen-nyheder - {date_str}" if is_morning else f"Aften-nyheder - {date_str}"

    parts = []

    # TV2 via scraping
    parts.append("TV2")
    tv2_entries = fetch_tv2(cutoff)
    if tv2_entries:
        for i, e in enumerate(tv2_entries, 1):
            parts.append(format_scraped_entry(e, i))
    else:
        parts.append("Ingen nyheder fundet.")
    parts.append("")

    # RSS sources
    for source, urls in RSS_FEEDS.items():
        parts.append(source)
        entries = fetch_rss(urls, cutoff)
        if entries:
            for i, e in enumerate(entries, 1):
                parts.append(format_rss_entry(e, i))
        else:
            parts.append("Ingen nyheder fundet.")
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
        print(f"Fejl: {resp.status_code} - {resp.text}", file=sys.stderr)
        sys.exit(1)

if
