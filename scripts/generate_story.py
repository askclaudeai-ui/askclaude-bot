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

BG      = (13,  17,  23)
BG2     = (17,  24,  39)
GRID    = (28,  35,  51)
ORANGE  = (249, 115, 22)
ORANGE2 = (251, 146, 60)
WHITE   = (255, 255, 255)
LIGHT   = (209, 213, 219)
GRAY    = (107, 114, 128)
MUTED   = (75,  85,  99)
DARK1   = (17,  24,  39)
GREEN   = (78,  201, 176)
PURPLE  = (124, 58,  237)
PURPLE2 = (167, 139, 250)

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
    clean = text.strip()
    if "```" in clean:
        parts = clean.split("```")
        clean = parts[1] if len(parts) > 1 else clean
        if clean.startswith("json"): clean = clean[4:]
    clean = clean.strip()
    clean = re.sub(r'(?<=[\[,])\s*#(\w+)"', r' "#\1"', clean)
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
    d.rectangle([0, 0,   W, 8],  fill=ORANGE)
    d.rectangle([0, H-8, W, H],  fill=(*ORANGE, 80))
    return img, d, W, H

def draw_logo(d, cx, y, size=110):
    bw = size; bh = int(size * 0.65)
    bx = cx - bw//2
    t_half = int(bw * 0.12)
    t_tip  = y + bh + int(bh * 0.28)
    d.polygon([(cx-t_half,y+bh),(cx+t_half,y+bh),(cx,t_tip)], fill=ORANGE)
    d.rounded_rectangle([bx,y,bx+bw,y+bh], radius=int(bw*0.15), fill=BG2)
    d.rounded_rectangle([bx,y,bx+bw,y+bh], radius=int(bw*0.15),
                         outline=ORANGE, width=max(4, size//20))
    pad = int(bw*0.14)
    d.rounded_rectangle([bx+pad,y+pad,bx+bw-pad,y+pad+int(bh*0.22)],
                         radius=int(bh*0.1), fill=ORANGE)
    yb = y+pad+int(bh*0.22)+int(bh*0.1)
    for op in [0.65, 0.48, 0.32]:
        c = tuple(int(v*op) for v in ORANGE2)
        d.rounded_rectangle([bx+pad,yb,bx+bw-pad-int(bw*0.18*op),yb+int(bh*0.14)],
                             radius=int(bh*0.06), fill=c)
        yb += int(bh*0.14)+int(bh*0.08)

def draw_handle(d, W, y):
    d.text((W//2, y), "@ask.claudeai",
           font=get_mono(28), fill=MUTED, anchor="mm")

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
        col  = colours[i] if colours and i < len(colours) else WHITE
        d.text(((W-tw)//2, y), line, font=font, fill=col)
        y += line_h
    return y

def pill(d, cx, y, text, font, bg=ORANGE, fg=BG, pad_x=60, h=54):
    bbox = d.textbbox((0,0), text, font=font)
    tw   = bbox[2]-bbox[0]
    w    = tw + pad_x
    d.rounded_rectangle([cx-w//2, y, cx+w//2, y+h], radius=h//2, fill=bg)
    d.text((cx, y+h//2), text, font=font, fill=fg, anchor="mm")
    return y + h

def outline_pill(d, cx, y, text, font, col=ORANGE, pad_x=60, h=54):
    bbox = d.textbbox((0,0), text, font=font)
    tw   = bbox[2]-bbox[0]
    w    = tw + pad_x
    d.rounded_rectangle([cx-w//2, y, cx+w//2, y+h],
                         radius=h//2, fill=BG2, outline=col, width=3)
    d.text((cx, y+h//2), text, font=font, fill=col, anchor="mm")
    return y + h

# ═══════════════════════════════════════════════════════════════════════
# Story renderers
# ═══════════════════════════════════════════════════════════════════════

def render_tip_repurpose(data):
    img, d, W, H = story_base()
    draw_logo(d, W//2, 148, size=130)
    pill(d, W//2, 390, "ASK CLAUDE TIP",
         get_font(26, True), pad_x=80, h=52)
    tip  = data.get("tip_text", "")
    f_tip, tip_lines = fit_text(tip, 72, 48, W-140, d, bold=True)
    line_h = int(f_tip.size * 1.35)
    colours = [WHITE if i < len(tip_lines)//2 else ORANGE
               for i in range(len(tip_lines))]
    y = draw_centred_lines(d, tip_lines, f_tip, 478, line_h,
                           colours=colours, W=W)
    y += 24
    d.rectangle([W//2-80, y, W//2+80, y+3], fill=GRID)
    d.rectangle([W//2-80, y, W//2,    y+3], fill=ORANGE)
    y += 28
    sub = data.get("subtext", "")
    f_sub, sub_lines = fit_text(sub, 46, 36, W-160, d, bold=False)
    sub_h = int(f_sub.size * 1.5)
    y = draw_centred_lines(d, sub_lines, f_sub, y, sub_h,
                           colours=[LIGHT]*10, W=W)
    y += 40
    pill(d, W//2, y, "Save this tip",
         get_font(40, True), pad_x=100, h=84)
    d.text((W//2, H-148), "New post  Mon · Wed · Thu",
           font=get_mono(28), fill=MUTED, anchor="mm")
    draw_handle(d, W, H-96)
    return img

def render_poll(data):
    img, d, W, H = story_base()
    draw_logo(d, W//2, 148, size=120)
    outline_pill(d, W//2, 370, "QUICK QUESTION",
                 get_font(28, True), pad_x=80, h=52)
    q = data.get("question", "")
    f_q, q_lines = fit_text(q, 76, 52, W-140, d, bold=True)
    q_h = int(f_q.size * 1.4)
    y = draw_centred_lines(d, q_lines, f_q, 460, q_h,
                           colours=[WHITE]*10, W=W)
    y += 60
    options = data.get("options", ["Option A", "Option B"])
    f_opt = get_font(52, True)
    for i, opt in enumerate(options[:2]):
        if i == 1:
            outline_pill(d, W//2, y, opt, f_opt, pad_x=120, h=110)
        else:
            pill(d, W//2, y, opt, f_opt, bg=ORANGE, fg=BG, pad_x=120, h=110)
        y += 130
    y += 20
    # Poll sticker reminder box
    d.rounded_rectangle([100, y, W-100, y+100],
                         radius=16, fill=BG2, outline=ORANGE, width=3)
    d.text((W//2, y+30), "👆 Add Poll sticker in Instagram app",
           font=get_font(30, True), fill=ORANGE, anchor="mm")
    d.text((W//2, y+70), "Settings → Stickers → Poll",
           font=get_font(26), fill=LIGHT, anchor="mm")
    y += 120
    d.text((W//2, y+20), "Comment your answer below 👇",
           font=get_font(36), fill=LIGHT, anchor="mm")
    draw_handle(d, W, H-60)
    return img

def render_quiz(data):
    """Quiz story — question with 4 options, correct answer indicated."""
    img, d, W, H = story_base()
    draw_logo(d, W//2, 100, size=110)

    # Header
    pill(d, W//2, 310, "DEV QUIZ",
         get_font(30, True), bg=PURPLE, fg=WHITE, pad_x=80, h=60)

    # Question
    q = data.get("question", "")
    f_q, q_lines = fit_text(q, 70, 50, W-140, d, bold=True)
    q_h = int(f_q.size * 1.4)
    y = draw_centred_lines(d, q_lines, f_q, 420, q_h,
                           colours=[WHITE]*10, W=W)
    y += 50

    # 4 answer options
    options      = data.get("options", ["A", "B", "C", "D"])
    correct_idx  = data.get("correct_index", 0)
    f_opt        = get_font(44, True)
    f_letter     = get_font(36, True)

    for i, opt in enumerate(options[:4]):
        is_correct = (i == correct_idx)
        bg  = PURPLE if is_correct else BG2
        fg  = WHITE
        out = PURPLE if is_correct else GRAY

        # Option pill
        d.rounded_rectangle([80, y, W-80, y+96],
                             radius=48, fill=bg, outline=out, width=3)

        # Letter badge
        letters = ["A", "B", "C", "D"]
        letter_bg = ORANGE if is_correct else GRID
        d.ellipse([96, y+18, 96+60, y+78], fill=letter_bg)
        d.text((126, y+48), letters[i],
               font=f_letter, fill=WHITE, anchor="mm")

        # Option text
        f_t, t_lines = fit_text(opt, 42, 32, W-280, d)
        ty = y + 48 - int(f_t.size * len(t_lines) * 0.6)
        for tl in t_lines[:2]:
            d.text((180, ty), tl, font=f_t, fill=fg)
            ty += int(f_t.size * 1.3)

        # Correct indicator
        if is_correct:
            d.text((W-110, y+48), "✓",
                   font=get_font(48, True), fill=GREEN, anchor="mm")

        y += 120

    # Quiz sticker reminder
    y += 10
    d.rounded_rectangle([100, y, W-100, y+100],
                         radius=16, fill=BG2, outline=PURPLE, width=3)
    d.text((W//2, y+30), "👆 Add Quiz sticker in Instagram app",
           font=get_font(30, True), fill=PURPLE2, anchor="mm")
    d.text((W//2, y+70), "Settings → Stickers → Quiz",
           font=get_font(26), fill=LIGHT, anchor="mm")

    draw_handle(d, W, H-60)
    return img

def render_behind_scenes(data):
    img, d, W, H = story_base()
    d.rounded_rectangle([60, 80, W-60, 164],
                         radius=20, fill=BG2, outline=ORANGE, width=3)
    d.text((W//2, 122), "Behind the scenes",
           font=get_font(40, True), fill=ORANGE, anchor="mm")
    d.text((W//2, 210), "How this post was generated",
           font=get_font(36), fill=LIGHT, anchor="mm")
    term_y = 270; term_h = 860
    d.rounded_rectangle([40, term_y, W-40, term_y+term_h],
                         radius=18, fill=(17,17,17))
    d.rounded_rectangle([40, term_y, W-40, term_y+term_h],
                         radius=18, outline=GRID, width=2)
    d.rounded_rectangle([40, term_y, W-40, term_y+52],
                         radius=18, fill=(45,45,45))
    d.rectangle([40, term_y+26, W-40, term_y+52], fill=(45,45,45))
    for i, col in enumerate([(255,95,87),(254,188,46),(40,200,64)]):
        cx = 80 + i*32
        d.ellipse([cx-11, term_y+16, cx+11, term_y+38], fill=col)
    d.text((W//2, term_y+26), "claude_bot.py",
           font=get_mono(24), fill=GRAY, anchor="mm")
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
        elif line.startswith("→"): col = ORANGE
        else:                       col = (204,204,204)
        d.text((64, y_term), line, font=f_term, fill=col)
        y_term += 42
    disc_y = term_y + term_h + 30
    d.rounded_rectangle([60, disc_y, W-60, disc_y+110],
                         radius=14, fill=BG2)
    d.rectangle([60, disc_y, 68, disc_y+110], fill=ORANGE)
    d.rounded_rectangle([60, disc_y, 68, disc_y+110], radius=4, fill=ORANGE)
    d.text((88, disc_y+22), "✦  AI-generated content",
           font=get_font(28), fill=GRAY)
    d.text((88, disc_y+62), "✓  Reviewed & approved by a human",
           font=get_font(28), fill=LIGHT)
    draw_handle(d, W, H-60)
    return img

def render_reel_teaser(data):
    img, d, W, H = story_base()
    outline_pill(d, W//2, 100, "NEW REEL OUT NOW",
                 get_font(28, True), pad_x=80, h=56)
    topic = data.get("topic", "")
    f_t, t_lines = fit_text(topic, 72, 52, W-140, d, bold=True)
    t_h = int(f_t.size * 1.4)
    y = draw_centred_lines(d, t_lines, f_t, 210, t_h,
                           colours=[WHITE]*10, W=W)
    y = max(y + 60, 580)
    cx, cy, r = W//2, y+200, 190
    d.ellipse([cx-r, cy-r, cx+r, cy+r], fill=BG2)
    d.ellipse([cx-r, cy-r, cx+r, cy+r], outline=ORANGE, width=10)
    offset = 18
    d.polygon([
        (cx - 70 + offset, cy - 100),
        (cx - 70 + offset, cy + 100),
        (cx + 110 + offset, cy),
    ], fill=ORANGE)
    y = cy + r + 50
    pill(d, W//2, y, "Watch the Reel →",
         get_font(40, True), pad_x=100, h=88)
    y += 88 + 36
    d.text((W//2, y), "Tap the link in bio",
           font=get_font(36), fill=LIGHT, anchor="mm")
    draw_logo(d, W//2, H-280, size=110)
    draw_handle(d, W, H-96)
    return img

def render_weekly_roundup(data, slide_num=1, total_slides=2):
    img, d, W, H = story_base()
    pill(d, W//2, 80, f"Week in review  ·  {slide_num} / {total_slides}",
         get_font(30, True), pad_x=80, h=60)
    if slide_num == 1:
        d.text((W//2, 210), "This week on Ask Claude",
               font=get_font(54, True), fill=WHITE, anchor="mm")
        posts  = data.get("posts_summary", [])
        f_day  = get_font(32, True)
        f_post = get_font(40)
        y_pos  = 320
        for post in posts[:4]:
            day   = post.get("day", "")
            title = post.get("title", "")
            d.rounded_rectangle([80, y_pos, 220, y_pos+58],
                                 radius=29, fill=BG2, outline=ORANGE, width=3)
            d.text((150, y_pos+29), day, font=f_day, fill=ORANGE, anchor="mm")
            f_t, t_lines = fit_text(title, 40, 32, W-300, d)
            ty = y_pos + 8
            for tl in t_lines[:2]:
                d.text((250, ty), tl, font=f_t, fill=WHITE)
                ty += int(f_t.size * 1.3)
            y_pos = max(y_pos + 100, ty + 20)
        d.rectangle([80, y_pos+20, W-80, y_pos+23], fill=GRID)
        d.text((W//2, y_pos+60), "Swipe for next week's teaser →",
               font=get_font(34), fill=LIGHT, anchor="mm")
    elif slide_num == 2:
        d.text((W//2, 210), "Coming next week",
               font=get_font(54, True), fill=WHITE, anchor="mm")
        teaser = data.get("teaser", "")
        f_t, t_lines = fit_text(teaser, 76, 52, W-160, d, bold=True)
        t_h = int(f_t.size * 1.4)
        colours = [WHITE if i < len(t_lines)//2 else ORANGE
                   for i in range(len(t_lines))]
        y = draw_centred_lines(d, t_lines, f_t, 380, t_h,
                               colours=colours, W=W)
        y += 80
        pill(d, W//2, y, "Follow for daily tips",
             get_font(40, True), pad_x=100, h=88)
    draw_logo(d, W//2, H-280, size=110)
    draw_handle(d, W, H-96)
    return img

# ═══════════════════════════════════════════════════════════════════════
# Content generation
# ═══════════════════════════════════════════════════════════════════════

def generate_story_content(client, story_type, parent_post=None):
    parent_ctx = ""
    if parent_post:
        parent_ctx = f"""
Parent feed post:
- Topic: {parent_post.get('post',{}).get('topic','')}
- Hook: {parent_post.get('post',{}).get('hook','')}
- Caption preview: {parent_post.get('post',{}).get('caption','')[:200]}
"""
    prompts = {
        "tip_repurpose": f"""You are creating a tip repurpose Instagram Story for @ask.claudeai.
{parent_ctx}
Extract the single most valuable standalone insight. Make it punchy and worth saving.
Return ONLY valid JSON:
{{
  "tip_text": "the main tip in 8-12 words",
  "subtext": "one supporting sentence explaining why this matters (max 18 words)",
  "caption": "story caption (hook + 2-3 lines + hashtags)"
}}""",

        "poll": f"""You are creating a poll Instagram Story for @ask.claudeai.
{parent_ctx}
Create an engaging either/or poll for developers. No obvious right answer.
Return ONLY valid JSON:
{{
  "question": "poll question (max 10 words)",
  "options": ["Option A (max 4 words)", "Option B (max 4 words)"],
  "caption": "caption teasing the poll (1-2 lines)"
}}""",

        "quiz": f"""You are creating a developer quiz Instagram Story for @ask.claudeai.
{parent_ctx}
Create a genuinely educational Claude API quiz question with 4 options. One correct answer.
The question should teach something useful even if the viewer gets it wrong.
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
  "explanation": "one sentence explaining why the answer is correct (max 20 words)",
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

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1500,
        messages=[{"role": "user",
                   "content": prompts.get(story_type, prompts["tip_repurpose"])}]
    )
    return parse_claude_json(message.content[0].text)

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

# Manual action instructions per story type
MANUAL_ACTIONS = {
    "poll": {
        "required": True,
        "action":   "Add Poll sticker",
        "steps": [
            "Open Instagram Stories",
            "Tap the Sticker icon (smiley face)",
            "Select 'Poll'",
            f"Set the two options to match your post",
            "Position the sticker on the image"
        ]
    },
    "quiz": {
        "required": True,
        "action":   "Add Quiz sticker",
        "steps": [
            "Open Instagram Stories",
            "Tap the Sticker icon (smiley face)",
            "Select 'Quiz'",
            "Enter the question and 4 answers",
            "Mark the correct answer",
            "Position the sticker on the image"
        ]
    },
    "reel_teaser": {
        "required": False,
        "action":   "Add Link sticker (optional)",
        "steps": [
            "Open the Story after posting",
            "Tap 'Add Link' sticker",
            "Paste your Reel URL",
            "Position above the 'Watch the Reel' button"
        ]
    },
    "behind_scenes": {
        "required": False,
        "action":   "Add Link sticker to parent post (optional)",
        "steps": [
            "Copy the parent feed post URL",
            "Add a Link sticker pointing to it"
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

    data = generate_story_content(client, story_type, parent_post)
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

    # Get manual action instructions for this story type
    manual_action = MANUAL_ACTIONS.get(story_type, {
        "required": False, "action": None, "steps": []
    })

    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"queue/stories/{date_str}_{post_id}.json"

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

    # Upload story images to Cloudinary
    if image_paths:
        try:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from upload_media import upload_all_story_images
            print("Uploading story images to Cloudinary...")
            story_urls = upload_all_story_images(image_paths)
            queue_entry["cloudinary_story_urls"] = story_urls
            queue_entry["imgbb_url"] = story_urls[0] if story_urls else None
            print(f"Uploaded {len([u for u in story_urls if u])} story images")
        except Exception as e:
            print(f"Story upload skipped: {e}")

    # Send email notification
    try:
        from notify import notify_post_ready
        notify_post_ready(queue_entry)
    except Exception as e:
        print(f"Notification skipped: {e}")

    with open(filename, "w") as f:
        json.dump(queue_entry, f, indent=2)

    print(f"\nStory saved: {filename}")
    if manual_action.get("required"):
        print(f"⚠️  Manual action required after posting: {manual_action['action']}")
    return filename, queue_entry

if __name__ == "__main__":
    import sys
    story_type = sys.argv[1] if len(sys.argv) > 1 else None
    generate_story(story_type)