import json
import os
import sys
import shutil
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

INSTAGRAM_USER_ID = os.getenv("INSTAGRAM_USER_ID")
INSTAGRAM_TOKEN   = os.getenv("INSTAGRAM_ACCESS_TOKEN")
IMGBB_API_KEY     = os.getenv("IMGBB_API_KEY")
GRAPH_API_VERSION = "v19.0"
GRAPH_BASE        = f"https://graph.facebook.com/{GRAPH_API_VERSION}"

def upload_to_imgbb(image_path):
    print(f"Uploading image to ImgBB: {image_path}")
    import base64
    with open(image_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")
    response = requests.post(
        "https://api.imgbb.com/1/upload",
        data={"key": IMGBB_API_KEY, "image": encoded}
    )
    result = response.json()
    if not result.get("success"):
        raise Exception(f"ImgBB upload failed: {result}")
    url = result["data"]["url"]
    print(f"Image uploaded: {url}")
    return url

def create_media_container(image_url, caption):
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
    hook     = post["post"].get("hook", "")
    caption  = post["post"].get("caption", "")
    hashtags = post["post"].get("hashtags", [])
    parts = []
    if hook:    parts.append(hook)
    if caption: parts.append(caption)
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
    """Fallback — save image and caption to Desktop for manual posting."""
    out_dir  = os.path.expanduser("~/Desktop/askclaude_to_post")
    os.makedirs(out_dir, exist_ok=True)

    date_str = datetime.now().strftime("%Y-%m-%d_%H%M")
    img_dest = f"{out_dir}/{date_str}.png"
    cap_dest = f"{out_dir}/{date_str}_caption.txt"

    shutil.copy(image_path, img_dest)
    with open(cap_dest, "w") as f:
        f.write(full_caption)

    print("\n" + "="*50)
    print("MANUAL PUBLISH REQUIRED")
    print("="*50)
    print(f"\nImage saved to:   {img_dest}")
    print(f"Caption saved to: {cap_dest}")
    print("\nSteps:")
    print("1. Open Instagram app on your phone")
    print("2. Tap + to create a new post")
    print("3. Select the image from Desktop/askclaude_to_post")
    print("4. Open the caption .txt file and copy the text")
    print("5. Paste into Instagram caption field and post")
    print("="*50)

    # Mark as ready_to_post in queue
    post["status"] = "ready_to_post"
    post["manual_publish_package"] = {
        "image_path":   img_dest,
        "caption_path": cap_dest,
        "prepared_at":  datetime.now().isoformat()
    }
    with open(path, "w") as f:
        json.dump(post, f, indent=2)

    return img_dest, cap_dest

def publish_post(dry_run=False):
    path, post, post_id = find_oldest_approved()
    if not post:
        print("No approved posts found. Approve a post in the dashboard first.")
        return False

    content_type = post.get("content_type", "static")
    print(f"\nPublishing post: {post_id}")
    print(f"Type: {content_type}")
    print(f"Hook: {post['post'].get('hook', '')}")

    if content_type != "static":
        print(f"Content type '{content_type}' not yet supported. Only 'static' supported.")
        return False

    # Use Cloudinary URL directly if available — image files not stored in repo
cloudinary_url = post.get("cloudinary_image_url")
imgbb_url      = post.get("imgbb_url", "")
existing_url   = cloudinary_url or (imgbb_url if "cloudinary" in imgbb_url else None)

image_path = f"queue/images/{post_id}.png"
if not existing_url and not os.path.exists(image_path):
    print(f"Image not found: {image_path}")
    print("No Cloudinary URL in queue file either.")
    return False

    full_caption = build_full_caption(post)
    print(f"\nCaption preview ({len(full_caption)} chars):")
    print(full_caption[:300] + "..." if len(full_caption) > 300 else full_caption)

    if dry_run:
        print("\n--- DRY RUN --- Nothing posted to Instagram.")
        print(f"Would upload: {image_path}")
        print(f"Would post caption ({len(full_caption)} chars)")
        return True

    try:
       
        # Upload image to Cloudinary — Late API can fetch from Cloudinary
        # ImgBB blocks external service requests
        # Use existing Cloudinary URL if available — avoids re-uploading
        existing_cloudinary = post.get("cloudinary_image_url")
        # Use existing Cloudinary URL — avoids needing local image file
        if existing_url:
            image_url = existing_url
            print(f"Using existing Cloudinary URL: {image_url}")
        elif os.path.exists(image_path):
            # Local run — upload to Cloudinary
            try:
                import sys
                sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
                from upload_media import upload_image_cloudinary_feed
                image_url = upload_image_cloudinary_feed(image_path)
                print(f"Uploaded to Cloudinary: {image_url}")
                post["cloudinary_image_url"] = image_url
                post["imgbb_url"]             = image_url
                with open(path, "w") as f:
                    json.dump(post, f, indent=2)
            except Exception as e:
                raise Exception(f"Cloudinary upload failed: {e}")
        else:
            raise Exception("No image URL and no local image file found")
        # Publish via Late API
        late_key        = os.getenv("LATE_API_KEY")
        late_account_id = os.getenv("LATE_ACCOUNT_ID")

        if not late_key or not late_account_id:
            raise Exception("LATE_API_KEY or LATE_ACCOUNT_ID not set in .env")

        print("Publishing via Late API...")
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
        result = r.json()
        print(f"Late API status: {r.status_code}")
        print(f"Late API full response: {json.dumps(result, indent=2)}")

        # Extract post ID from response
        post_obj = result.get("post", {})
        media_id = post_obj.get("_id")

        if r.status_code in (200, 201) and media_id:
            update_queue_file(path, post, media_id)
            print(f"\nSuccess! Published via Late API.")
            print(f"Post ID: {media_id}")
            return True
        else:
            raise Exception(f"Late API error: {result.get('message', result)}")

    except Exception as e:
        print(f"\nPublish failed: {e}")
        print("Falling back to manual publish package...")
        notify_manual_publish(path, post, image_path, full_caption)
        return False

if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    if dry_run:
        print("Running in DRY RUN mode — nothing will be posted.")
    publish_post(dry_run=dry_run)