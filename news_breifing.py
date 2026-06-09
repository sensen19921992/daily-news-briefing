import feedparser
import requests
import re
import sys
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup

NTFY_URL = "https://ntfy.sh/frederik_daily_news"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

RSS_FEEDS = {
    "Politiken": [
        "https://politiken.dk/rss/",
        "https://politiken.dk/rss",
    ],
    "Berlingske": [
        "https://www.berlingske.dk/rss/allenyheder",
        "https://www.berlingske.dk/rss/",
    ],
    "Borsen": [
        "https://borsen.dk/rss",
        "https://borsen.dk/feed/",
    ],
}

JUNK_PHRASES = ["farvetema", "cookie", "log ind", "login", "javascript", "indstilling", "auto", "lys og mork"]


def get_cutoff():
    return datetime.now(timezone.utc) - timedelta(hours=12)


def clean_html(text):
    return re.sub(r"<[^>]+>", "", text or "").strip()


def is_junk(text):
    t = text.lower()
    return any(phrase in t for phrase in JUNK_PHRASES)


def scrape_article_summary(url, max_chars=350):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=8)
        soup = BeautifulSoup(resp.text, "html.parser")
        for container in ["article", "main", "body"]:
            section = soup.find(container)
            if not section:
                continue
            for p in section.find_all("p"):
                text = p.get_text(strip=True)
                if len(text) > 80 and not is_junk(text):
                    return text[:max_chars] + ("..." if len(text) > max_chars else "")
    except Exception:
        pass
    return ""


def fetch_rss(urls, cutoff, max_items=2):
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


def fetch_dr(cutoff, max_items=2):
    entries = fetch_rss(["https://www.dr.dk/nyheder/service/feeds/allenyheder"], cutoff, max_items)
    result = []
    for e in entries:
        title = clean_html(e.get("title", "Ingen titel"))
        link = e.get("link", "")
        summary = scrape_article_summary(link) if link else ""
        result.append({"title": title, "summary": summary or "Laes mere pa dr.dk"})
    return result


def fetch_tv2(max_items=2):
    try:
        resp = requests.get("https://nyheder.tv2.dk", headers=HEADERS, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        seen = set()
        articles = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if not (re.search(r"/\d{4}/\d{2}/\d{2}/", href) or "/nyhed" in href):
                continue
            h = a.find(["h2", "h3"])
            if not h:
                continue
            title = h.get_text(strip=True)
            if len(title) < 20 or title in seen or is_junk(title):
                continue
            seen.add(title)
            article_url = href if href.startswith("http") else "https://nyheder.tv2.dk" + href
            summary = scrape_article_summary(article_url)
            articles.append({"title": title, "summary": summary or "Laes mere pa nyheder.tv2.dk"})
            if len(articles) >= max_items:
                break
        return articles
    except Exception:
        return []


def format_entry(entry, index):
    return str(index) + ". " + entry["title"] + "\n" + entry.get("summary", "")


def format_rss_entry(entry, index):
    title = clean_html(entry.get("title", "Ingen titel"))
    summary = clean_html(entry.get("summary", entry.get("description", "")))
    if not summary:
        summary = "Ingen beskrivelse tilgaengelig."
    if len(summary) > 400:
        summary = summary[:397] + "..."
    return str(index) + ". " + title + "\n" + summary


def main():
    now = datetime.now(timezone.utc)
    cutoff = get_cutoff()
    date_str = now.strftime("%d/%m/%Y")
    is_morning = 4 <= now.hour < 14
    title = "Morgen-nyheder - " + date_str if is_morning else "Aften-nyheder - " + date_str

    parts = []

    parts.append("TV2")
    tv2_entries = fetch_tv2()
    if tv2_entries:
        for i, e in enumerate(tv2_entries, 1):
            parts.append(format_entry(e, i))
    else:
        parts.append("Ingen nyheder fundet.")
    parts.append("")

    parts.append("DR")
    dr_entries = fetch_dr(cutoff)
    if dr_entries:
        for i, e in enumerate(dr_entries, 1):
            parts.append(format_entry(e, i))
    else:
        parts.append("Ingen nyheder fundet.")
    parts.append("")

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
        print("Sendt: " + title)
    else:
        print("Fejl: " + str(resp.status_code) + " - " + resp.text, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
