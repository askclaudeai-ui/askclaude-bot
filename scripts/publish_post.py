import json
import os
import sys
import shutil
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

IMGBB_API_KEY = os.getenv("IMGBB_API_KEY")

def build_full_caption(post):
    hook     = post["post"].get("hook", "")
    caption  = post["post"].get("caption", "")
    hashtags = post["post"].get("hashtags", [])
    parts = []
    if hook:     parts.append(hook)
    if caption:  parts.append(caption)
    if hashtags: parts.append("\n" + " ".join(hashtags))
    return "\n\n".join(parts)

def find_oldest_approved():
    queue_dir  = "queue"
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
    post["status"]             = "published"
    post["published_at"]       = datetime.now().isoformat()
    post["instagram_media_id"] = media_id
    post["scheduling"]["actual_publish_day"]      = datetime.now().strftime("%A").lower()
    post["scheduling"]["actual_publish_time_utc"] = datetime.now().strftime("%H:%M")
    try:
        rec_h = int(post["scheduling"]["recommended_time_utc"].split(":")[0])
        act_h = datetime.now().hour
        post["scheduling"]["timing_deviation_hours"] = act_h - rec_h
    except:
        pass
    with open(path, "w") as f:
        json.dump(post, f, indent=2)
    print(f"Queue file updated: {path}")

def notify_manual_publish(path, post, image_path, full_caption):
    out_dir  = os.path.expanduser("~/Desktop/askclaude_to_post")
    os.makedirs(out_dir, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d_%H%M")
    img_dest = f"{out_dir}/{date_str}.png"
    cap_dest = f"{out_dir}/{date_str}_caption.txt"
    if image_path and os.path.exists(image_path):
        shutil.copy(image_path, img_dest)
    with open(cap_dest, "w") as f:
        f.write(full_caption)
    print("\n" + "="*50)
    print("MANUAL PUBLISH REQUIRED")
    print("="*50)
    print(f"\nImage saved to:   {img_dest}")
    print(f"Caption saved to: {cap_dest}")
    print("="*50)
    post["status"] = "ready_to_post"
    with open(path, "w") as f:
        json.dump(post, f, indent=2)
    return img_dest, cap_dest

def get_image_url(post, post_id, path):
    """Get the best available image URL — Cloudinary preferred."""
    # 1. Cloudinary image URL (best — works everywhere)
    if post.get("cloudinary_image_url"):
        return post["cloudinary_image_url"]

    # 2. imgbb_url that is actually a Cloudinary URL
    imgbb = post.get("imgbb_url", "")
    if imgbb and "cloudinary" in imgbb:
        return imgbb

    # 3. Upload local file to Cloudinary
    local_path = f"queue/images/{post_id}.png"
    if os.path.exists(local_path):
        try:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from upload_media import upload_image_cloudinary_feed
            url = upload_image_cloudinary_feed(local_path)
            print(f"Uploaded to Cloudinary: {url}")
            post["cloudinary_image_url"] = url
            post["imgbb_url"]             = url
            with open(path, "w") as f:
                json.dump(post, f, indent=2)
            return url
        except Exception as e:
            print(f"Cloudinary upload failed: {e}")

    # 4. Fall back to ImgBB URL (may not work with Late API)
    if imgbb:
        print(f"Warning: using ImgBB URL — Late API may reject it")
        return imgbb

    return None

def publish_post(dry_run=False):
    path, post, post_id = find_oldest_approved()
    if not post:
        print("No approved posts found. Approve a post in the dashboard first.")
        return False

    content_type = post.get("content_type", "static")
    print(f"\nPublishing post: {post_id}")
    print(f"Type: {content_type}")
    print(f"Hook: {post['post'].get('hook', '')}")

    full_caption = build_full_caption(post)
    print(f"\nCaption preview ({len(full_caption)} chars):")
    print(full_caption[:300] + "..." if len(full_caption) > 300 else full_caption)

    if dry_run:
        print("\n--- DRY RUN --- Nothing posted to Instagram.")
        return True

    # Get image URL
    image_url  = get_image_url(post, post_id, path)
    image_path = f"queue/images/{post_id}.png"

    if not image_url:
        print("No image URL available — cannot publish.")
        return False

    try:
        late_key        = os.getenv("LATE_API_KEY")
        late_account_id = os.getenv("LATE_ACCOUNT_ID")

        if not late_key or not late_account_id:
            raise Exception("LATE_API_KEY or LATE_ACCOUNT_ID not set")

        print(f"Publishing via Late API...")
        print(f"Image URL: {image_url}")

        r = requests.post(
            "https://getlate.dev/api/v1/posts",
            headers={
                "Authorization": f"Bearer {late_key}",
                "Content-Type":  "application/json"
            },
            json={
                "platforms": [{
                    "platform":  "instagram",
                    "accountId": late_account_id
                }],
                "content":    full_caption,
                "mediaItems": [{"type": "image", "url": image_url}],
                "publishNow": True
            }
        )
        result   = r.json()
        post_obj = result.get("post", {})
        media_id = post_obj.get("_id")

        print(f"Late API status: {r.status_code}")

        if r.status_code in (200, 201) and media_id:
            update_queue_file(path, post, media_id)
            print(f"\nSuccess! Published via Late API.")
            print(f"Post ID: {media_id}")
            return True
        elif r.status_code == 207:
            # 207 means created but publishing pending — treat as success
            if media_id:
                update_queue_file(path, post, media_id)
                print(f"\nPost scheduled — Late API will publish shortly.")
                return True
            raise Exception(f"Late API 207: {result.get('message', result)}")
        else:
            raise Exception(f"Late API error {r.status_code}: {result.get('message', result)}")

    except Exception as e:
        print(f"\nPublish failed: {e}")
        img_path = image_path if os.path.exists(image_path) else None
        notify_manual_publish(path, post, img_path, full_caption)
        return False

if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    if dry_run:
        print("Running in DRY RUN mode — nothing will be posted.")
    publish_post(dry_run=dry_run)