import anthropic
import json
import os
import base64
import re
import uuid
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

def load_strategy():
    with open("data/strategy.json", "r") as f:
        return json.load(f)

def load_latest_trends():
    trend_files = [f for f in os.listdir("data") if f.startswith("trends_")]
    if not trend_files:
        return {}
    latest = sorted(trend_files)[-1]
    with open(f"data/{latest}", "r") as f:
        return json.load(f)

def load_anthropic_news():
    news_files = sorted([f for f in os.listdir("data") if f.startswith("anthropic_news_")])
    if not news_files:
        return {}
    with open(f"data/{news_files[-1]}") as f:
        return json.load(f)

def get_content_type_for_today(strategy):
    day = datetime.now().strftime("%A").lower()
    cadence = strategy["timing"]["weekly_cadence"]
    return cadence.get(day, "static")

def parse_claude_json(response_text):
    clean = response_text.strip()
    # Extract JSON object — find outermost { }
    start = clean.find('{')
    end   = clean.rfind('}')
    if start == -1 or end == -1:
        raise ValueError("No JSON object found in response")
    clean = clean[start:end+1]
    # Fix trailing commas
    clean = re.sub(r',\s*([}\]])', r'\1', clean)
    return json.loads(clean)

def get_recent_topics(limit=10):
    """Get topics from the last N queue files to enforce cooldown."""
    recent = []
    try:
        queue_files = sorted([
            f for f in os.listdir("queue")
            if f.endswith(".json") and os.path.isfile(f"queue/{f}")
        ], reverse=True)[:limit]
        for qf in queue_files:
            try:
                with open(f"queue/{qf}") as f:
                    q = json.load(f)
                t = q.get("post", {}).get("topic", "")
                c = q.get("generation_inputs", {}).get("topic_cluster", "")
                if t: recent.append(t.lower())
                if c and c not in recent: recent.append(c.lower())
            except:
                continue
    except:
        pass
    return recent

def generate_content(content_type=None):
    client   = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    strategy = load_strategy()
    trends   = load_latest_trends()

    if not content_type:
        content_type = get_content_type_for_today(strategy)

    print(f"Generating {content_type} post...")

    # Strategy summary — compressed to ~200 tokens
    try:
        import sys
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from strategy_summary import get_strategy_summary
        strategy_summary = get_strategy_summary()
    except:
        strategy_summary = "Bootstrap phase. Post Claude API tips 3x/week."

    # Topic pool + trending boost
    topics         = [c["cluster"] for c in strategy["topics"]["ranked_clusters"]]
    trending_boost = strategy["topics"].get("trending_boost", [])
    all_topics     = trending_boost + topics

    # Recent topics for cooldown
    recent_topics    = get_recent_topics(10)
    cooldown_days    = strategy.get("topics", {}).get("topic_cooldown_days", 14)
    avoid_topics_str = "\n".join(f"- {t}" for t in recent_topics[:8]) if recent_topics else "none yet"
    print(f"Recent topics (avoid for {cooldown_days}d): {recent_topics[:5]}")

    # Hook + caption config
    hook_style     = strategy["hooks"]["by_format"].get(content_type, "how_to")
    max_hook_chars = strategy["hooks"]["max_hook_chars"]
    evergreen      = strategy["hashtags"]["evergreen_tags"]
    caption_config = strategy["caption"]
    word_count     = caption_config["optimal_word_count"].get(
                         content_type, {"min": 80, "max": 150})
    preferred_days  = strategy["timing"]["preferred_days"]
    preferred_hours = strategy["timing"]["preferred_hours_utc"]
    rec_day  = preferred_days[0]["day"]  if preferred_days  else "thursday"
    rec_hour = f"{preferred_hours[0]:02d}:00" if preferred_hours else "13:00"

    # Trend context
    trend_context = ""
    if trends:
        trend_context = (
            f"Trending topics: {', '.join(trends.get('trending_topics',[])[:3])}\n"
            f"Top hook styles: {', '.join(trends.get('top_hook_styles',[])[:2])}\n"
            f"Trending audio: {trends.get('trending_audio',['original audio'])[0]}"
        )
    news = load_anthropic_news()
    news_ctx = ""
    if news:
        headlines = news.get("headlines", [])[:3]
        if headlines:
            news_ctx = f"Latest Anthropic news: {', '.join(headlines)}"

    prompt = f"""You are a social media content creator for @ask.claudeai — an Instagram page posting Claude API tips for developers.

CONTENT TYPE: {content_type} post
TOPIC POOL: {', '.join(all_topics[:6])}
HOOK STYLE: {hook_style} (max {max_hook_chars} characters)
CAPTION LENGTH: {word_count['min']}-{word_count['max']} words
CTA STYLE: {caption_config['cta_style']}
EMOJI DENSITY: {caption_config['emoji_density']}

STRATEGY:
{strategy_summary}

TREND CONTEXT:
{trend_context}
{news_ctx}

RECENTLY USED TOPICS (do NOT repeat these):
{avoid_topics_str}

EVERGREEN HASHTAGS: {', '.join(evergreen)}

Generate a high-quality Instagram post for developers about Claude API. Requirements:
- Genuinely useful and specific — not generic AI hype
- Written for developers who already code
- Practical with real code examples or concrete tips
- Optimised for saves — teach something worth keeping
- Do NOT choose a topic from the recently used list above

Return ONLY valid JSON:
{{
  "topic": "specific topic chosen (must not be in recently used list)",
  "topic_cluster": "{all_topics[0]}",
  "hook": "hook line (under {max_hook_chars} chars)",
  "hook_style": "{hook_style}",
  "caption": "full caption body (no hook, no hashtags, {word_count['min']}-{word_count['max']} words)",
  "hashtags": ["#claudeai","#anthropic","#aidev","#llm","#pythondev","#apidevelopment","#aiintegration","#machinelearning","#codinglife","#devtips","#programming","#artificialintelligence","#developer","#techstack","#buildwithclaude","#promptengineering","#automation","#aitools"],
  "audio_suggestion": "original audio",
  "image_text": "main text for image card (max 10 words)",
  "image_subtext": "secondary text for image (max 8 words)",
  "recommended_day": "{rec_day}",
  "recommended_time_utc": "{rec_hour}"
}}
CRITICAL: The caption must NOT contain any backticks, markdown code blocks, or triple backticks. Plain text only."""

    import time
    for attempt in range(3):
        try:
            message = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )
            break
        except Exception as e:
            if "rate_limit" in str(e).lower() or "429" in str(e):
                wait = 60 * (attempt + 1)
                print(f"Rate limit hit — waiting {wait}s before retry {attempt+1}/3")
                time.sleep(wait)
            else:
                raise

    try:
        post_data = parse_claude_json(message.content[0].text)
    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}")
        print(f"Raw response: {message.content[0].text[:500]}")
        return None

    post_id  = str(uuid.uuid4())[:8]
    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"queue/{date_str}_{post_id}.json"

    queue_entry = {
        "id":               post_id,
        "content_type":     content_type,
        "status":           "pending",
        "created_at":       datetime.now().isoformat(),
        "published_at":     None,
        "instagram_media_id": None,
        "imgbb_url":        None,
        "generation_inputs": {
            "strategy_snapshot": {
                "model_phase":    strategy["meta"]["model_phase"],
                "timing":         strategy["timing"],
                "content_format": strategy["content_format"]
            },
            "trend_report":    trends,
            "topic_cluster":   post_data.get("topic_cluster", "claude_api"),
            "hook_style_used": post_data.get("hook_style", hook_style)
        },
        "post": {
            "topic":           post_data.get("topic", ""),
            "hook":            post_data.get("hook", ""),
            "caption":         post_data.get("caption", ""),
            "hashtags":        post_data.get("hashtags", evergreen),
            "audio_suggestion":post_data.get("audio_suggestion", "original audio"),
            "image_text":      post_data.get("image_text", ""),
            "image_subtext":   post_data.get("image_subtext", "")
        },
        "scheduling": {
            "recommended_day":         post_data.get("recommended_day", rec_day),
            "recommended_time_utc":    post_data.get("recommended_time_utc", rec_hour),
            "actual_publish_day":      None,
            "actual_publish_time_utc": None,
            "timing_deviation_hours":  None
        },
        "model_prediction": {
            "predicted_engagement_rate": None,
            "predicted_reach":           None,
            "prediction_confidence":     None,
            "model_phase_at_prediction": strategy["meta"]["model_phase"]
        }
    }

    os.makedirs("queue", exist_ok=True)
    with open(filename, "w") as f:
        json.dump(queue_entry, f, indent=2)

    print(f"\nPost saved: {filename}")
    print(f"HOOK:  {post_data.get('hook','')}")
    print(f"TOPIC: {post_data.get('topic','')}")
    print(f"IMAGE: {post_data.get('image_text','')}")
    print(f"\nCAPTION PREVIEW:\n{post_data.get('caption','')[:200]}...")

    # Upload image to ImgBB if it exists
    # Upload image to Cloudinary (works in emails, no hotlink restrictions)
    image_path = f"queue/images/{post_id}.png"
    if os.path.exists(image_path):
        try:
            from upload_media import upload_image_cloudinary_feed
            url = upload_image_cloudinary_feed(image_path)
            queue_entry["imgbb_url"] = url   # reuse imgbb_url field for compatibility
            queue_entry["cloudinary_image_url"] = url
            with open(filename, "w") as f:
                json.dump(queue_entry, f, indent=2)
            print(f"Image uploaded to Cloudinary: {url}")
        except Exception as e:
            print(f"Cloudinary upload skipped: {e}")

    # Email notification sent by generate_image.py after image is uploaded
    # This ensures the email always has a valid image preview
    print("Email notification will be sent after image is generated.")

    return filename, queue_entry

if __name__ == "__main__":
    import sys
    content_type = sys.argv[1] if len(sys.argv) > 1 else None
    generate_content(content_type)