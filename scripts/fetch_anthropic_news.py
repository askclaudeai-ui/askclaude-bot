import anthropic
import json
import os
import requests
import re
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_NEWS_SOURCES = [
    "https://www.anthropic.com/news",
    "https://docs.anthropic.com/en/release-notes/overview",
]

def fetch_page(url):
    """Fetch a page and return text content."""
    try:
        r = requests.get(url, timeout=15,
                         headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200:
            # Strip HTML tags
            text = re.sub(r'<[^>]+>', ' ', r.text)
            text = re.sub(r'\s+', ' ', text).strip()
            return text[:8000]  # limit context
    except Exception as e:
        print(f"Could not fetch {url}: {e}")
    return ""

def extract_news_with_claude(client, raw_content):
    """Use Claude to extract structured news from raw page content."""
    prompt = f"""You are analysing Anthropic's news page and release notes.
Extract the most important recent developments from this content.

RAW CONTENT:
{raw_content[:6000]}

Return ONLY valid JSON:
{{
  "headlines": [
    {{
      "title": "headline title",
      "summary": "one sentence summary (max 20 words)",
      "category": "model_release | api_update | research | product | policy",
      "relevance_for_devs": "why this matters for Claude API developers (max 15 words)"
    }}
  ],
  "new_topics_for_content": [
    "specific claude api topic suggested by this news (actionable, teachable)",
    "another topic"
  ],
  "top_3_this_week": [
    "most important development 1",
    "most important development 2",
    "most important development 3"
  ]
}}

Extract 3-6 headlines. Focus on what matters most for developers using Claude API.
Return only the JSON, no other text."""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1500,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": prompt}]
    )

    response_text = ""
    for block in message.content:
        if hasattr(block, "text"):
            response_text += block.text

    try:
        clean = response_text.strip()
        if "```" in clean:
            parts = clean.split("```")
            clean = parts[1] if len(parts) > 1 else clean
            if clean.startswith("json"): clean = clean[4:]
        clean = re.sub(r',\s*([}\]])', r'\1', clean.strip())
        return json.loads(clean)
    except Exception as e:
        print(f"JSON parse error: {e}")
        return {"headlines": [], "new_topics_for_content": [], "top_3_this_week": []}

def update_topic_guide(news_data):
    """Add new topics from Anthropic news into topic_guide.json."""
    guide_path = "data/topic_guide.json"
    if not os.path.exists(guide_path):
        print("topic_guide.json not found — skipping topic update")
        return

    with open(guide_path, "r") as f:
        guide = json.load(f)

    # Update Anthropic News pillar
    for pillar in guide["content_pillars"]:
        if pillar["pillar"] == "Anthropic News & Updates":
            new_topics = news_data.get("new_topics_for_content", [])
            # Add new topics, avoid duplicates
            existing = set(pillar["topics"])
            for t in new_topics:
                if t not in existing:
                    pillar["topics"].append(t)
            # Keep only last 10 news topics (they go stale)
            pillar["topics"] = pillar["topics"][-10:]
            break

    # Update last headlines
    guide["anthropic_news"]["last_headlines"] = news_data.get("top_3_this_week", [])
    guide["anthropic_news"]["last_fetched"]   = datetime.now().isoformat()
    guide["last_updated"] = datetime.now().strftime("%Y-%m-%d")

    with open(guide_path, "w") as f:
        json.dump(guide, f, indent=2)
    print(f"Topic guide updated with {len(news_data.get('new_topics_for_content',[]))} new topics")

def update_strategy_trending_boost(news_data):
    """Inject top news topics as trending_boost in strategy.json."""
    strategy_path = "data/strategy.json"
    if not os.path.exists(strategy_path):
        return

    with open(strategy_path, "r") as f:
        strategy = json.load(f)

    new_topics = news_data.get("new_topics_for_content", [])[:3]
    strategy["topics"]["trending_boost"] = new_topics
    strategy["meta"]["last_updated"]     = datetime.now().isoformat()

    with open(strategy_path, "w") as f:
        json.dump(strategy, f, indent=2)
    print(f"Strategy trending_boost updated: {new_topics}")

def fetch_anthropic_news():
    print("=" * 50)
    print("Fetching Anthropic news")
    print("=" * 50)

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    # Use Claude with web_search to find latest Anthropic news
    print("\nSearching for latest Anthropic news...")

    search_prompt = """Search for the latest Anthropic news, Claude model updates,
and API changes from the past week. Focus on:
1. New model releases or updates
2. New API features or endpoints
3. New Claude capabilities
4. Anthropic research papers or blog posts
5. Changes to Claude's behaviour or guidelines

Return ONLY valid JSON:
{
  "headlines": [
    {
      "title": "headline",
      "summary": "one sentence summary (max 20 words)",
      "category": "model_release | api_update | research | product | policy",
      "relevance_for_devs": "why this matters for Claude API developers (max 15 words)"
    }
  ],
  "new_topics_for_content": [
    "specific teachable claude api topic from this news",
    "another teachable topic"
  ],
  "top_3_this_week": [
    "most important development 1",
    "most important development 2",
    "most important development 3"
  ]
}

Return only the JSON."""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": search_prompt}]
    )

    response_text = ""
    for block in message.content:
        if hasattr(block, "text"):
            response_text += block.text

    try:
        clean = response_text.strip()
        if "```" in clean:
            parts = clean.split("```")
            clean = parts[1] if len(parts) > 1 else clean
            if clean.startswith("json"): clean = clean[4:]
        clean = re.sub(r',\s*([}\]])', r'\1', clean.strip())
        news_data = json.loads(clean)
    except Exception as e:
        print(f"Could not parse news response: {e}")
        news_data = {"headlines": [], "new_topics_for_content": [], "top_3_this_week": []}

    # Print findings
    print(f"\nFound {len(news_data.get('headlines', []))} headlines")
    for h in news_data.get("headlines", []):
        print(f"  [{h.get('category','')}] {h.get('title','')}")
        print(f"    → {h.get('relevance_for_devs','')}")

    print(f"\nTop 3 this week:")
    for item in news_data.get("top_3_this_week", []):
        print(f"  • {item}")

    print(f"\nNew content topics:")
    for t in news_data.get("new_topics_for_content", []):
        print(f"  + {t}")

    # Update topic guide and strategy
    update_topic_guide(news_data)
    update_strategy_trending_boost(news_data)

    # Save news report
    os.makedirs("data", exist_ok=True)
    date_str  = datetime.now().strftime("%Y-%m-%d")
    out_path  = f"data/anthropic_news_{date_str}.json"
    news_data["fetched_at"] = datetime.now().isoformat()

    with open(out_path, "w") as f:
        json.dump(news_data, f, indent=2)

    print(f"\nNews saved to {out_path}")
    print("=" * 50)
    return news_data

if __name__ == "__main__":
    fetch_anthropic_news()