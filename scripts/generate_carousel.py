import anthropic
import json
import os
import re
import uuid
import sys
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from dotenv import load_dotenv

load_dotenv()

BG      = (13, 17, 23)
BG2     = (17, 24, 39)
GRID    = (28, 35, 51)
ORANGE  = (249, 115, 22)
ORANGE2 = (251, 146, 60)
WHITE   = (255, 255, 255)
GRAY    = (107, 114, 128)
DARK1   = (55, 65, 81)
GREEN   = (16, 185, 129)

def get_font(size, bold=False):
    candidates = [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
    ]
    for p in candidates:
        try: return ImageFont.truetype(p, size)
        except: pass
    return ImageFont.load_default()

def get_mono(size):
    for p in ["/System/Library/Fonts/Menlo.ttc",
              "/Library/Fonts/Courier New.ttf"]:
        try: return ImageFont.truetype(p, size)
        except: pass
    return ImageFont.load_default()

def wrap_text(text, font, max_width, draw):
    words = text.split()
    lines, current = [], []
    for word in words:
        test = " ".join(current + [word])
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current.append(word)
        else:
            if current: lines.append(" ".join(current))
            current = [word]
    if current: lines.append(" ".join(current))
    return lines

def draw_bubble(d, x, y, w, h, radius, sw):
    cx     = x + w // 2
    t_half = int(w * 0.12)
    t_tip  = y + h + int(h * 0.26)
    d.polygon([(cx-t_half, y+h),(cx+t_half, y+h),(cx, t_tip)], fill=ORANGE)
    d.rounded_rectangle([x, y, x+w, y+h], radius=radius, fill=BG2)
    d.rounded_rectangle([x, y, x+w, y+h], radius=radius, outline=ORANGE, width=sw)

def draw_logo(d, x, y):
    bw, bh = 100, 74
    draw_bubble(d, x, y, bw, bh, radius=14, sw=4)
    pad = 10
    d.rounded_rectangle([x+pad, y+pad, x+bw-pad, y+pad+8], radius=4, fill=ORANGE)
    yb = y + pad + 8 + 6
    for op in [0.60, 0.42, 0.28]:
        c = tuple(int(v*op) for v in ORANGE2)
        d.rounded_rectangle([x+pad, yb, x+bw-pad-12, yb+6], radius=3, fill=c)
        yb += 6 + 5

def draw_progress(d, current, total, S):
    dot_r   = 6
    spacing = 24
    total_w = (total * dot_r*2) + ((total-1) * (spacing - dot_r*2))
    start_x = (S - total_w) // 2
    y       = S - 48
    for i in range(total):
        cx = start_x + i * spacing + dot_r
        if i == current:
            d.ellipse([cx-dot_r, y-dot_r, cx+dot_r, y+dot_r], fill=ORANGE)
        else:
            d.ellipse([cx-dot_r, y-dot_r, cx+dot_r, y+dot_r],
                      fill=GRID, outline=GRAY, width=1)

def render_cover_slide(slide, post_id, slide_num, total, topic):
    S = 1080
    img = Image.new("RGB", (S, S), BG)
    d   = ImageDraw.Draw(img)
    sp  = S // 4
    for x in range(0, S, sp): d.line([(x,0),(x,S)], fill=GRID, width=1)
    for y in range(0, S, sp): d.line([(0,y),(S,y)], fill=GRID, width=1)
    d.rectangle([0, 0, 6, S], fill=ORANGE)
    d.rectangle([0, 0, S, 6], fill=ORANGE)
    d.rectangle([S-6, 0, S, S], fill=(*ORANGE, 60))
    d.rectangle([0, S-6, S, S], fill=(*ORANGE, 60))
    draw_logo(d, 54, 44)
    d.text((168, 72),  "Ask",          font=get_font(28, True), fill=WHITE,  anchor="lm")
    d.text((208, 72),  "Claude",       font=get_font(28),       fill=ORANGE, anchor="lm")
    d.text((168, 104), "@ask.claudeai",font=get_mono(18),       fill=GRAY,   anchor="lm")
    d.text((S-48, 72), f"1 / {total}", font=get_mono(20),       fill=GRAY,   anchor="rm")
    title   = slide.get("title", topic)
    f_title = get_font(74, True)
    lines   = wrap_text(title, f_title, S - 120, d)
    y_pos   = 280
    for i, line in enumerate(lines[:3]):
        bbox = d.textbbox((0,0), line, font=f_title)
        tw   = bbox[2] - bbox[0]
        col  = ORANGE if i >= len(lines)//2 else WHITE
        d.text(((S-tw)//2, y_pos), line, font=f_title, fill=col)
        y_pos += 92
    subtitle = slide.get("subtitle", "")
    if subtitle:
        f_sub  = get_font(34)
        lines2 = wrap_text(subtitle, f_sub, S - 160, d)
        y_sub  = y_pos + 24
        for line in lines2[:2]:
            bbox = d.textbbox((0,0), line, font=f_sub)
            tw   = bbox[2] - bbox[0]
            d.text(((S-tw)//2, y_sub), line, font=f_sub, fill=GRAY)
            y_sub += 48
    d.text((S//2, S-80), "Swipe to learn →",
           font=get_mono(22), fill=GRAY, anchor="mm")
    draw_progress(d, 0, total, S)
    return img

def render_content_slide(slide, post_id, slide_num, total):
    S = 1080
    img = Image.new("RGB", (S, S), BG)
    d   = ImageDraw.Draw(img)
    sp  = S // 4
    for x in range(0, S, sp): d.line([(x,0),(x,S)], fill=GRID, width=1)
    for y in range(0, S, sp): d.line([(0,y),(S,y)], fill=GRID, width=1)
    d.rectangle([0, 0, 6, S], fill=ORANGE)
    d.rectangle([0, S-6, S, S], fill=(*ORANGE, 60))
    draw_logo(d, 54, 44)
    d.text((168, 74),  "Ask",          font=get_font(24, True), fill=WHITE,  anchor="lm")
    d.text((202, 74),  "Claude",       font=get_font(24),       fill=ORANGE, anchor="lm")
    d.text((S-48, 74), f"{slide_num} / {total}",
           font=get_mono(20), fill=GRAY, anchor="rm")
    tip_num = slide.get("tip_number", slide_num - 1)
    d.rounded_rectangle([54, 148, 160, 198], radius=25, fill=ORANGE)
    d.text((107, 173), f"Tip {tip_num}",
           font=get_font(24, True), fill=BG, anchor="mm")
    title = slide.get("title", "")
    f_t   = get_font(52, True)
    lines = wrap_text(title, f_t, S - 120, d)
    y_pos = 228
    for line in lines[:2]:
        bbox = d.textbbox((0,0), line, font=f_t)
        tw   = bbox[2] - bbox[0]
        d.text(((S-tw)//2, y_pos), line, font=f_t, fill=WHITE)
        y_pos += 66
    d.rectangle([54, y_pos+16, S-54, y_pos+19], fill=GRID)
    d.rectangle([54, y_pos+16, 180, y_pos+19], fill=ORANGE)
    body  = slide.get("body", "")
    f_b   = get_font(32)
    b_lines = wrap_text(body, f_b, S - 120, d)
    y_body  = y_pos + 44
    for line in b_lines[:5]:
        d.text((54, y_body), line, font=f_b, fill=WHITE)
        y_body += 46
    code = slide.get("code_snippet", "")
    if code and y_body < 820:
        code_lines = code.strip().split("\n")[:6]
        box_h = len(code_lines) * 36 + 32
        box_y = min(y_body + 20, 820)
        if box_y + box_h < S - 80:
            d.rounded_rectangle([54, box_y, S-54, box_y+box_h],
                                 radius=10, fill=BG2)
            d.rounded_rectangle([54, box_y, 62, box_y+box_h],
                                 radius=0, fill=ORANGE)
            f_code = get_mono(26)
            yc = box_y + 16
            for cl in code_lines:
                d.text((78, yc), cl, font=f_code, fill=GREEN)
                yc += 36
    draw_progress(d, slide_num-1, total, S)
    return img

def render_cta_slide(slide, post_id, total, handle="@ask.claudeai"):
    S = 1080
    img = Image.new("RGB", (S, S), BG)
    d   = ImageDraw.Draw(img)
    sp  = S // 4
    for x in range(0, S, sp): d.line([(x,0),(x,S)], fill=GRID, width=1)
    for y in range(0, S, sp): d.line([(0,y),(S,y)], fill=GRID, width=1)
    d.rectangle([0, 0, 6, S], fill=ORANGE)
    d.rectangle([0, 0, S, 6], fill=ORANGE)
    d.rectangle([S-6, 0, S, S], fill=(*ORANGE, 60))
    d.rectangle([0, S-6, S, S], fill=(*ORANGE, 60))
    bw, bh = 240, 168
    bx = (S - bw) // 2
    by = 180
    draw_bubble(d, bx, by, bw, bh, radius=32, sw=10)
    pad = 24
    d.rounded_rectangle([bx+pad, by+pad, bx+bw-pad, by+pad+22],
                         radius=11, fill=ORANGE)
    yb = by + pad + 22 + 14
    for op in [0.65, 0.48, 0.32]:
        c = tuple(int(v*op) for v in ORANGE2)
        d.rounded_rectangle([bx+pad, yb, bx+bw-pad-28, yb+16],
                             radius=8, fill=c)
        yb += 16 + 12
    cta_title = slide.get("title", "Found this useful?")
    f_ct  = get_font(58, True)
    lines = wrap_text(cta_title, f_ct, S-160, d)
    y_pos = 420
    for line in lines[:2]:
        bbox = d.textbbox((0,0), line, font=f_ct)
        tw   = bbox[2] - bbox[0]
        d.text(((S-tw)//2, y_pos), line, font=f_ct, fill=WHITE)
        y_pos += 72
    body  = slide.get("body", "Save this carousel and follow for more Claude API tips every week.")
    f_sub = get_font(32)
    sub_lines = wrap_text(body, f_sub, S-200, d)
    y_sub = y_pos + 16
    for line in sub_lines[:3]:
        bbox = d.textbbox((0,0), line, font=f_sub)
        tw   = bbox[2] - bbox[0]
        d.text(((S-tw)//2, y_sub), line, font=f_sub, fill=GRAY)
        y_sub += 46
    d.rounded_rectangle([240, 810, S-240, 880], radius=35, fill=ORANGE)
    d.text((S//2, 845), "Save this carousel",
           font=get_font(32, True), fill=BG, anchor="mm")
    d.text((S//2, 940), handle, font=get_mono(28), fill=GRAY, anchor="mm")
    d.text((S//2, 984), "New post every  Mon  ·  Wed  ·  Thu",
           font=get_mono(20), fill=DARK1, anchor="mm")
    draw_progress(d, total-1, total, S)
    return img

def render_slides(slides_data, post_id, topic):
    out_dir = f"queue/images/{post_id}"
    os.makedirs(out_dir, exist_ok=True)
    total   = len(slides_data)
    images  = []
    for i, slide in enumerate(slides_data):
        slide_type = slide.get("type", "content")
        if slide_type == "cover":
            img = render_cover_slide(slide, post_id, i+1, total, topic)
        elif slide_type == "cta":
            img = render_cta_slide(slide, post_id, total)
        else:
            img = render_content_slide(slide, post_id, i+1, total)
        path = f"{out_dir}/slide_{i+1:02d}.png"
        img.save(path, "PNG", optimize=True)
        images.append(path)
        print(f"  Slide {i+1}/{total} saved")
    return images

def parse_claude_json(text):
    clean = text.strip()
    if "```" in clean:
        parts = clean.split("```")
        clean = parts[1] if len(parts) > 1 else clean
        if clean.startswith("json"): clean = clean[4:]
    clean = clean.strip()
    clean = re.sub(r'(?<=[\[,])\s*#(\w+)"', r' "#\1"', clean)
    clean = re.sub(r',\s*([}\]])', r'\1', clean)
    return json.loads(clean)

def generate_carousel():
    client   = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    strategy = json.load(open("data/strategy.json"))
    trend_files = sorted([f for f in os.listdir("data") if f.startswith("trends_")])
    trends = json.load(open(f"data/{trend_files[-1]}")) if trend_files else {}
    topics    = [c["cluster"] for c in strategy["topics"]["ranked_clusters"]]
    evergreen = strategy["hashtags"]["evergreen_tags"]
    rec_day   = strategy["timing"]["preferred_days"][0]["day"]
    rec_hour  = f"{strategy['timing']['preferred_hours_utc'][0]:02d}:00"
    n_slides  = strategy["content_format"].get("carousel_optimal_slides", 6)
    trend_ctx = ""
    if trends:
        trend_ctx = f"Trending topics: {', '.join(trends.get('trending_topics', [])[:3])}"
    prompt = f"""You are a social media content creator for @ask.claudeai — an Instagram page posting Claude API tips for developers.

Create a {n_slides}-slide Instagram carousel post about Claude API for developers.

TOPIC POOL: {', '.join(topics[:5])}
TREND CONTEXT: {trend_ctx}
EVERGREEN HASHTAGS: {', '.join(evergreen)}

Structure:
- Slide 1: Cover slide with a strong hook title
- Slides 2 to {n_slides-1}: One tip per slide with title, explanation, and optional code
- Slide {n_slides}: CTA slide (follow/save prompt)

Rules:
- Each tip must be genuinely useful and specific
- Code snippets should be real, runnable Python using the Anthropic SDK
- Max 2 lines of body text per content slide
- Code snippets max 5 lines

Return ONLY valid JSON:
{{
  "topic": "overall carousel topic",
  "topic_cluster": "{topics[0]}",
  "hook": "carousel hook line (max 90 chars)",
  "slides": [
    {{
      "type": "cover",
      "title": "carousel title (max 8 words)",
      "subtitle": "one line subtitle (max 10 words)"
    }},
    {{
      "type": "content",
      "tip_number": 1,
      "title": "tip title (max 6 words)",
      "body": "explanation in 1-2 sentences",
      "code_snippet": "optional python code (max 5 lines, or empty string)"
    }},
    {{
      "type": "cta",
      "title": "CTA headline (max 6 words)",
      "body": "follow/save prompt sentence"
    }}
  ],
  "hashtags": ["#claudeai","#anthropic","#aidev","#llm","#pythondev","#apidevelopment","#aiintegration","#machinelearning","#codinglife","#devtips","#programming","#artificialintelligence","#developer","#techstack","#buildwithclaude","#promptengineering","#automation","#aitools"],
  "recommended_day": "{rec_day}",
  "recommended_time_utc": "{rec_hour}"
}}

Include exactly {n_slides} slides total (1 cover + {n_slides-2} content + 1 CTA)."""

    print(f"Generating {n_slides}-slide carousel...")
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}]
    )
    try:
        data = parse_claude_json(message.content[0].text)
    except Exception as e:
        print(f"JSON parse error: {e}")
        return None

    post_id     = str(uuid.uuid4())[:8]
    topic       = data.get("topic", "Claude API tips")
    print(f"\nTopic: {topic}")
    print(f"Hook:  {data.get('hook','')}")
    print(f"\nRendering {len(data['slides'])} slides...")
    image_paths = render_slides(data["slides"], post_id, topic)

    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"queue/{date_str}_{post_id}.json"

    queue_entry = {
        "id":               post_id,
        "content_type":     "carousel",
        "status":           "pending",
        "created_at":       datetime.now().isoformat(),
        "published_at":     None,
        "instagram_media_id": None,
        "imgbb_url":        None,
        "imgbb_slide_urls": [],
        "generation_inputs": {
            "strategy_snapshot": {
                "model_phase":    strategy["meta"]["model_phase"],
                "timing":         strategy["timing"],
                "content_format": strategy["content_format"]
            },
            "trend_report":    trends,
            "topic_cluster":   data.get("topic_cluster", topics[0]),
            "hook_style_used": "number_list"
        },
        "post": {
            "topic":           topic,
            "hook":            data.get("hook", ""),
            "caption":         data.get("hook", "") + "\n\nSave this carousel for your next Claude API project.",
            "hashtags":        data.get("hashtags", evergreen),
            "audio_suggestion":"original audio",
            "slides":          data["slides"],
            "slide_count":     len(data["slides"]),
            "image_paths":     image_paths
        },
        "scheduling": {
            "recommended_day":       data.get("recommended_day", rec_day),
            "recommended_time_utc":  data.get("recommended_time_utc", rec_hour),
            "actual_publish_day":    None,
            "actual_publish_time_utc": None,
            "timing_deviation_hours":  None
        },
        "model_prediction": {
            "predicted_engagement_rate": None,
            "predicted_reach":           None,
            "prediction_confidence":     None,
            "model_phase_at_prediction": strategy["meta"]["model_phase"]
        }
    }

    # Upload all slides to ImgBB
    if image_paths:
        try:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from upload_media import upload_all_slides_imgbb
            print("\nUploading carousel slides to ImgBB...")
            slide_urls = upload_all_slides_imgbb(image_paths)
            queue_entry["imgbb_url"]        = slide_urls[0] if slide_urls else None
            queue_entry["imgbb_slide_urls"] = slide_urls
            print(f"Uploaded {len([u for u in slide_urls if u])} slides")
        except Exception as e:
            print(f"Slide upload skipped: {e}")

    # Send email notification
    try:
        from notify import notify_post_ready
        notify_post_ready(queue_entry)
    except Exception as e:
        print(f"Notification skipped: {e}")

    os.makedirs("queue", exist_ok=True)
    with open(filename, "w") as f:
        json.dump(queue_entry, f, indent=2)

    print(f"\nCarousel saved to {filename}")
    print(f"Slides saved to queue/images/{post_id}/")
    return filename, queue_entry

if __name__ == "__main__":
    generate_carousel()