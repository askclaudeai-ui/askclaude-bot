import anthropic
import json
import os
import base64
import re
import uuid
from datetime import datetime
from dotenv import load_dotenv
from strategy_summary import get_strategy_summary

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

def get_content_type_for_today(strategy):
    day = datetime.now().strftime("%A").lower()
    cadence = strategy["timing"]["weekly_cadence"]
    return cadence.get(day, "static")

def parse_claude_json(response_text):
    clean = response_text.strip()
    if "```" in clean:
        parts = clean.split("```")
        clean = parts[1] if len(parts) > 1 else clean
        if clean.startswith("json"):
            clean = clean[4:]
    clean = clean.strip()
    clean = re.sub(r'(?<=[\[,])\s*#(\w+)"', r' "#\1"', clean)
    clean = re.sub(r',\s*([}\]])', r'\1', clean)
    return json.loads(clean)

def generate_content(content_type=None):
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    strategy = load_strategy()
    trends = load_latest_trends()

    if not content_type:
        content_type = get_content_type_for_today(strategy)

    print(f"Generating {content_type} post...")

    topics = [c["cluster"] for c in strategy["topics"]["ranked_clusters"]]
    trending_boost = strategy["topics"].get("trending_boost", [])
    all_topics = trending_boost + topics

    hook_style = strategy["hooks"]["by_format"].get(content_type, "how_to")
    max_hook_chars = strategy["hooks"]["max_hook_chars"]
    hashtags_config = strategy["hashtags"]
    evergreen = hashtags_config["evergreen_tags"]
    caption_config = strategy["caption"]
    word_count = caption_config["optimal_word_count"].get(
        content_type, {"min": 80, "max": 150}
    )
    preferred_days = strategy["timing"]["preferred_days"]
    preferred_hours = strategy["timing"]["preferred_hours_utc"]
    rec_day = preferred_days[0]["day"] if preferred_days else "thursday"
    rec_hour = f"{preferred_hours[0]:02d}:00" if preferred_hours else "13:00"

    trend_context = ""
    if trends:
        trend_context = f"""
Current trending topics: {', '.join(trends.get('trending_topics', [])[:3])}
Top hook styles performing well: {', '.join(trends.get('top_hook_styles', [])[:2])}
Trending audio suggestion: {trends.get('trending_audio', ['original audio'])[0]}
"""
    strategy_summary = get_strategy_summary()
    prompt = f"""You are a social media content creator for @askclaudeai — an Instagram page that posts Claude API tips and tricks for developers.

CONTENT TYPE: {content_type} post
TOPIC POOL: {', '.join(all_topics[:5])}
HOOK STYLE: {hook_style} (max {max_hook_chars} characters)
CAPTION LENGTH: {word_count['min']}-{word_count['max']} words
CTA STYLE: {caption_config['cta_style']}
EMOJI DENSITY: {caption_config['emoji_density']}
LINE BREAK STYLE: {caption_config['line_break_style']}

STRATEGY:
{strategy_summary}

TREND CONTEXT:
{trend_context}

EVERGREEN HASHTAGS TO INCLUDE: {', '.join(evergreen)}

Generate a high-quality Instagram post for developers about Claude API. The content must be:
- Genuinely useful and specific (not generic AI hype)
- Written for developers who already code
- Practical with real code examples or concrete tips
- Optimised for saves (teach something worth keeping)

IMPORTANT: Return ONLY valid JSON. Every string value must have both opening and closing double quotes. No trailing commas.

Return this exact structure:
{{
  "topic": "specific topic chosen",
  "topic_cluster": "{all_topics[0]}",
  "hook": "your hook line here (under {max_hook_chars} chars)",
  "hook_style": "{hook_style}",
  "caption": "full caption body here (no hook, no hashtags)",
  "hashtags": ["#claudeai", "#anthropic", "#aidev", "#llm", "#pythondev", "#apidevelopment", "#aiintegration", "#machinelearning", "#codinglife", "#devtips", "#programming", "#artificialintelligence", "#developer", "#techstack", "#buildwithclaude", "#promptengineering", "#automation", "#aitools"],
  "audio_suggestion": "original audio",
  "image_text": "main text for image card (max 10 words)",
  "image_subtext": "secondary text for image (max 8 words)",
  "recommended_day": "{rec_day}",
  "recommended_time_utc": "{rec_hour}"
}}"""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )

    response_text = message.content[0].text

    try:
        post_data = parse_claude_json(response_text)
    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}")
        print(f"Raw response: {response_text}")
        return None

    post_id = str(uuid.uuid4())[:8]
    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"queue/{date_str}_{post_id}.json"

    queue_entry = {
        "id": post_id,
        "content_type": content_type,
        "status": "pending",
        "created_at": datetime.now().isoformat(),
        "published_at": None,
        "instagram_media_id": None,
        "generation_inputs": {
            "strategy_snapshot": {
                "model_phase": strategy["meta"]["model_phase"],
                "timing": strategy["timing"],
                "content_format": strategy["content_format"]
            },
            "trend_report": trends,
            "topic_cluster": post_data.get("topic_cluster", "claude_api"),
            "hook_style_used": post_data.get("hook_style", hook_style)
        },
        "post": {
            "topic": post_data.get("topic", ""),
            "hook": post_data.get("hook", ""),
            "caption": post_data.get("caption", ""),
            "hashtags": post_data.get("hashtags", evergreen),
            "audio_suggestion": post_data.get("audio_suggestion", "original audio"),
            "image_text": post_data.get("image_text", ""),
            "image_subtext": post_data.get("image_subtext", "")
        },
        "scheduling": {
            "recommended_day": post_data.get("recommended_day", rec_day),
            "recommended_time_utc": post_data.get("recommended_time_utc", rec_hour),
            "actual_publish_day": None,
            "actual_publish_time_utc": None,
            "timing_deviation_hours": None
        },
        "model_prediction": {
            "predicted_engagement_rate": None,
            "predicted_reach": None,
            "prediction_confidence": None,
            "model_phase_at_prediction": strategy["meta"]["model_phase"]
        }
    }

    os.makedirs("queue", exist_ok=True)
    with open(filename, "w") as f:
        json.dump(queue_entry, f, indent=2)

    print(f"\nPost generated and saved to {filename}")
    print(f"\nHOOK: {post_data.get('hook', '')}")
    print(f"TOPIC: {post_data.get('topic', '')}")
    print(f"IMAGE TEXT: {post_data.get('image_text', '')}")
    print(f"\nCAPTION PREVIEW:\n{post_data.get('caption', '')[:200]}...")
    print(f"\nHASHTAGS: {' '.join(post_data.get('hashtags', []))}")
    print(f"\nRECOMMENDED: {post_data.get('recommended_day', '')} at {post_data.get('recommended_time_utc', '')} UTC")
# Upload image to ImgBB immediately for dashboard preview
    image_path = f"queue/images/{post_id}.png"
    if os.path.exists(image_path):
        try:
            imgbb_key = os.getenv("IMGBB_API_KEY")
            with open(image_path, "rb") as f:
                encoded = base64.b64encode(f.read()).decode("utf-8")
            r = requests.post("https://api.imgbb.com/1/upload",
                              data={"key": imgbb_key, "image": encoded})
            result = r.json()
            if result.get("success"):
                queue_entry["imgbb_url"] = result["data"]["url"]
                with open(filename, "w") as f:
                    json.dump(queue_entry, f, indent=2)
                print(f"Image uploaded to ImgBB: {queue_entry['imgbb_url']}")
        except Exception as e:
            print(f"ImgBB upload skipped: {e}")

    # Send email notification
    try:
        from notify import notify_post_ready
        notify_post_ready(queue_entry)
    except Exception as e:
        print(f"Notification skipped: {e}")

    return filename, queue_entry

if __name__ == "__main__":
    import sys
    content_type = sys.argv[1] if len(sys.argv) > 1 else None
    generate_content(content_type)