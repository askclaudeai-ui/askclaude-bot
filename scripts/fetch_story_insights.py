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

def fetch_published_stories():
    """Get all published stories from the queue."""
    stories_dir = "queue/stories"
    stories = []
    if not os.path.exists(stories_dir):
        return stories
    for fname in os.listdir(stories_dir):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(stories_dir, fname)
        try:
            with open(path, "r") as f:
                story = json.load(f)
            if (story.get("status") == "published"
                    and story.get("instagram_media_id")):
                stories.append((path, story))
        except:
            continue
    return sorted(stories, key=lambda x: x[1].get("published_at",""))

def fetch_story_insights(media_id):
    """
    Fetch Story-specific metrics.
    Stories expire after 24h — insights must be fetched promptly.
    """
    print(f"  Fetching story insights for {media_id}...")

    # Story insight fields
    metrics = "exits,impressions,reach,replies,taps_forward,taps_back"
    result  = get(f"{media_id}/insights", params={"metric": metrics})

    if "error" in result:
        print(f"    Error: {result['error'].get('message','unknown')}")
        return None

    insights = {}
    for item in result.get("data", []):
        insights[item["name"]] = item.get("value", 0)

    return insights

def compute_story_rates(insights):
    """Compute story-specific rates."""
    impressions = insights.get("impressions", 0)
    if impressions == 0:
        return {}

    exits    = insights.get("exits", 0)
    replies  = insights.get("replies", 0)
    taps_fwd = insights.get("taps_forward", 0)
    taps_bck = insights.get("taps_back", 0)

    return {
        "completion_rate":   round(1 - (exits / impressions), 4),
        "interaction_rate":  round((replies + taps_bck) / impressions, 4),
        "exit_rate":         round(exits / impressions, 4),
        "reply_rate":        round(replies / impressions, 4),
        "taps_forward_rate": round(taps_fwd / impressions, 4),
        "taps_back_rate":    round(taps_bck / impressions, 4),
    }

def is_within_48h(story):
    """
    Stories expire after 24h — fetch within 48h window.
    After 48h insights may no longer be available.
    """
    published = story.get("published_at", "")
    if not published:
        return False
    try:
        pub_dt = datetime.fromisoformat(published)
        age    = datetime.now() - pub_dt
        return timedelta(hours=1) <= age <= timedelta(hours=48)
    except:
        return False

def load_story_training():
    path = "data/model/story_training.json"
    if not os.path.exists(path):
        return []
    with open(path, "r") as f:
        return json.load(f)

def already_in_training(story_id, training_data):
    return any(r.get("story_id") == story_id for r in training_data)

def append_story_training_record(story, insights, rates):
    """Append to story training dataset."""
    training_data = load_story_training()

    if already_in_training(story["id"], training_data):
        print(f"    Already in story training — skipping")
        return

    record = {
        "story_id":       story["id"],
        "recorded_at":    datetime.now().isoformat(),
        "published_at":   story.get("published_at", ""),

        # Features
        "story_type":     story.get("story_type", ""),
        "parent_post_id": story.get("parent_post_id"),
        "slide_count":    story.get("post",{}).get("slide_count", 1),
        "publish_hour":   int(story.get("scheduling",{}).get(
            "actual_publish_time","0:00").split(":")[0]),

        # Raw metrics
        "impressions":    insights.get("impressions", 0),
        "reach":          insights.get("reach", 0),
        "exits":          insights.get("exits", 0),
        "replies":        insights.get("replies", 0),
        "taps_forward":   insights.get("taps_forward", 0),
        "taps_back":      insights.get("taps_back", 0),

        # Computed rates (targets for story model)
        "completion_rate":   rates.get("completion_rate", 0),
        "interaction_rate":  rates.get("interaction_rate", 0),
        "exit_rate":         rates.get("exit_rate", 0),
        "reply_rate":        rates.get("reply_rate", 0),
        "taps_forward_rate": rates.get("taps_forward_rate", 0),
        "taps_back_rate":    rates.get("taps_back_rate", 0),
    }

    training_data.append(record)

    os.makedirs("data/model", exist_ok=True)
    with open("data/model/story_training.json", "w") as f:
        json.dump(training_data, f, indent=2)
    print(f"    Story training record saved (total: {len(training_data)})")

def update_story_queue_file(path, story, insights, rates):
    """Write insights back into the story queue JSON."""
    try:
        with open(path, "r") as f:
            data = json.load(f)
        data["actual_metrics"] = {
            **insights,
            **rates,
            "fetched_at": datetime.now().isoformat()
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"    Could not update queue file: {e}")

def fetch_story_insights_all():
    print("=" * 50)
    print("Fetching Story insights")
    print("=" * 50)

    stories = fetch_published_stories()
    print(f"\nPublished stories in queue: {len(stories)}")

    fetched = 0
    skipped = 0
    expired = 0

    story_insights_list = []

    for path, story in stories:
        story_id   = story["id"]
        story_type = story.get("story_type", "")
        media_id   = story.get("instagram_media_id")

        print(f"\nStory {story_id} ({story_type})")

        # Check if within fetch window
        published = story.get("published_at","")
        if published:
            try:
                pub_dt = datetime.fromisoformat(published)
                age    = datetime.now() - pub_dt
                if age > timedelta(hours=48):
                    print(f"  Expired ({age.days}d old) — insights no longer available")
                    expired += 1
                    continue
                if age < timedelta(hours=1):
                    print(f"  Too fresh — wait at least 1 hour")
                    skipped += 1
                    continue
            except:
                pass

        insights = fetch_story_insights(media_id)
        if not insights:
            skipped += 1
            continue

        rates = compute_story_rates(insights)

        print(f"  Impressions:    {insights.get('impressions',0)}")
        print(f"  Reach:          {insights.get('reach',0)}")
        print(f"  Exits:          {insights.get('exits',0)}")
        print(f"  Replies:        {insights.get('replies',0)}")
        print(f"  Completion:     {rates.get('completion_rate',0):.2%}")
        print(f"  Interaction:    {rates.get('interaction_rate',0):.2%}")

        update_story_queue_file(path, story, insights, rates)
        append_story_training_record(story, insights, rates)

        story_insights_list.append({
            "story_id":   story_id,
            "story_type": story_type,
            "insights":   insights,
            "rates":      rates
        })
        fetched += 1

    # Save weekly story insights file
    date_str = datetime.now().strftime("%Y-%m-%d")
    out_path = f"data/insights/stories_{date_str}.json"
    os.makedirs("data/insights", exist_ok=True)

    output = {
        "fetched_at":     datetime.now().isoformat(),
        "stories_fetched": fetched,
        "stories_skipped": skipped,
        "stories_expired": expired,
        "story_insights":  story_insights_list
    }

    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n{'='*50}")
    print(f"Done. Story insights saved to {out_path}")
    print(f"Fetched:  {fetched}")
    print(f"Skipped:  {skipped}")
    print(f"Expired:  {expired}")
    print(f"Story training records: {len(load_story_training())}")

    return output

if __name__ == "__main__":
    fetch_story_insights_all()