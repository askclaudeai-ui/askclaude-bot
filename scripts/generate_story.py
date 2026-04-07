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
GRID    = (210, 180,  80)   # grid lines
WHITE   = (255, 255, 255)
GREEN   = (78,  201, 176)   # terminal green

def get_font(size, bold=False):
    for p in ["/System/Library/Fonts/Helvetica.ttc",
              "/System/Library/Fonts/Arial.ttf"]:
        try: return ImageFont.truetype(p, size)
        except: pass
    return ImageFont.load_default()

def get_mono(size):
    for p in ["/System/Library/Fonts/Menlo.ttc",
              "/Library/Fonts/Courier New.ttf"]:
        try: return ImageFont.truetype(p, size)
        except: pass
    return ImageFont.load_default()

def parse_claude_json(text):
    if not text or not text.strip():
        raise ValueError("Empty response from Claude")
    clean = text.strip()
    # Find JSON object in response
    start = clean.find('{')
    end   = clean.rfind('}')
    if start != -1 and end != -1:
        clean = clean[start:end+1]
    clean = re.sub(r',\s*([}\]])', r'\1', clean)
    return json.loads(clean)

def draw_grid(d, w, h, sp=360):
    for x in range(0, w, sp): d.line([(x,0),(x,h)], fill=GRID, width=1)
    for y in range(0, h, sp): d.line([(0,y),(w,y)], fill=GRID, width=1)

def story_base():
    W, H = 1080, 1920
    img = Image.new("RGB", (W, H), BG)
    d   = ImageDraw.Draw(img)
    draw_grid(d, W, H)
    # Indigo top bar, gold bottom bar
    d.rectangle([0, 0,   W, 10], fill=INDIGO)
    d.rectangle([0, H-10, W, H], fill=GOLD)
    return img, d, W, H

def draw_logo(d, cx, y, size=120):
    """Uses exact same approach as working brand assets."""
    bw     = size
    bh     = int(size * 0.65)
    radius = max(14, int(bw * 0.15))
    stroke = max(4,  int(bw * 0.055))
    pad    = int(bw * 0.13)

    # Tail
    t     = int(bw * 0.11)
    tip_y = y + bh + int(bh * 0.30)
    d.polygon([(cx-t, y+bh),(cx+t, y+bh),(cx, tip_y)], fill=INDIGO)

    # Body fill
    bx = cx - bw//2
    d.rounded_rectangle([bx, y, bx+bw, y+bh], radius=radius, fill=BG2)

    # Stroke
    d.rounded_rectangle([bx, y, bx+bw, y+bh], radius=radius,
                         outline=INDIGO, width=stroke)

    # Top indigo bar
    bar_h = int(bh * 0.18)
    d.rounded_rectangle([bx+pad, y+pad, bx+bw-pad, y+pad+bar_h],
                         radius=bar_h//2, fill=INDIGO)

    # Three gold content bars
    yb = y + pad + bar_h + int(bh * 0.08)
    for op, w_ratio in [(1.0, 0.9), (0.65, 0.7), (0.40, 0.5)]:
        bh2  = int(bh * 0.10)
        bw2  = int((bw - pad*2) * w_ratio)
        c    = tuple(int(GOLD[i]*op + BG2[i]*(1-op)) for i in range(3))
        d.rounded_rectangle([bx+pad, yb, bx+pad+bw2, yb+bh2],
                             radius=bh2//2, fill=c)
        yb += bh2 + int(bh * 0.07)

def draw_handle(d, W, y):
    d.text((W//2, y), "@ask.claudeai",
           font=get_mono(28), fill=MID, anchor="mm")

def fit_text(text, max_size, min_size, max_width, d, bold=False):
    size = max_size
    while size >= min_size:
        f = get_font(size, bold)
        words = text.split()
        lines, current = [], []
        for word in words:
            test = " ".join(current + [word])
            bbox = d.textbbox((0,0), test, font=f)
            if bbox[2]-bbox[0] <= max_width:
                current.append(word)
            else:
                if current: lines.append(" ".join(current))
                current = [word]
        if current: lines.append(" ".join(current))
        if len(lines) * int(size * 1.3) <= max_size * 6:
            return f, lines
        size -= 4
    return get_font(min_size, bold), lines

def draw_centred_lines(d, lines, font, start_y, line_h,
                       colours=None, W=1080):
    y = start_y
    for i, line in enumerate(lines):
        bbox = d.textbbox((0,0), line, font=font)
        tw   = bbox[2]-bbox[0]
        col  = colours[i] if colours and i < len(colours) else TEXT
        d.text(((W-tw)//2, y), line, font=font, fill=col)
        y += line_h
    return y

def pill(d, cx, y, text, font, bg=INDIGO, fg=BG, pad_x=60, h=54):
    bbox = d.textbbox((0,0), text, font=font)
    tw   = bbox[2]-bbox[0]
    w    = tw + pad_x
    d.rounded_rectangle([cx-w//2, y, cx+w//2, y+h], radius=h//2, fill=bg)
    d.text((cx, y+h//2), text, font=font, fill=fg, anchor="mm")
    return y + h

def outline_pill(d, cx, y, text, font, col=INDIGO, pad_x=60, h=54):
    bbox = d.textbbox((0,0), text, font=font)
    tw   = bbox[2]-bbox[0]
    w    = tw + pad_x
    d.rounded_rectangle([cx-w//2, y, cx+w//2, y+h],
                         radius=h//2, fill=BG, outline=col, width=3)
    d.text((cx, y+h//2), text, font=font, fill=col, anchor="mm")
    return y + h

# ═══════════════════════════════════════════════════════════════════════
# Story renderers
# ═══════════════════════════════════════════════════════════════════════

def render_tip_repurpose(data):
    img, d, W, H = story_base()

    # ── Logo — large, centred at top third ───────────────────────────
    draw_logo(d, W//2, 160, size=200)

    # ── Label pill ───────────────────────────────────────────────────
    pill(d, W//2, 470, "ASK CLAUDE TIP",
         get_font(36, True), bg=INDIGO, fg=BG, pad_x=80, h=72)

    # ── Main tip text — large, fills middle ──────────────────────────
    tip = data.get("tip_text", "")
    f_tip, tip_lines = fit_text(tip, 108, 72, W-140, d, bold=True)
    line_h  = int(f_tip.size * 1.4)
    total_h = len(tip_lines) * line_h
    y_start = 620
    colours = [TEXT if i < (len(tip_lines)+1)//2 else INDIGO
               for i in range(len(tip_lines))]
    y = draw_centred_lines(d, tip_lines, f_tip, y_start, line_h,
                           colours=colours, W=W)

    # ── Divider ───────────────────────────────────────────────────────
    y += 40
    d.rectangle([W//2-100, y, W//2+100, y+4], fill=GRID)
    d.rectangle([W//2-100, y, W//2,     y+4], fill=INDIGO)

    # ── Subtext ───────────────────────────────────────────────────────
    y += 28
    sub = data.get("subtext", "")
    f_sub, sub_lines = fit_text(sub, 52, 40, W-160, d, bold=False)
    sub_h = int(f_sub.size * 1.5)
    y = draw_centred_lines(d, sub_lines, f_sub, y, sub_h,
                           colours=[MID]*10, W=W)

    # ── Save button ───────────────────────────────────────────────────
    y += 60
    pill(d, W//2, y, "Save this tip",
         get_font(48, True), bg=GOLD, fg=TEXT, pad_x=120, h=108)

    # ── Bottom branding ───────────────────────────────────────────────
    d.text((W//2, H-156), "New post  Mon · Wed · Thu",
           font=get_mono(32), fill=MID, anchor="mm")
    draw_handle(d, W, H-96)
    return img

def render_poll(data):
    img, d, W, H = story_base()

    draw_logo(d, W//2, 140, size=180)

    outline_pill(d, W//2, 420, "QUICK QUESTION",
                 get_font(36, True), col=INDIGO, pad_x=80, h=68)

    # Question
    q = data.get("question", "")
    f_q, q_lines = fit_text(q, 100, 68, W-140, d, bold=True)
    q_h = int(f_q.size * 1.45)
    y = draw_centred_lines(d, q_lines, f_q, 560, q_h,
                           colours=[TEXT]*10, W=W)

    y += 72
    options = data.get("options", ["Option A", "Option B"])
    f_opt = get_font(60, True)
    for i, opt in enumerate(options[:2]):
        if i == 0:
            pill(d, W//2, y, opt, f_opt,
                 bg=INDIGO, fg=BG, pad_x=120, h=128)
        else:
            outline_pill(d, W//2, y, opt, f_opt,
                         col=INDIGO, pad_x=120, h=128)
        y += 152

    y += 24
    d.rounded_rectangle([120, y, W-120, y+112],
                         radius=20, fill=BG2, outline=INDIGO, width=3)
    d.text((W//2, y+36), "👆 Add Poll sticker in Instagram app",
           font=get_font(32, True), fill=INDIGO, anchor="mm")
    d.text((W//2, y+82), "Stickers → Poll",
           font=get_font(28), fill=MID, anchor="mm")

    draw_handle(d, W, H-72)
    return img

def render_quiz(data):
    img, d, W, H = story_base()

    draw_logo(d, W//2, 100, size=160)

    pill(d, W//2, 352, "DEV QUIZ",
         get_font(38, True), bg=INDIGO, fg=BG, pad_x=80, h=72)

    q = data.get("question", "")
    f_q, q_lines = fit_text(q, 92, 64, W-140, d, bold=True)
    q_h = int(f_q.size * 1.45)
    y = draw_centred_lines(d, q_lines, f_q, 490, q_h,
                           colours=[TEXT]*10, W=W)

    y += 56
    options  = data.get("options", ["A","B","C","D"])
    f_opt    = get_font(50, True)
    f_letter = get_font(44, True)
    letters  = ["A","B","C","D"]

    for i, opt in enumerate(options[:4]):
        d.rounded_rectangle([80, y, W-80, y+112],
                             radius=56, fill=BG2, outline=INDIGO, width=3)
        # Letter badge
        d.ellipse([96, y+20, 176, y+92], fill=INDIGO)
        d.text((136, y+56), letters[i],
               font=f_letter, fill=BG, anchor="mm")
        # Option text
        f_t, t_lines = fit_text(opt, 48, 36, W-300, d)
        ty = y + 56 - int(f_t.size * len(t_lines) * 0.6)
        for tl in t_lines[:2]:
            d.text((196, ty), tl, font=f_t, fill=TEXT)
            ty += int(f_t.size * 1.3)
        y += 136

    y += 20
    d.text((W//2, y), "What's your answer? 👇",
           font=get_font(44, True), fill=GOLD, anchor="mm")

    draw_handle(d, W, H-72)
    return img

def render_behind_scenes(data):
    img, d, W, H = story_base()

    # Header on cream
    d.rounded_rectangle([60, 80, W-60, 168],
                         radius=20, fill=BG2, outline=INDIGO, width=3)
    d.text((W//2, 124), "Behind the scenes",
           font=get_font(40, True), fill=INDIGO, anchor="mm")
    d.text((W//2, 216), "How this post was generated",
           font=get_font(36), fill=MID, anchor="mm")

    # Terminal — stays dark, it's a terminal
    term_y = 280; term_h = 860
    d.rounded_rectangle([40, term_y, W-40, term_y+term_h],
                         radius=18, fill=(17,17,17))
    d.rounded_rectangle([40, term_y, W-40, term_y+term_h],
                         radius=18, outline=(55,55,55), width=2)
    d.rounded_rectangle([40, term_y, W-40, term_y+52],
                         radius=18, fill=(45,45,45))
    d.rectangle([40, term_y+26, W-40, term_y+52], fill=(45,45,45))
    for i, col in enumerate([(255,95,87),(254,188,46),(40,200,64)]):
        cx = 80 + i*32
        d.ellipse([cx-11, term_y+16, cx+11, term_y+38], fill=col)
    d.text((W//2, term_y+26), "claude_bot.py",
           font=get_mono(24), fill=(128,128,128), anchor="mm")

    prompt_lines = data.get("prompt_preview", [
        "# Prompt sent to Claude:",
        "",
        "You are a content creator",
        "for @ask.claudeai...",
        "",
        "# Claude response:",
        "Hook: generated ✓",
        "Caption: written ✓",
        "Hashtags: done ✓",
        "Image: created ✓",
        "",
        "→ Saved to review queue",
    ])
    f_term = get_mono(28)
    y_term = term_y + 68
    for line in prompt_lines[:16]:
        if line == "":
            y_term += 16
            continue
        if line.startswith("#"):   col = (106,153,85)
        elif "✓" in line:          col = GREEN
        elif line.startswith("→"): col = GOLD
        else:                       col = (204,204,204)
        d.text((64, y_term), line, font=f_term, fill=col)
        y_term += 42

    # Disclosure card — cream background
    disc_y = term_y + term_h + 30
    d.rounded_rectangle([60, disc_y, W-60, disc_y+114],
                         radius=14, fill=BG2)
    d.rectangle([60, disc_y, 70, disc_y+114], fill=INDIGO)
    d.rounded_rectangle([60, disc_y, 70, disc_y+114], radius=6, fill=INDIGO)
    d.text((90, disc_y+24), "✦  AI-generated content",
           font=get_font(28), fill=MID)
    d.text((90, disc_y+66), "✓  Reviewed & approved by a human",
           font=get_font(28), fill=TEXT)

    draw_handle(d, W, H-60)
    return img

def render_reel_teaser(data):
    img, d, W, H = story_base()

    outline_pill(d, W//2, 120, "NEW REEL OUT NOW",
                 get_font(36, True), col=INDIGO, pad_x=80, h=72)

    # Topic text — large, fills upper half
    topic = data.get("topic", "")
    f_t, t_lines = fit_text(topic, 104, 72, W-140, d, bold=True)
    t_h = int(f_t.size * 1.45)
    y = draw_centred_lines(d, t_lines, f_t, 280, t_h,
                           colours=[TEXT]*10, W=W)

    # Play button — centred
    y = max(y + 80, 820)
    cx, cy, r = W//2, y + 220, 210
    d.ellipse([cx-r, cy-r, cx+r, cy+r], fill=BG2)
    d.ellipse([cx-r, cy-r, cx+r, cy+r], outline=INDIGO, width=12)
    offset = 22
    d.polygon([
        (cx - 80 + offset, cy - 112),
        (cx - 80 + offset, cy + 112),
        (cx + 120 + offset, cy),
    ], fill=GOLD)

    y = cy + r + 64
    pill(d, W//2, y, "Watch the Reel →",
         get_font(48, True), bg=INDIGO, fg=BG, pad_x=120, h=108)
    y += 108 + 48
    d.text((W//2, y), "Tap the link in bio",
           font=get_font(44), fill=MID, anchor="mm")

    draw_logo(d, W//2, H-320, size=130)
    draw_handle(d, W, H-120)
    return img

def render_weekly_roundup(data, slide_num=1, total_slides=2):
    img, d, W, H = story_base()

    pill(d, W//2, 100, f"Week in review  ·  {slide_num} / {total_slides}",
         get_font(36, True), bg=INDIGO, fg=BG, pad_x=80, h=72)

    if slide_num == 1:
        d.text((W//2, 260), "This week on Ask Claude",
               font=get_font(64, True), fill=TEXT, anchor="mm")

        posts  = data.get("posts_summary", [])
        f_day  = get_font(40, True)
        f_post = get_font(48)
        y_pos  = 380
        for post in posts[:3]:
            day   = post.get("day", "")
            title = post.get("title", "")
            d.rounded_rectangle([80, y_pos, 240, y_pos+80],
                                 radius=40, fill=INDIGO)
            d.text((160, y_pos+40), day, font=f_day, fill=BG, anchor="mm")
            f_t, t_lines = fit_text(title, 48, 36, W-340, d)
            ty = y_pos + 16
            for tl in t_lines[:2]:
                d.text((268, ty), tl, font=f_t, fill=TEXT)
                ty += int(f_t.size * 1.3)
            y_pos = max(y_pos + 140, ty + 24)

        d.rectangle([80, y_pos+28, W-80, y_pos+32], fill=GRID)
        d.text((W//2, y_pos+80), "Swipe for next week's teaser →",
               font=get_font(40), fill=MID, anchor="mm")

        draw_logo(d, W//2, H-320, size=140)
        draw_handle(d, W, H-120)

    elif slide_num == 2:
        d.text((W//2, 260), "Coming next week",
               font=get_font(64, True), fill=TEXT, anchor="mm")

        teaser = data.get("teaser", "")
        f_t, t_lines = fit_text(teaser, 108, 72, W-160, d, bold=True)
        t_h = int(f_t.size * 1.45)
        colours = [TEXT if i < (len(t_lines)+1)//2 else INDIGO
                   for i in range(len(t_lines))]
        y = draw_centred_lines(d, t_lines, f_t, 450, t_h,
                               colours=colours, W=W)
        y += 100
        pill(d, W//2, y, "Follow for daily tips",
             get_font(48, True), bg=INDIGO, fg=BG, pad_x=120, h=108)

        draw_logo(d, W//2, H-320, size=140)
        draw_handle(d, W, H-120)

    return img

# ═══════════════════════════════════════════════════════════════════════
# Content generation
# ═══════════════════════════════════════════════════════════════════════

def generate_story_content(client, story_type, parent_post=None, recent_topics=None):
    parent_ctx = ""
    if parent_post:
        parent_ctx = f"""
Parent feed post:
- Topic: {parent_post.get('post',{}).get('topic','')}
- Hook: {parent_post.get('post',{}).get('hook','')}
"""
    avoid_str = ""
    if recent_topics:
        avoid_str = "RECENTLY USED TOPICS (do NOT repeat):\n" + "\n".join(f"- {t}" for t in recent_topics[:6])
    prompts = {
        "tip_repurpose": f"""You are creating a tip repurpose Instagram Story for @ask.claudeai.
{parent_ctx}
{avoid_str}
Extract the single most valuable standalone insight. Make it punchy and worth saving.
Return ONLY valid JSON:
{{
  "tip_text": "the main tip in 8-12 words",
  "subtext": "one supporting sentence explaining why this matters (max 18 words)",
  "caption": "story caption (hook + 2-3 lines + hashtags)"
}}""",

        "poll": f"""You are creating a poll Instagram Story for @ask.claudeai.
{parent_ctx}
{avoid_str}
Create an engaging either/or poll for developers. No obvious right answer.
Return ONLY valid JSON:
{{
  "question": "poll question (max 10 words)",
  "options": ["Option A (max 4 words)", "Option B (max 4 words)"],
  "caption": "caption teasing the poll (1-2 lines)"
}}""",

        "quiz": f"""You are creating a developer quiz Instagram Story for @ask.claudeai.
{parent_ctx}
{avoid_str}
Create a genuinely educational Claude API quiz with 4 options. One correct answer.
Return ONLY valid JSON:
{{
  "question": "quiz question (max 12 words, specific to Claude API)",
  "options": [
    "first option (max 6 words)",
    "second option (max 6 words)",
    "third option (max 6 words)",
    "fourth option (max 6 words)"
  ],
  "correct_index": 0,
  "explanation": "one sentence why the answer is correct (max 20 words)",
  "caption": "caption teasing the quiz (1-2 lines + hashtags)"
}}""",

        "behind_scenes": f"""You are creating a behind-the-scenes Instagram Story for @ask.claudeai.
{parent_ctx}
Show how this post was generated. Create realistic prompt lines.
Return ONLY valid JSON:
{{
  "prompt_preview": [
    "# Prompt sent to Claude:",
    "",
    "You are a content creator",
    "for @ask.claudeai...",
    "",
    "Topic: {parent_post.get('post',{}).get('topic','claude api') if parent_post else 'claude api'}",
    "",
    "# Claude response:",
    "Hook: generated ✓",
    "Caption: written ✓",
    "Hashtags: done ✓",
    "Image: created ✓",
    "",
    "→ Saved to review queue"
  ],
  "caption": "caption revealing how the bot works (2-3 lines)"
}}""",

        "reel_teaser": f"""You are creating a Reel teaser Instagram Story for @ask.claudeai.
{parent_ctx}
{avoid_str}
Tease today's Reel to drive views.
Return ONLY valid JSON:
{{
  "topic": "reel topic in 6-10 words (punchy, makes them want to watch)",
  "caption": "caption driving to the reel (1-2 lines)"
}}""",

        "weekly_roundup": f"""You are creating a 2-slide weekly roundup for @ask.claudeai.
Return ONLY valid JSON:
{{
  "slide1": {{
    "posts_summary": [
      {{"day": "Mon", "title": "post title max 6 words"}},
      {{"day": "Wed", "title": "post title max 6 words"}},
      {{"day": "Thu", "title": "post title max 6 words"}}
    ]
  }},
  "slide2": {{
    "teaser": "teaser for next week in 6-8 words"
  }},
  "caption": "weekly roundup caption (2-3 lines)"
}}"""
    }

    for attempt in range(3):
        try:
            message = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1500,
                messages=[{"role": "user",
                           "content": prompts.get(story_type, prompts["tip_repurpose"])}]
            )
            return parse_claude_json(message.content[0].text)
        except Exception as e:
            print(f"Attempt {attempt+1} failed: {e}")
            if attempt == 2:
                raise

def get_story_type_for_today(strategy):
    day = datetime.now().strftime("%A").lower()
    mapping = strategy.get("stories", {}).get("best_format_by_day", {
        "monday":    "tip_repurpose",
        "tuesday":   "poll",
        "wednesday": "behind_scenes",
        "thursday":  "reel_teaser",
        "friday":    "quiz",
        "sunday":    "weekly_roundup"
    })
    return mapping.get(day, "tip_repurpose")

def find_latest_published_post():
    queue_dir  = "queue"
    candidates = []
    for fname in os.listdir(queue_dir):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(queue_dir, fname)
        try:
            with open(path, "r") as f:
                post = json.load(f)
            if post.get("status") in ("published", "approved"):
                candidates.append((post.get("created_at",""), path, post))
        except:
            continue
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][2]

MANUAL_ACTIONS = {
    "poll": {
        "required": True,
        "action":   "Add Poll sticker",
        "steps": [
            "Open the story in Instagram after posting",
            "Tap the Sticker icon",
            "Select Poll",
            "Set the two options to match your post",
            "Position and post"
        ]
    },
    "quiz": {
        "required": True,
        "action":   "Add Quiz sticker",
        "steps": [
            "Open the story in Instagram after posting",
            "Tap the Sticker icon",
            "Select Quiz",
            "Enter the question and 4 answers",
            "Mark the correct answer",
            "Position and post"
        ]
    },
    "reel_teaser": {
        "required": False,
        "action":   "Add Link sticker (optional)",
        "steps": [
            "Copy your Reel URL",
            "Add a Link sticker pointing to it",
            "Position above the Watch the Reel button"
        ]
    }
}

def generate_story(story_type=None):
    client   = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    strategy = json.load(open("data/strategy.json"))

    if not story_type:
        story_type = get_story_type_for_today(strategy)

    print(f"Generating story: {story_type}")

    parent_post = find_latest_published_post()
    if parent_post:
        print(f"Parent post: {parent_post.get('post',{}).get('topic','')}")

    # Get recent story topics to avoid repetition
    recent_story_topics = []
    try:
        all_queue = list(os.listdir("queue"))
        for f in sorted(all_queue, reverse=True)[:20]:
            if not f.endswith(".json"): continue
            try:
                d = json.load(open(f"queue/{f}"))
                if d.get("content_type") == "story":
                    t = d.get("post", {}).get("story_data", {})
                    tip = t.get("tip_text", "") or t.get("question", "") or t.get("topic", "")
                    if tip: recent_story_topics.append(tip.lower())
            except: continue
    except: pass

    data = generate_story_content(client, story_type, parent_post, recent_story_topics)
    print("Content generated")

    post_id   = str(uuid.uuid4())[:8]
    story_dir = f"queue/stories/{post_id}"
    os.makedirs(story_dir, exist_ok=True)

    image_paths = []

    if story_type == "tip_repurpose":
        img  = render_tip_repurpose(data)
        path = f"{story_dir}/story_01.png"
        img.save(path, "PNG", optimize=True)
        image_paths.append(path)

    elif story_type == "poll":
        img  = render_poll(data)
        path = f"{story_dir}/story_01.png"
        img.save(path, "PNG", optimize=True)
        image_paths.append(path)

    elif story_type == "quiz":
        img  = render_quiz(data)
        path = f"{story_dir}/story_01.png"
        img.save(path, "PNG", optimize=True)
        image_paths.append(path)

    elif story_type == "behind_scenes":
        img  = render_behind_scenes(data)
        path = f"{story_dir}/story_01.png"
        img.save(path, "PNG", optimize=True)
        image_paths.append(path)

    elif story_type == "reel_teaser":
        img  = render_reel_teaser(data)
        path = f"{story_dir}/story_01.png"
        img.save(path, "PNG", optimize=True)
        image_paths.append(path)

    elif story_type == "weekly_roundup":
        slides_to_render = [
            (1, data.get("slide1", {})),
            (2, data.get("slide2", {})),
        ]
        for slide_num, slide_data in slides_to_render:
            img  = render_weekly_roundup(slide_data,
                                         slide_num=slide_num,
                                         total_slides=2)
            path = f"{story_dir}/story_{len(image_paths)+1:02d}.png"
            img.save(path, "PNG", optimize=True)
            image_paths.append(path)

    print(f"Rendered {len(image_paths)} image(s)")

    manual_action = MANUAL_ACTIONS.get(story_type, {
        "required": False, "action": None, "steps": []
    })

    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"queue/{date_str}_{post_id}.json"

    queue_entry = {
        "id":                 post_id,
        "content_type":       "story",
        "story_type":         story_type,
        "status":             "pending",
        "created_at":         datetime.now().isoformat(),
        "published_at":       None,
        "instagram_media_id": None,
        "imgbb_url":          None,
        "cloudinary_story_urls": [],
        "parent_post_id":     parent_post.get("id") if parent_post else None,
        "manual_action":      manual_action,
        "generation_inputs": {
            "story_type":   story_type,
            "parent_topic": parent_post.get("post",{}).get("topic","") if parent_post else ""
        },
        "post": {
            "caption":     data.get("caption", ""),
            "image_paths": image_paths,
            "slide_count": len(image_paths),
            "story_data":  data
        },
        "scheduling": {
            "recommended_time_utc": strategy.get("stories",{}).get("optimal_post_hour_utc", 18),
            "actual_publish_time":  None
        }
    }

    # Upload to Cloudinary
    if image_paths:
        try:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from upload_media import upload_all_story_images
            print("Uploading story images to Cloudinary...")
            story_urls = upload_all_story_images(image_paths)
            queue_entry["cloudinary_story_urls"] = story_urls
            queue_entry["imgbb_url"] = story_urls[0] if story_urls else None
            print(f"Uploaded {len([u for u in story_urls if u])} images")
        except Exception as e:
            print(f"Story upload skipped: {e}")

    # Email notification
    try:
        from notify import notify_post_ready
        notify_post_ready(queue_entry)
    except Exception as e:
        print(f"Notification skipped: {e}")

    with open(filename, "w") as f:
        json.dump(queue_entry, f, indent=2)

    print(f"\nStory saved: {filename}")
    if manual_action.get("required"):
        print(f"⚠️  Manual action required: {manual_action['action']}")
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
    story_type = sys.argv[1] if len(sys.argv) > 1 else None
    generate_story(story_type)