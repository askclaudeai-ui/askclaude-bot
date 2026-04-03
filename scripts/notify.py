import os
import smtplib
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

NOTIFY_EMAIL       = os.getenv("NOTIFY_EMAIL", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
DASHBOARD_URL      = os.getenv("DASHBOARD_URL", "http://127.0.0.1:5000")

def send_email(subject, html_body):
    if not NOTIFY_EMAIL or not GMAIL_APP_PASSWORD:
        print("Email not configured — skipping notification")
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = NOTIFY_EMAIL
        msg["To"]      = NOTIFY_EMAIL
        msg.attach(MIMEText(html_body, "html"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(NOTIFY_EMAIL, GMAIL_APP_PASSWORD)
            smtp.sendmail(NOTIFY_EMAIL, NOTIFY_EMAIL, msg.as_string())
        print(f"Notification sent to {NOTIFY_EMAIL}")
        return True
    except Exception as e:
        print(f"Email failed: {e}")
        return False

def get_preview_url(post):
    """
    Get the best image URL for email preview.
    Priority: Cloudinary (no hotlink restrictions) > skip image
    Never use ImgBB — it blocks email hotlinking on free tier.
    """
    # Cloudinary image (feed posts)
    if post.get("cloudinary_image_url"):
        return post["cloudinary_image_url"]
    # Cloudinary video thumbnail (reels)
    if post.get("imgbb_url") and "cloudinary" in post.get("imgbb_url", ""):
        return post["imgbb_url"]
    # Cloudinary story images
    story_urls = post.get("cloudinary_story_urls", [])
    if story_urls and story_urls[0]:
        return story_urls[0]
    # Carousel — use first Cloudinary slide if available
    slide_urls = post.get("imgbb_slide_urls", [])
    cloudinary_slides = [u for u in slide_urls if u and "cloudinary" in u]
    if cloudinary_slides:
        return cloudinary_slides[0]
    # No valid URL
    return None

def notify_post_ready(post):
    """Send email when a new post is ready for review."""
    post_data    = post.get("post", {})
    hook         = post_data.get("hook", "")
    topic        = post_data.get("topic", "")
    content_type = post.get("content_type", "static")
    story_type   = post.get("story_type", "")
    post_id      = post.get("id", "")
    preview_url  = get_preview_url(post)

    rec_day  = post.get("scheduling",{}).get("recommended_day","")
    rec_time = post.get("scheduling",{}).get("recommended_time_utc","")

    type_emoji = {
        "static":   "🖼️",
        "carousel": "📊",
        "reel":     "🎬",
        "story":    "📱"
    }.get(content_type, "📝")

    type_label = content_type
    if story_type:
        type_label = f"{content_type} · {story_type}"

    # Image block — only if we have a Cloudinary URL
    if preview_url:
        image_html = f"""
        <div style="margin:16px 0;border-radius:12px;overflow:hidden;max-width:420px">
            <img src="{preview_url}"
                 style="width:100%;max-width:420px;display:block;border-radius:12px"
                 alt="Post preview">
        </div>"""
    else:
        image_html = """
        <div style="margin:16px 0;background:#1C2333;border-radius:12px;
                    padding:24px;text-align:center;max-width:420px">
            <div style="font-size:32px;margin-bottom:8px">🖼️</div>
            <div style="font-size:13px;color:#8B949E">
                Preview available in dashboard
            </div>
        </div>"""

    html = f"""
<!DOCTYPE html>
<html>
<body style="font-family:-apple-system,sans-serif;background:#0D1117;
             color:#E6EDF3;margin:0;padding:20px">
<div style="max-width:520px;margin:0 auto">

  <div style="background:#161B22;border-radius:16px;padding:24px;
              border:1px solid #30363D">

    <!-- Header -->
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:20px;
                padding-bottom:16px;border-bottom:1px solid #30363D">
      <span style="font-size:32px">{type_emoji}</span>
      <div>
        <div style="font-size:20px;font-weight:700;color:#D97706">
          Ask Claude Bot
        </div>
        <div style="font-size:14px;color:#8B949E">
          New {type_label} post ready for review
        </div>
      </div>
    </div>

    {image_html}

    <!-- Hook -->
    <div style="background:#0D1117;border-radius:10px;padding:14px 16px;
                margin:12px 0;border-left:3px solid #3730A3">
      <div style="font-size:11px;color:#3730A3;font-weight:700;
                  margin-bottom:6px;letter-spacing:.05em">HOOK</div>
      <div style="font-size:16px;font-weight:600;color:#E6EDF3">
        {hook}
      </div>
    </div>

    <!-- Topic -->
    <div style="background:#0D1117;border-radius:10px;padding:12px 16px;
                margin:12px 0">
      <div style="font-size:11px;color:#8B949E;font-weight:700;
                  margin-bottom:4px">TOPIC</div>
      <div style="font-size:14px;color:#C9D1D9">{topic}</div>
    </div>

    <!-- Timing + ID -->
    <div style="display:flex;gap:12px;margin:12px 0">
      <div style="flex:1;background:#0D1117;border-radius:10px;
                  padding:10px 14px">
        <div style="font-size:11px;color:#8B949E">Recommended</div>
        <div style="font-size:14px;color:#D97706;font-weight:600">
          {rec_day.title()} at {rec_time} UTC
        </div>
      </div>
      <div style="flex:1;background:#0D1117;border-radius:10px;
                  padding:10px 14px">
        <div style="font-size:11px;color:#8B949E">Post ID</div>
        <div style="font-size:13px;color:#C9D1D9;font-family:monospace">
          {post_id}
        </div>
      </div>
    </div>

    <!-- CTA Button -->
    <a href="{DASHBOARD_URL}"
       style="display:block;background:#3730A3;color:#FFF3D0;
              text-align:center;padding:16px;border-radius:12px;
              font-weight:700;font-size:16px;text-decoration:none;
              margin-top:20px">
      Review in Dashboard →
    </a>

    <div style="text-align:center;margin-top:14px;font-size:12px;
                color:#8B949E">
      Tap to open the dashboard and approve, reject, or edit this post.
    </div>

  </div>

  <div style="text-align:center;margin-top:16px;font-size:11px;color:#444">
    Ask Claude Bot · @ask.claudeai
  </div>

</div>
</body>
</html>"""

    return send_email(
        f"{type_emoji} New {type_label} post ready — {hook[:50]}",
        html
    )

def notify_post_published(post, media_id):
    """Send email confirming a post went live."""
    hook         = post.get("post",{}).get("hook","")
    content_type = post.get("content_type","static")
    type_emoji   = {
        "static":"🖼️","carousel":"📊","reel":"🎬","story":"📱"
    }.get(content_type,"📝")

    html = f"""
<!DOCTYPE html>
<html>
<body style="font-family:-apple-system,sans-serif;background:#0D1117;
             color:#E6EDF3;margin:0;padding:20px">
<div style="max-width:520px;margin:0 auto">
  <div style="background:#161B22;border-radius:16px;padding:24px;
              border:1px solid #30363D">
    <div style="text-align:center;margin-bottom:20px">
      <div style="font-size:52px">✅</div>
      <div style="font-size:22px;font-weight:700;color:#D97706;margin-top:8px">
        Post Published!
      </div>
    </div>
    <div style="background:#0D1117;border-radius:10px;padding:14px 16px;
                margin:12px 0;border-left:3px solid #3730A3">
      <div style="font-size:16px;font-weight:600;color:#E6EDF3">{hook}</div>
    </div>
    <div style="background:#0D1117;border-radius:10px;padding:12px 16px;
                margin:12px 0">
      <div style="font-size:11px;color:#8B949E">Instagram Media ID</div>
      <div style="font-size:14px;color:#C9D1D9;font-family:monospace">
        {media_id}
      </div>
    </div>
    <a href="https://www.instagram.com/ask.claudeai"
       style="display:block;background:#3730A3;color:#FFF3D0;
              text-align:center;padding:16px;border-radius:12px;
              font-weight:700;font-size:16px;text-decoration:none;
              margin-top:20px">
      View on Instagram →
    </a>
  </div>
</div>
</body>
</html>"""

    return send_email(
        f"{type_emoji} Published — {hook[:50]}",
        html
    )

if __name__ == "__main__":
    print("Sending test email...")
    result = send_email(
        "Test from Ask Claude Bot",
        """<div style='font-family:sans-serif;background:#0D1117;padding:20px;
                      color:#E6EDF3;border-radius:12px'>
           <h1 style='color:#D97706'>It works!</h1>
           <p>Email notifications are configured correctly.</p>
           </div>"""
    )
    print("Sent successfully" if result else "Failed — check GMAIL_APP_PASSWORD in .env")