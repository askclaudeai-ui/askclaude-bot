import anthropic
import json
import os
import re
import sys
from dotenv import load_dotenv

load_dotenv()

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

def regenerate_post(post_id, feedback=None):
    """
    Rewrite a post based on optional feedback notes.
    If feedback is None, just regenerates the image from existing content.
    """
    # Find the queue file
    queue_dir = "queue"
    post_path = None
    post = None
    for fname in os.listdir(queue_dir):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(queue_dir, fname)
        try:
            with open(path, "r") as f:
                data = json.load(f)
            if data.get("id") == post_id:
                post_path = path
                post = data
                break
        except:
            continue

    if not post:
        print(f"Post {post_id} not found")
        return False

    # If feedback provided, rewrite the post content via Claude
    if feedback and feedback.strip():
        print(f"Rewriting post based on feedback: {feedback}")
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

        current = post["post"]
        content_type = post["content_type"]

        prompt = f"""You are a social media content creator for @askclaude — an Instagram page posting Claude API tips for developers.

You previously wrote this {content_type} Instagram post:

HOOK: {current.get('hook', '')}

CAPTION: {current.get('caption', '')}

HASHTAGS: {' '.join(current.get('hashtags', []))}

IMAGE TEXT: {current.get('image_text', '')}
IMAGE SUBTEXT: {current.get('image_subtext', '')}

The reviewer has given this feedback:
"{feedback}"

Please rewrite the post incorporating this feedback. Keep it:
- Developer-focused and technically accurate
- Practical with real value
- Optimised for saves

Return ONLY valid JSON with this exact structure:
{{
  "hook": "rewritten hook (max 90 chars)",
  "caption": "rewritten caption body (no hook, no hashtags)",
  "hashtags": ["#claudeai", "#anthropic", "#aidev", "#llm", "#pythondev", "#apidevelopment", "#aiintegration", "#machinelearning", "#codinglife", "#devtips", "#programming", "#artificialintelligence", "#developer", "#techstack", "#buildwithclaude", "#promptengineering", "#automation", "#aitools"],
  "image_text": "main image text (max 10 words)",
  "image_subtext": "secondary image text (max 8 words)",
  "topic": "updated topic description"
}}"""

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )

        try:
            new_data = parse_claude_json(message.content[0].text)
            post["post"]["hook"]         = new_data.get("hook",         current.get("hook"))
            post["post"]["caption"]      = new_data.get("caption",      current.get("caption"))
            post["post"]["hashtags"]     = new_data.get("hashtags",     current.get("hashtags"))
            post["post"]["image_text"]   = new_data.get("image_text",   current.get("image_text"))
            post["post"]["image_subtext"]= new_data.get("image_subtext",current.get("image_subtext"))
            post["post"]["topic"]        = new_data.get("topic",        current.get("topic"))
            print("Post content rewritten successfully")
        except Exception as e:
            print(f"Error parsing Claude response: {e}")
            return False

    # Save updated post content
    with open(post_path, "w") as f:
        json.dump(post, f, indent=2)

    # Regenerate image
    print("Regenerating image...")
    from generate_image import generate_image
    try:
        image_path = generate_image(post_path)
        print(f"Image regenerated: {image_path}")
        return True
    except Exception as e:
        print(f"Error regenerating image: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/regenerate_post.py <post_id> [feedback]")
        sys.exit(1)
    post_id  = sys.argv[1]
    feedback = sys.argv[2] if len(sys.argv) > 2 else None
    regenerate_post(post_id, feedback)