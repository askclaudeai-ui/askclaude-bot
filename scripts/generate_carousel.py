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

BG      = (255, 243, 208)   # #FFF3D0 cream
BG2     = (255, 232, 150)   # #FFE896 deeper cream
INDIGO  = (55,  48,  163)   # #3730A3 primary
INDIGO2 = (79,  70,  229)   # #4F46E5 mid
GOLD    = (217, 119,   6)   # #D97706 accent
TEXT    = (30,  27,   75)   # #1E1B4B dark text
MID     = (61,  56,  120)   # #3D3878 mid text
GRID    = (210, 180,  80)   # subtle grid
WHITE   = (255, 255, 255)

# VS Code dark theme colours for code blocks
VS_BG   = (30,  30,  30)
VS_GUT  = (24,  24,  24)
VS_KW   = (86,  156, 214)
VS_FN   = (220, 220, 170)
VS_STR  = (206, 145, 120)
VS_CMT  = (106, 153,  85)
VS_VAR  = (156, 220, 254)
VS_NUM  = (181, 206, 168)
VS_OP   = (212, 212, 212)
VS_HL   = (38,  79,  120)
VS_TEXT = (204, 204, 204)

def get_font(size, bold=False):
    for p in ["/System/Library/Fonts/Helvetica.ttc",
              "/System/Library/Fonts/Arial.ttf",
              "/Library/Fonts/Arial.ttf"]:
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

def tokenize_python(line):
    keywords = {'import','from','def','class','with','for','in',
                'if','else','elif','return','as','try','except',
                'True','False','None','and','or','not','pass',
                'while','break','continue','raise','yield'}
    tokens = []
    if line.lstrip().startswith('#'):
        tokens.append((line, VS_CMT))
        return tokens
    i = 0
    while i < len(line):
        if line[i] == '#':
            tokens.append((line[i:], VS_CMT))
            break
        if line[i] in ('"', "'"):
            q = line[i]
            if line[i:i+3] in ('"""', "'''"):
                q = line[i:i+3]
            j = i + len(q)
            while j < len(line):
                if line[j:j+len(q)] == q:
                    j += len(q)
                    break
                j += 1
            tokens.append((line[i:j], VS_STR))
            i = j
            continue
        if line[i].isdigit():
            j = i
            while j < len(line) and (line[j].isdigit() or line[j] == '.'):
                j += 1
            tokens.append((line[i:j], VS_NUM))
            i = j
            continue
        if line[i].isalpha() or line[i] == '_':
            j = i
            while j < len(line) and (line[j].isalnum() or line[j] == '_'):
                j += 1
            word = line[i:j]
            after = line[j:].lstrip()
            if word in keywords:
                tokens.append((word, VS_KW))
            elif after.startswith('('):
                tokens.append((word, VS_FN))
            else:
                tokens.append((word, VS_VAR))
            i = j
            continue
        if line[i] in '()[]{}':
            tokens.append((line[i], (255, 215, 0)))
            i += 1
            continue
        tokens.append((line[i], VS_OP))
        i += 1
    return tokens

def draw_logo_bubble(d, x, y, w, h, radius=18, sw=5):
    cx     = x + w // 2
    t_half = int(w * 0.12)
    t_tip  = y + h + int(h * 0.28)
    d.polygon([(cx-t_half, y+h),(cx+t_half, y+h),(cx, t_tip)], fill=INDIGO)
    d.rounded_rectangle([x, y, x+w, y+h], radius=radius, fill=BG2)
    d.rounded_rectangle([x, y, x+w, y+h], radius=radius, outline=INDIGO, width=sw)
    pad = int(w * 0.13)
    d.rounded_rectangle([x+pad, y+pad, x+w-pad, y+pad+10],
                         radius=5, fill=INDIGO)
    yb = y + pad + 10 + 7
    for op in [1.0, 0.65, 0.40]:
        c = tuple(int(GOLD[i]*op + BG2[i]*(1-op)) for i in range(3))
        bw2 = int((w - pad*2) * (0.85 if op==1.0 else 0.65 if op==0.65 else 0.45))
        d.rounded_rectangle([x+pad, yb, x+pad+bw2, yb+8], radius=4, fill=c)
        yb += 8 + 6

def draw_progress(d, current, total, S):
    dot_r   = 7
    spacing = 28
    total_w = total*dot_r*2 + (total-1)*(spacing-dot_r*2)
    start_x = (S - total_w) // 2
    y       = S - 52
    for i in range(total):
        cx = start_x + i*spacing + dot_r
        if i == current:
            d.ellipse([cx-dot_r, y-dot_r, cx+dot_r, y+dot_r], fill=INDIGO)
        else:
            d.ellipse([cx-dot_r, y-dot_r, cx+dot_r, y+dot_r],
                      fill=BG2, outline=INDIGO, width=2)

def draw_vscode_block(d, x, y, w, h, code_lines, font_size=24):
    """Draw a VS Code dark theme code block that fits within bounds."""
    f_code = get_mono(font_size)
    f_ln   = get_mono(font_size - 4)
    GUTTER = 52
    LINE_H = int(font_size * 1.6)

    # Background
    d.rounded_rectangle([x, y, x+w, y+h], radius=12, fill=VS_BG)

    # Tab bar
    TAB_H = 36
    d.rounded_rectangle([x, y, x+w, y+TAB_H], radius=12, fill=(45,45,45))
    d.rectangle([x, y+TAB_H//2, x+w, y+TAB_H], fill=(45,45,45))
    # Tab dots
    for i, col in enumerate([(255,95,87),(254,188,46),(40,200,64)]):
        cx = x + 16 + i*20
        d.ellipse([cx-6, y+TAB_H//2-6, cx+6, y+TAB_H//2+6], fill=col)

    # Gutter
    d.rectangle([x, y+TAB_H, x+GUTTER, y+h], fill=VS_GUT)
    d.line([(x+GUTTER, y+TAB_H),(x+GUTTER, y+h)], fill=(55,55,55), width=1)

    # Code lines — clip to available height
    max_lines = (h - TAB_H - 12) // LINE_H
    code_to_show = code_lines[:max_lines]

    for i, line in enumerate(code_to_show):
        ly = y + TAB_H + 6 + i * LINE_H

        # Line number
        d.text((x+GUTTER-8, ly+2), str(i+1),
               font=f_ln, fill=(90,90,90), anchor="rt")

        # Syntax highlighted code — clip to box width
        tokens = tokenize_python(line)
        cx = x + GUTTER + 10
        max_x = x + w - 10
        for text, colour in tokens:
            if not text or cx >= max_x:
                break
            bbox = d.textbbox((cx, ly), text, font=f_code)
            tw = bbox[2] - bbox[0]
            # Clip text if it would overflow
            if cx + tw > max_x:
                # Truncate with ellipsis
                for end in range(len(text), 0, -1):
                    t2 = text[:end] + "…"
                    b2 = d.textbbox((cx, ly), t2, font=f_code)
                    if b2[2] - b2[0] <= max_x - cx:
                        d.text((cx, ly), t2, font=f_code, fill=colour)
                        break
                break
            d.text((cx, ly), text, font=f_code, fill=colour)
            cx += tw

def render_cover_slide(slide, total, topic):
    S = 1080
    img = Image.new("RGB", (S, S), BG)
    d   = ImageDraw.Draw(img)

    sp = S // 4
    for x in range(0, S, sp): d.line([(x,0),(x,S)], fill=GRID, width=1)
    for y in range(0, S, sp): d.line([(0,y),(S,y)], fill=GRID, width=1)

    # Border
    d.rectangle([0,   0,   8,   S], fill=INDIGO)
    d.rectangle([0,   0,   S,   8], fill=INDIGO)
    d.rectangle([S-8, 0,   S,   S], fill=GOLD)
    d.rectangle([0,   S-8, S,   S], fill=GOLD)

    # Logo + handle
    draw_logo_bubble(d, 54, 46, 148, 104, radius=20, sw=6)
    d.text((222, 86),  "Ask",           font=get_font(30, True), fill=TEXT,   anchor="lm")
    d.text((272, 86),  "Claude",        font=get_font(30),       fill=INDIGO, anchor="lm")
    d.text((222, 124), "@ask.claudeai", font=get_mono(18),       fill=MID,    anchor="lm")
    d.text((S-48, 86), f"1 / {total}",  font=get_mono(20),       fill=MID,    anchor="rm")

    # Main title
    title   = slide.get("title", topic)
    f_title = get_font(82, True)
    lines   = wrap_text(title, f_title, S - 120, d)
    y_pos   = 300
    for i, line in enumerate(lines[:3]):
        bbox = d.textbbox((0,0), line, font=f_title)
        tw   = bbox[2] - bbox[0]
        col  = INDIGO if i >= len(lines)//2 else TEXT
        d.text(((S-tw)//2, y_pos), line, font=f_title, fill=col)
        y_pos += 100

    # Subtitle
    subtitle = slide.get("subtitle", "")
    if subtitle:
        f_sub  = get_font(36)
        lines2 = wrap_text(subtitle, f_sub, S - 160, d)
        y_sub  = y_pos + 28
        for line in lines2[:2]:
            bbox = d.textbbox((0,0), line, font=f_sub)
            tw   = bbox[2] - bbox[0]
            d.text(((S-tw)//2, y_sub), line, font=f_sub, fill=MID)
            y_sub += 50

    # Swipe prompt
    d.text((S//2, S-90), "Swipe to learn →",
           font=get_mono(24), fill=MID, anchor="mm")
    draw_progress(d, 0, total, S)
    return img

def render_content_slide(slide, slide_num, total):
    S = 1080
    img = Image.new("RGB", (S, S), BG)
    d   = ImageDraw.Draw(img)

    sp = S // 4
    for x in range(0, S, sp): d.line([(x,0),(x,S)], fill=GRID, width=1)
    for y in range(0, S, sp): d.line([(0,y),(S,y)], fill=GRID, width=1)

    d.rectangle([0,   0,   8,   S], fill=INDIGO)
    d.rectangle([0,   S-8, S,   S], fill=GOLD)

    # Logo + handle
    draw_logo_bubble(d, 54, 46, 148, 104, radius=20, sw=6)
    d.text((222, 86),  "Ask",           font=get_font(30, True), fill=TEXT,   anchor="lm")
    d.text((272, 86),  "Claude",        font=get_font(30),       fill=INDIGO, anchor="lm")
    d.text((222, 124), "@ask.claudeai", font=get_mono(18),       fill=MID,    anchor="lm")
    d.text((S-48, 86), f"{slide_num} / {total}",
           font=get_mono(20), fill=MID, anchor="rm")

    # Tip number pill — indigo bg, cream text, clearly readable
    tip_num = slide.get("tip_number", slide_num - 1)
    tip_lbl = f"Tip {tip_num}"
    f_tip   = get_font(28, True)
    bbox    = d.textbbox((0,0), tip_lbl, font=f_tip)
    tw      = bbox[2]-bbox[0]
    px, py  = 54, 178
    pw, ph  = tw + 48, 52
    d.rounded_rectangle([px, py, px+pw, py+ph], radius=ph//2, fill=INDIGO)
    d.text((px+pw//2, py+ph//2), tip_lbl,
           font=f_tip, fill=BG, anchor="mm")

    # Tip title
    title = slide.get("title", "")
    f_t   = get_font(56, True)
    lines = wrap_text(title, f_t, S - 120, d)
    y_pos = 260
    for line in lines[:2]:
        bbox = d.textbbox((0,0), line, font=f_t)
        tw   = bbox[2] - bbox[0]
        d.text(((S-tw)//2, y_pos), line, font=f_t, fill=TEXT)
        y_pos += 72

    # Divider
    d.rectangle([54, y_pos+16, S-54, y_pos+20], fill=GRID)
    d.rectangle([54, y_pos+16, 200,  y_pos+20], fill=INDIGO)

    # Body text
    body    = slide.get("body", "")
    f_b     = get_font(34)
    b_lines = wrap_text(body, f_b, S - 120, d)
    y_body  = y_pos + 44
    for line in b_lines[:4]:
        d.text((54, y_body), line, font=f_b, fill=TEXT)
        y_body += 48

    # VS Code code block
    code = slide.get("code_snippet", "").strip()
    if code:
        code_lines = code.split("\n")
        # Calculate available space
        box_y = y_body + 24
        box_h = S - box_y - 80
        if box_h >= 120:
            draw_vscode_block(d, 54, box_y, S-108, box_h,
                              code_lines, font_size=26)

    draw_progress(d, slide_num-1, total, S)
    return img

def render_cta_slide(slide, total):
    S = 1080
    img = Image.new("RGB", (S, S), BG)
    d   = ImageDraw.Draw(img)

    sp = S // 4
    for x in range(0, S, sp): d.line([(x,0),(x,S)], fill=GRID, width=1)
    for y in range(0, S, sp): d.line([(0,y),(S,y)], fill=GRID, width=1)

    d.rectangle([0,   0,   8,   S], fill=INDIGO)
    d.rectangle([0,   0,   S,   8], fill=INDIGO)
    d.rectangle([S-8, 0,   S,   S], fill=GOLD)
    d.rectangle([0,   S-8, S,   S], fill=GOLD)

    # Large centred logo — bubble with tail pointing down
    bw, bh = 280, 180
    bx = (S - bw) // 2
    by = 160
    # Draw bubble body
    cx     = bx + bw // 2
    t_half = int(bw * 0.12)
    t_tip  = by + bh + int(bh * 0.28)
    d.polygon([(cx-t_half, by+bh),(cx+t_half, by+bh),(cx, t_tip)], fill=INDIGO)
    d.rounded_rectangle([bx, by, bx+bw, by+bh], radius=40, fill=BG2)
    d.rounded_rectangle([bx, by, bx+bw, by+bh], radius=40, outline=INDIGO, width=12)
    # Top indigo bar
    pad = int(bw * 0.13)
    d.rounded_rectangle([bx+pad, by+pad, bx+bw-pad, by+pad+18],
                         radius=9, fill=INDIGO)
    # Gold content bars
    yb = by + pad + 18 + 10
    for op in [1.0, 0.65, 0.40]:
        c   = tuple(int(GOLD[i]*op + BG2[i]*(1-op)) for i in range(3))
        bw2 = int((bw - pad*2) * (0.85 if op==1.0 else 0.65 if op==0.65 else 0.45))
        bh2 = 14
        d.rounded_rectangle([bx+pad, yb, bx+pad+bw2, yb+bh2],
                             radius=bh2//2, fill=c)
        yb += bh2 + 10

    # CTA title
    cta_title = slide.get("title", "Found this useful?")
    f_ct  = get_font(64, True)
    lines = wrap_text(cta_title, f_ct, S-160, d)
    y_pos = 440
    for line in lines[:2]:
        bbox = d.textbbox((0,0), line, font=f_ct)
        tw   = bbox[2] - bbox[0]
        d.text(((S-tw)//2, y_pos), line, font=f_ct, fill=TEXT)
        y_pos += 80

    # Sub text
    body  = slide.get("body", "Save this carousel and follow for more Claude API tips every week.")
    f_sub = get_font(34)
    sub_lines = wrap_text(body, f_sub, S-200, d)
    y_sub = y_pos + 20
    for line in sub_lines[:3]:
        bbox = d.textbbox((0,0), line, font=f_sub)
        tw   = bbox[2] - bbox[0]
        d.text(((S-tw)//2, y_sub), line, font=f_sub, fill=MID)
        y_sub += 48

    # Save button
    d.rounded_rectangle([240, 820, S-240, 900], radius=40, fill=INDIGO)
    d.text((S//2, 860), "Save this carousel",
           font=get_font(36, True), fill=BG, anchor="mm")

    d.text((S//2, 950),  "@ask.claudeai",
           font=get_mono(30), fill=MID, anchor="mm")
    d.text((S//2, 996),  "New post every  Mon  ·  Wed  ·  Thu",
           font=get_mono(22), fill=MID, anchor="mm")

    draw_progress(d, total-1, total, S)
    return img

def render_slides(slides_data, post_id, topic):
    out_dir = f"queue/images/{post_id}"
    os.makedirs(out_dir, exist_ok=True)
    total  = len(slides_data)
    images = []
    for i, slide in enumerate(slides_data):
        slide_type = slide.get("type", "content")
        if slide_type == "cover":
            img = render_cover_slide(slide, total, topic)
        elif slide_type == "cta":
            img = render_cta_slide(slide, total)
        else:
            img = render_content_slide(slide, i+1, total)
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

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        from strategy_summary import get_strategy_summary
        strategy_summary = get_strategy_summary()
    except:
        strategy_summary = ""

    trend_files = sorted([f for f in os.listdir("data") if f.startswith("trends_")])
    trends    = json.load(open(f"data/{trend_files[-1]}")) if trend_files else {}
    topics    = [c["cluster"] for c in strategy["topics"]["ranked_clusters"]]
    evergreen = strategy["hashtags"]["evergreen_tags"]
    rec_day   = strategy["timing"]["preferred_days"][0]["day"]
    rec_hour  = f"{strategy['timing']['preferred_hours_utc'][0]:02d}:00"
    n_slides  = strategy["content_format"].get("carousel_optimal_slides", 6)
    trend_ctx = ""
    if trends:
        trend_ctx = f"Trending: {', '.join(trends.get('trending_topics',[])[:3])}"

    prompt = f"""You are a social media content creator for @ask.claudeai — Claude API tips for developers.

STRATEGY:
{strategy_summary}

Create a {n_slides}-slide Instagram carousel about Claude API.

TOPIC POOL: {', '.join(topics[:5])}
TREND CONTEXT: {trend_ctx}

Structure:
- Slide 1: Cover with strong hook title
- Slides 2 to {n_slides-1}: One tip per slide — title, body, optional code
- Slide {n_slides}: CTA slide

CODE RULES (critical):
- Max 5 lines of code per slide
- Max 40 characters per line — lines must be SHORT to fit the screen
- Use 4-space indentation
- Real runnable Python using the Anthropic SDK

Return ONLY valid JSON:
{{
  "topic": "overall topic",
  "topic_cluster": "{topics[0]}",
  "hook": "hook line (max 90 chars)",
  "slides": [
    {{
      "type": "cover",
      "title": "title (max 8 words)",
      "subtitle": "subtitle (max 10 words)"
    }},
    {{
      "type": "content",
      "tip_number": 1,
      "title": "tip title (max 6 words)",
      "body": "explanation in 1-2 sentences",
      "code_snippet": "python code max 5 lines max 40 chars each"
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

Include exactly {n_slides} slides (1 cover + {n_slides-2} content + 1 CTA)."""

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
            "caption":         data.get("hook","") + "\n\nSave this carousel for your next Claude API project.",
            "hashtags":        data.get("hashtags", evergreen),
            "audio_suggestion":"original audio",
            "slides":          data["slides"],
            "slide_count":     len(data["slides"]),
            "image_paths":     image_paths
        },
        "scheduling": {
            "recommended_day":         data.get("recommended_day", rec_day),
            "recommended_time_utc":    data.get("recommended_time_utc", rec_hour),
            "actual_publish_day":      None,
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

    # Upload slides to ImgBB
    if image_paths:
        try:
            from upload_media import upload_all_slides_imgbb
            print("\nUploading slides to ImgBB...")
            slide_urls = upload_all_slides_imgbb(image_paths)
            queue_entry["imgbb_url"]        = slide_urls[0] if slide_urls else None
            queue_entry["imgbb_slide_urls"] = slide_urls
            print(f"Uploaded {len([u for u in slide_urls if u])} slides")
        except Exception as e:
            print(f"Slide upload skipped: {e}")

    # Email notification
    try:
        from notify import notify_post_ready
        notify_post_ready(queue_entry)
    except Exception as e:
        print(f"Notification skipped: {e}")

    os.makedirs("queue", exist_ok=True)
    with open(filename, "w") as f:
        json.dump(queue_entry, f, indent=2)

    print(f"\nCarousel saved: {filename}")
    # Auto-commit and push queue file so Render dashboard can see it
    try:
        import subprocess
        subprocess.run(["git", "add", "queue/", "data/"], cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))), check=False)
        subprocess.run(["git", "commit", "-m", f"Generated post {post_id}"], cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))), check=False)
        subprocess.run(["git", "push"], cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))), check=False)
        print("Queue file pushed to GitHub — visible on Render dashboard")
    except Exception as e:
        print(f"Git push skipped: {e}")
    return filename, queue_entry

if __name__ == "__main__":
    generate_carousel()