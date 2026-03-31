import json
import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

INSTAGRAM_USER_ID = os.getenv("INSTAGRAM_USER_ID")
INSTAGRAM_TOKEN   = os.getenv("INSTAGRAM_ACCESS_TOKEN")
GRAPH_BASE        = "https://graph.facebook.com/v19.0"

def get(endpoint, params={}):
    params["access_token"] = INSTAGRAM_TOKEN
    r = requests.get(f"{GRAPH_BASE}/{endpoint}", params=params)
    return r.json()

def fetch_account_summary():
    """Fetch account-level metrics."""
    print("Fetching account summary...")
    result = get(f"{INSTAGRAM_USER_ID}", params={
        "fields": "followers_count,media_count,name"
    })
    return {
        "followers_count": result.get("followers_count", 0),
        "media_count":     result.get("media_count", 0),
        "name":            result.get("name", "")
    }

def fetch_published_posts():
    """Get all published posts from the queue."""
    queue_dir = "queue"
    posts = []
    for fname in os.listdir(queue_dir):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(queue_dir, fname)
        try:
            with open(path, "r") as f:
                post = json.load(f)
            if (post.get("status") == "published"
                    and post.get("instagram_media_id")):
                posts.append(post)
        except:
            continue
    return sorted(posts, key=lambda x: x.get("published_at",""))

def fetch_post_insights(media_id, content_type="static"):
    """Fetch insights for a single post."""
    print(f"  Fetching insights for {media_id}...")

    # Basic metrics available for all post types
    base_metrics = "reach,impressions,saved,likes,comments"

    # Reels have extra metrics
    if content_type == "reel":
        metrics = base_metrics + ",plays,total_interactions"
    else:
        metrics = base_metrics + ",shares"

    result = get(f"{media_id}/insights", params={"metric": metrics})

    if "error" in result:
        print(f"    Error: {result['error'].get('message','unknown')}")
        return None

    insights = {}
    for item in result.get("data", []):
        insights[item["name"]] = item.get("values",[{}])[-1].get("value", 0) \
                                  if "values" in item else item.get("value", 0)

    # Also fetch like/comment counts directly from media object
    media = get(media_id, params={
        "fields": "like_count,comments_count,timestamp,media_type"
    })
    insights["like_count"]     = media.get("like_count", 0)
    insights["comments_count"] = media.get("comments_count", 0)
    insights["timestamp"]      = media.get("timestamp", "")

    return insights

def compute_rates(insights, post):
    """Compute engagement rates from raw metrics."""
    reach = insights.get("reach", 0)
    if reach == 0:
        return {}

    saves    = insights.get("saved", 0)
    likes    = insights.get("like_count", insights.get("likes", 0))
    comments = insights.get("comments_count", insights.get("comments", 0))
    shares   = insights.get("shares", 0)

    total_engagement = likes + saves + comments + shares

    return {
        "engagement_rate": round(total_engagement / reach, 4),
        "save_rate":       round(saves / reach, 4),
        "like_rate":       round(likes / reach, 4),
        "comment_rate":    round(comments / reach, 4),
        "share_rate":      round(shares / reach, 4),
    }

def is_72h_old(post):
    """Check if post is at least 72 hours old (metrics stabilised)."""
    published = post.get("published_at", "")
    if not published:
        return False
    try:
        pub_dt  = datetime.fromisoformat(published)
        age     = datetime.now() - pub_dt
        return age >= timedelta(hours=72)
    except:
        return False

def load_training_data():
    path = "data/model/training.json"
    if not os.path.exists(path):
        return []
    with open(path, "r") as f:
        return json.load(f)

def already_in_training(post_id, training_data):
    return any(r.get("post_id") == post_id for r in training_data)

def append_training_record(post, insights, rates):
    """Build and append a training record for the model."""
    training_data = load_training_data()

    if already_in_training(post["id"], training_data):
        print(f"    Already in training data — skipping")
        return

    scheduling = post.get("scheduling", {})
    gen_inputs = post.get("generation_inputs", {})
    snap       = gen_inputs.get("strategy_snapshot", {})

    record = {
        "post_id":        post["id"],
        "recorded_at":    datetime.now().isoformat(),
        "published_at":   post.get("published_at", ""),

        # Features
        "content_type":   post.get("content_type", "static"),
        "topic_cluster":  gen_inputs.get("topic_cluster", ""),
        "hook_style":     gen_inputs.get("hook_style_used", ""),
        "publish_day":    scheduling.get("actual_publish_day", ""),
        "publish_hour":   int(scheduling.get("actual_publish_time_utc","0:00").split(":")[0]),
        "timing_deviation_hours": scheduling.get("timing_deviation_hours", 0),
        "model_phase":    snap.get("model_phase", "bootstrap"),
        "caption_words":  len(post.get("post",{}).get("caption","").split()),
        "hashtag_count":  len(post.get("post",{}).get("hashtags",[])),

        # Raw metrics
        "reach":          insights.get("reach", 0),
        "impressions":    insights.get("impressions", 0),
        "saves":          insights.get("saved", 0),
        "likes":          insights.get("like_count", 0),
        "comments":       insights.get("comments_count", 0),
        "shares":         insights.get("shares", 0),

        # Computed rates (targets for model)
        "engagement_rate": rates.get("engagement_rate", 0),
        "save_rate":       rates.get("save_rate", 0),
        "like_rate":       rates.get("like_rate", 0),
        "comment_rate":    rates.get("comment_rate", 0),
        "share_rate":      rates.get("share_rate", 0),

        # Model prediction vs actual
        "predicted_engagement_rate": post.get("model_prediction",{}).get(
            "predicted_engagement_rate"),
        "prediction_error": None
    }

    # Compute prediction error if prediction exists
    if record["predicted_engagement_rate"] is not None:
        record["prediction_error"] = round(
            abs(record["engagement_rate"] -
                record["predicted_engagement_rate"]), 4)

    training_data.append(record)

    os.makedirs("data/model", exist_ok=True)
    with open("data/model/training.json", "w") as f:
        json.dump(training_data, f, indent=2)
    print(f"    Training record saved (total: {len(training_data)})")

def update_queue_file_with_insights(post, insights, rates):
    """Write insights back into the queue JSON file."""
    queue_dir = "queue"
    for fname in os.listdir(queue_dir):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(queue_dir, fname)
        try:
            with open(path, "r") as f:
                data = json.load(f)
            if data.get("id") == post["id"]:
                data["actual_metrics"] = {
                    **insights,
                    **rates,
                    "fetched_at": datetime.now().isoformat()
                }
                with open(path, "w") as f:
                    json.dump(data, f, indent=2)
                return
        except:
            continue

def fetch_insights():
    print("=" * 50)
    print("Fetching Instagram insights")
    print("=" * 50)

    # Account summary
    account = fetch_account_summary()
    print(f"\nAccount: {account['name']}")
    print(f"Followers: {account['followers_count']}")
    print(f"Total posts: {account['media_count']}")

    # Fetch insights for each published post
    posts = fetch_published_posts()
    print(f"\nPublished posts in queue: {len(posts)}")

    post_insights = []
    skipped = 0

    for post in posts:
        post_id    = post["id"]
        media_id   = post["instagram_media_id"]
        content_type = post.get("content_type", "static")

        print(f"\nPost {post_id} ({content_type})")

        # Only fetch if 72h+ old
        if not is_72h_old(post):
            age_h = (datetime.now() -
                     datetime.fromisoformat(post.get("published_at","2000-01-01"))).seconds // 3600
            print(f"  Too recent ({age_h}h old) — skipping")
            skipped += 1
            continue

        insights = fetch_post_insights(media_id, content_type)
        if not insights:
            continue

        rates = compute_rates(insights, post)
        print(f"  Reach: {insights.get('reach',0)}")
        print(f"  Saves: {insights.get('saved',0)}")
        print(f"  Engagement rate: {rates.get('engagement_rate',0):.2%}")
        print(f"  Save rate: {rates.get('save_rate',0):.2%}")

        # Write back to queue file
        update_queue_file_with_insights(post, insights, rates)

        # Append to training data
        append_training_record(post, insights, rates)

        post_insights.append({
            "post_id":      post_id,
            "content_type": content_type,
            "insights":     insights,
            "rates":        rates
        })

    # Save weekly insights file
    date_str = datetime.now().strftime("%Y-%m-%d")
    out_path = f"data/insights/{date_str}.json"
    os.makedirs("data/insights", exist_ok=True)

    output = {
        "fetched_at":    datetime.now().isoformat(),
        "account":       account,
        "posts_fetched": len(post_insights),
        "posts_skipped": skipped,
        "post_insights": post_insights
    }

    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n{'='*50}")
    print(f"Done. Insights saved to {out_path}")
    print(f"Posts fetched: {len(post_insights)}")
    print(f"Posts skipped (too recent): {skipped}")
    print(f"Training records: {len(load_training_data())}")

    return output

if __name__ == "__main__":
    fetch_insights()