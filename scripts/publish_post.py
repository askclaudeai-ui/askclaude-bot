import json
import os
import sys
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

INSTAGRAM_USER_ID    = os.getenv("INSTAGRAM_USER_ID")
INSTAGRAM_TOKEN      = os.getenv("INSTAGRAM_ACCESS_TOKEN")
IMGBB_API_KEY        = os.getenv("IMGBB_API_KEY")
GRAPH_API_VERSION    = "v19.0"
GRAPH_BASE           = f"https://graph.facebook.com/{GRAPH_API_VERSION}"

def upload_to_imgbb(image_path):
    """Upload image to ImgBB and return public URL."""
    print(f"Uploading image to ImgBB: {image_path}")
    with open(image_path, "rb") as f:
        image_data = f.read()
    import base64
    encoded = base64.b64encode(image_data).decode("utf-8")
    response = requests.post(
        "https://api.imgbb.com/1/upload",
        data={
            "key": IMGBB_API_KEY,
            "image": encoded,
        }
    )
    result = response.json()
    if not result.get("success"):
        raise Exception(f"ImgBB upload failed: {result}")
    url = result["data"]["url"]
    print(f"Image uploaded: {url}")
    return url

def create_media_container(image_url, caption):
    """Step 1: Create Instagram media container."""
    print("Creating Instagram media container...")
    response = requests.post(
        f"{GRAPH_BASE}/{INSTAGRAM_USER_ID}/media",
        params={
            "image_url":    image_url,
            "caption":      caption,
            "access_token": INSTAGRAM_TOKEN,
        }
    )
    result = response.json()
    if "id" not in result:
        raise Exception(f"Failed to create container: {result}")
    container_id = result["id"]
    print(f"Container created: {container_id}")
    return container_id

def publish_container(container_id):
    """Step 2: Publish the media container."""
    print("Publishing to Instagram...")
    response = requests.post(
        f"{GRAPH_BASE}/{INSTAGRAM_USER_ID}/media_publish",
        params={
            "creation_id":  container_id,
            "access_token": INSTAGRAM_TOKEN,
        }
    )
    result = response.json()
    if "id" not in result:
        raise Exception(f"Failed to publish: {result}")
    media_id = result["id"]
    print(f"Published! Instagram media ID: {media_id}")
    return media_id

def build_full_caption(post):
    """Combine hook + caption + hashtags into full Instagram caption."""
    hook     = post["post"].get("hook", "")
    caption  = post["post"].get("caption", "")
    hashtags = post["post"].get("hashtags", [])
    parts = []
    if hook:
        parts.append(hook)
    if caption:
        parts.append(caption)
    if hashtags:
        parts.append("\n" + " ".join(hashtags))
    return "\n\n".join(parts)

def find_oldest_approved():
    """Find the oldest approved post in the queue."""
    queue_dir = "queue"
    candidates = []
    for fname in os.listdir(queue_dir):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(queue_dir, fname)
        try:
            with open(path, "r") as f:
                post = json.load(f)
            if post.get("status") == "approved":
                candidates.append((post["created_at"], path, post))
        except:
            continue
    if not candidates:
        return None, None, None
    candidates.sort(key=lambda x: x[0])
    _, path, post = candidates[0]
    return path, post, post["id"]

def update_queue_file(path, post, media_id):
    """Mark post as published and record the Instagram media ID."""
    post["status"]              = "published"
    post["published_at"]        = datetime.now().isoformat()
    post["instagram_media_id"]  = media_id
    post["scheduling"]["actual_publish_day"]      = datetime.now().strftime("%A").lower()
    post["scheduling"]["actual_publish_time_utc"] = datetime.now().strftime("%H:%M")

    if post["scheduling"].get("recommended_time_utc"):
        try:
            rec_h = int(post["scheduling"]["recommended_time_utc"].split(":")[0])
            act_h = datetime.now().hour
            post["scheduling"]["timing_deviation_hours"] = act_h - rec_h
        except:
            pass

    with open(path, "w") as f:
        json.dump(post, f, indent=2)
    print(f"Queue file updated: {path}")

def publish_post(dry_run=False):
    # Find oldest approved post
    path, post, post_id = find_oldest_approved()
    if not post:
        print("No approved posts found. Approve a post in the dashboard first.")
        return False

    content_type = post.get("content_type", "static")
    print(f"\nPublishing post: {post_id}")
    print(f"Type: {content_type}")
    print(f"Hook: {post['post'].get('hook', '')}")

    if content_type != "static":
        print(f"Content type '{content_type}' not yet supported by publisher. Only 'static' supported currently.")
        return False

    # Find image
    image_path = f"queue/images/{post_id}.png"
    if not os.path.exists(image_path):
        print(f"Image not found: {image_path}")
        print("Run generate_image.py first.")
        return False

    # Build caption
    full_caption = build_full_caption(post)
    print(f"\nCaption preview ({len(full_caption)} chars):")
    print(full_caption[:300] + "..." if len(full_caption) > 300 else full_caption)

    if dry_run:
        print("\n--- DRY RUN --- Nothing was posted to Instagram.")
        print(f"Would upload: {image_path}")
        print(f"Would post caption ({len(full_caption)} chars)")
        return True

    # Upload image
    image_url = upload_to_imgbb(image_path)

    # Create container
    container_id = create_media_container(image_url, full_caption)

    # Publish
    media_id = publish_container(container_id)

    # Update queue file
    update_queue_file(path, post, media_id)

    print(f"\nSuccess! Post published to Instagram.")
    print(f"Instagram media ID: {media_id}")
    print(f"View at: https://www.instagram.com/askclaude")
    return True

if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    if dry_run:
        print("Running in DRY RUN mode — nothing will be posted.")
    publish_post(dry_run=dry_run)