import anthropic
import json
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

def research_trends():
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    prompt = """You are a social media strategist specialising in developer content on Instagram.

Research the current Instagram landscape for developer and AI content and provide a trend report covering:

1. TRENDING TOPICS: What AI/Claude/LLM topics are developers talking about right now?
2. HASHTAGS: Provide 20 relevant hashtags split into:
   - Primary (3 large reach): very popular dev/AI tags
   - Niche (10 targeted): Claude-specific and LLM dev tags  
   - Evergreen (5 stable): always-relevant dev tags
3. CONTENT FORMATS: What content formats are performing well for dev accounts right now?
4. BEST POSTING TIMES: Best days and times UTC for developer audience engagement
5. TRENDING AUDIO: Any trending audio/sounds suitable for dev tutorial Reels
6. HOOK STYLES: What opening hooks are getting most engagement in dev content?

Return your response as valid JSON with this exact structure:
{
  "trending_topics": ["topic1", "topic2", "topic3", "topic4", "topic5"],
  "hashtags": {
    "primary": ["#tag1", "#tag2", "#tag3"],
    "niche": ["#tag1", "#tag2", "#tag3", "#tag4", "#tag5", "#tag6", "#tag7", "#tag8", "#tag9", "#tag10"],
    "evergreen": ["#tag1", "#tag2", "#tag3", "#tag4", "#tag5"]
  },
  "best_posting_times": [
    {"day": "thursday", "time_utc": "13:00", "reason": "why"},
    {"day": "monday", "time_utc": "09:00", "reason": "why"}
  ],
  "trending_audio": ["audio name 1", "audio name 2"],
  "top_hook_styles": ["hook style 1", "hook style 2", "hook style 3"],
  "viral_formats": ["format 1", "format 2"],
  "research_date": "TODAY_DATE"
}

Replace TODAY_DATE with today's actual date. Return only the JSON, no other text."""

    prompt = prompt.replace("TODAY_DATE", datetime.now().strftime("%Y-%m-%d"))

    print("Researching Instagram trends...")

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1500,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": prompt}]
    )

    # Extract text from response (may include tool use blocks)
    response_text = ""
    for block in message.content:
        if hasattr(block, "text"):
            response_text += block.text

    # Parse JSON
    try:
        # Strip markdown code blocks if present
        clean = response_text.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        trend_data = json.loads(clean.strip())
    except json.JSONDecodeError:
        print("Warning: Could not parse JSON response, using raw text")
        trend_data = {"raw": response_text, "research_date": datetime.now().strftime("%Y-%m-%d")}

    # Save to file
    os.makedirs("data", exist_ok=True)
    output_path = f"data/trends_{datetime.now().strftime('%Y-%m-%d')}.json"
    with open(output_path, "w") as f:
        json.dump(trend_data, f, indent=2)

    print(f"Trends saved to {output_path}")
    print(json.dumps(trend_data, indent=2))
    return trend_data

if __name__ == "__main__":
    research_trends()
