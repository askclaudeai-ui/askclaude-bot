import os
import smtplib
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

NOTIFY_EMAIL      = os.getenv("NOTIFY_EMAIL", "")
GMAIL_APP_PASSWORD= os.getenv("GMAIL_APP_PASSWORD", "")
DASHBOARD_URL     = os.getenv("DASHBOARD_URL", "http://127.0.0.1:5000")

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

def notify_post_ready(post):
    """Send email when a new post is ready for review."""
    post_data    = post.get("post", {})
    hook         = post_data.get("hook", "")
    topic        = post_data.get("topic", "")
    content_type = post.get("content_type", "static")
    post_id      = post.get("id", "")
    image_url    = post.get("imgbb_url", "")

    rec_day  = post.get("scheduling",{}).get("recommended_day","")
    rec_time = post.get("scheduling",{}).get("recommended_time_utc","")

    type_emoji = {"static":"🖼️","carousel":"📊","reel":"🎬","story":"📱"}.get(content_type,"📝")

    image_html = f'<img src="{image_url}" style="width:100%;max-width:400px;border-radius:12px;margin:16px 0">' \
                 if image_url else '<p style="color:#888">No image preview available</p>'

    html = f"""
<!DOCTYPE html>
<html>
<body style="font-family:-apple-system,sans-serif;background:#0D1117;color:#E6EDF3;margin:0;padding:20px">
<div style="max-width:500px;margin:0 auto">

  <div style="background:#161B22;border-radius:16px;padding:24px;border:1px solid #30363D">

    <div style="display:flex;align-items:center;gap:12px;margin-bottom:20px">
      <span style="font-size:32px">{type_emoji}</span>
      <div>
        <div style="font-size:20px;font-weight:700;color:#F97316">Ask Claude Bot</div>
        <div style="font-size:14px;color:#8B949E">New {content_type} post ready for review</div>
      </div>
    </div>

    {image_html}

    <div style="background:#0D1117;border-radius:10px;padding:16px;margin:16px 0">
      <div style="font-size:11px;color:#F97316;font-weight:700;margin-bottom:6px">HOOK</div>
      <div style="font-size:16px;font-weight:600;color:#FFFFFF">{hook}</div>
    </div>

    <div style="background:#0D1117;border-radius:10px;padding:16px;margin:16px 0">
      <div style="font-size:11px;color:#8B949E;font-weight:700;margin-bottom:6px">TOPIC</div>
      <div style="font-size:14px;color:#C9D1D9">{topic}</div>
    </div>

    <div style="background:#0D1117;border-radius:10px;padding:12px 16px;margin:16px 0;
                display:flex;justify-content:space-between">
      <div>
        <div style="font-size:11px;color:#8B949E">Recommended</div>
        <div style="font-size:14px;color:#F97316;font-weight:600">{rec_day.title()} at {rec_time} UTC</div>
      </div>
      <div>
        <div style="font-size:11px;color:#8B949E">Post ID</div>
        <div style="font-size:14px;color:#C9D1D9;font-family:monospace">{post_id}</div>
      </div>
    </div>

    <a href="{DASHBOARD_URL}" style="display:block;background:#F97316;color:#000000;
       text-align:center;padding:16px;border-radius:10px;font-weight:700;font-size:16px;
       text-decoration:none;margin-top:20px">
      Review in Dashboard →
    </a>

    <div style="text-align:center;margin-top:16px;font-size:12px;color:#8B949E">
      Tap the button to open the dashboard and approve, reject, or edit this post.
    </div>

  </div>
</div>
</body>
</html>"""

    return send_email(
        f"{type_emoji} New {content_type} post ready — {hook[:50]}",
        html
    )

def notify_post_published(post, media_id):
    """Send email confirming a post went live."""
    hook         = post.get("post",{}).get("hook","")
    content_type = post.get("content_type","static")
    type_emoji   = {"static":"🖼️","carousel":"📊","reel":"🎬","story":"📱"}.get(content_type,"📝")

    html = f"""
<!DOCTYPE html>
<html>
<body style="font-family:-apple-system,sans-serif;background:#0D1117;color:#E6EDF3;
             margin:0;padding:20px">
<div style="max-width:500px;margin:0 auto">
  <div style="background:#161B22;border-radius:16px;padding:24px;border:1px solid #30363D">
    <div style="text-align:center;margin-bottom:20px">
      <div style="font-size:48px">✅</div>
      <div style="font-size:20px;font-weight:700;color:#F97316;margin-top:8px">Post Published!</div>
    </div>
    <div style="background:#0D1117;border-radius:10px;padding:16px;margin:16px 0">
      <div style="font-size:16px;font-weight:600;color:#FFFFFF">{hook}</div>
    </div>
    <div style="background:#0D1117;border-radius:10px;padding:12px 16px;margin:16px 0">
      <div style="font-size:11px;color:#8B949E">Instagram Media ID</div>
      <div style="font-size:14px;color:#C9D1D9;font-family:monospace">{media_id}</div>
    </div>
    <a href="https://www.instagram.com/ask.claudeai"
       style="display:block;background:#F97316;color:#000000;text-align:center;
              padding:16px;border-radius:10px;font-weight:700;font-size:16px;
              text-decoration:none;margin-top:20px">
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