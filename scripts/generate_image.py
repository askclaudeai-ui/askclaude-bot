import json
import os
import sys
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from dotenv import load_dotenv

load_dotenv()

# ── Brand colours ──────────────────────────────────────────────────────
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
        try:
            return ImageFont.truetype(p, size)
        except:
            pass
    return ImageFont.load_default()

def get_mono_font(size):
    candidates = [
        "/System/Library/Fonts/Menlo.ttc",
        "/Library/Fonts/Courier New.ttf",
    ]
    for p in candidates:
        try:
            return ImageFont.truetype(p, size)
        except:
            pass
    return ImageFont.load_default()

def wrap_text(text, font, max_width, draw):
    words = text.split()
    lines = []
    current = []
    for word in words:
        test = " ".join(current + [word])
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current.append(word)
        else:
            if current:
                lines.append(" ".join(current))
            current = [word]
    if current:
        lines.append(" ".join(current))
    return lines

def draw_bubble(d, x, y, w, h, radius, sw):
    cx     = x + w // 2
    t_half = int(w * 0.12)
    t_tip  = y + h + int(h * 0.26)
    d.polygon([(cx - t_half, y+h), (cx + t_half, y+h), (cx, t_tip)], fill=ORANGE)
    d.rounded_rectangle([x, y, x+w, y+h], radius=radius, fill=BG2)
    d.rounded_rectangle([x, y, x+w, y+h], radius=radius, outline=ORANGE, width=sw)

def generate_image(queue_file):
    with open(queue_file, "r") as f:
        post = json.load(f)

    image_text    = post["post"].get("image_text", "Claude API Tip")
    image_subtext = post["post"].get("image_subtext", "")
    post_id       = post["id"]

    S = 1080
    img = Image.new("RGB", (S, S), BG)
    d   = ImageDraw.Draw(img)

    # Grid
    sp = S // 4
    for x in range(0, S, sp): d.line([(x,0),(x,S)], fill=GRID, width=1)
    for y in range(0, S, sp): d.line([(0,y),(S,y)], fill=GRID, width=1)

    # Border
    d.rectangle([0,   0,   6, S], fill=ORANGE)
    d.rectangle([0,   0,   S, 6], fill=ORANGE)
    d.rectangle([S-6, 0,   S, S], fill=(*ORANGE, 76))
    d.rectangle([0,   S-6, S, S], fill=(*ORANGE, 76))

    # Top-left logo bubble
    bx, by, bw, bh = 66, 50, 144, 100
    draw_bubble(d, bx, by, bw, bh, radius=18, sw=5)
    pad = 14
    d.rounded_rectangle([bx+pad, by+pad, bx+bw-pad, by+pad+10],
                         radius=5, fill=ORANGE)
    y_bar = by + pad + 10 + 8
    for op in [0.60, 0.42, 0.28]:
        c = tuple(int(v*op) for v in ORANGE2)
        d.rounded_rectangle([bx+pad, y_bar, bx+bw-pad-20, y_bar+8],
                             radius=4, fill=c)
        y_bar += 8 + 6

    # Handle
    d.text((228, 90),  "Ask",        font=get_font(32, True), fill=WHITE,  anchor="lm")
    d.text((278, 90),  "Claude",     font=get_font(32),       fill=ORANGE, anchor="lm")
    d.text((228, 128), "@askclaude", font=get_mono_font(20),  fill=GRAY,   anchor="lm")

    # Main image text
    f_main = get_font(72, True)
    lines  = wrap_text(image_text, f_main, S - 120, d)
    y_text = 280
    for i, line in enumerate(lines[:3]):
        bbox   = d.textbbox((0, 0), line, font=f_main)
        tw     = bbox[2] - bbox[0]
        colour = ORANGE if i >= len(lines) // 2 else WHITE
        d.text(((S - tw) // 2, y_text), line, font=f_main, fill=colour)
        y_text += 90

    # Subtext
    if image_subtext:
        f_sub  = get_font(36)
        lines2 = wrap_text(image_subtext, f_sub, S - 160, d)
        y_sub  = y_text + 20
        for line in lines2[:2]:
            bbox = d.textbbox((0, 0), line, font=f_sub)
            tw   = bbox[2] - bbox[0]
            d.text(((S - tw) // 2, y_sub), line, font=f_sub, fill=GRAY)
            y_sub += 50

    # Divider
    d.rectangle([76, 620, S-84, 623], fill=GRID)
    d.rectangle([76, 620, 236,  623], fill=ORANGE)

    # Code card rows
    for ry, acc in [(660, GREEN), (740, ORANGE), (820, (129, 140, 248))]:
        d.rounded_rectangle([76, ry, S-84, ry+64], radius=10, fill=BG2)
        d.rounded_rectangle([100, ry+16, 288, ry+30], radius=7,
                             fill=tuple(int(x*0.8) for x in acc))
        d.rounded_rectangle([100, ry+38, 740, ry+50], radius=6, fill=DARK1)

    # Bottom text
    d.text((76, 988), "New post every  Mon  ·  Wed  ·  Thu",
           font=get_mono_font(22), fill=GRAY, anchor="lm")

    # Save CTA pill
    d.rounded_rectangle([692, 952, 992, 1010], radius=29, fill=ORANGE)
    d.text((842, 981), "Save this post",
           font=get_font(24, True), fill=WHITE, anchor="mm")

    # Save
    os.makedirs("queue/images", exist_ok=True)
    out_path = f"queue/images/{post_id}.png"
    img.save(out_path, "PNG", optimize=True)
    print(f"Image saved to {out_path}")
    return out_path

if __name__ == "__main__":
    if len(sys.argv) < 2:
        files = sorted([
            f for f in os.listdir("queue")
            if f.endswith(".json") and not f.startswith(".")
        ])
        if not files:
            print("No queue files found. Run generate_content.py first.")
            sys.exit(1)
        queue_file = f"queue/{files[-1]}"
        print(f"Using most recent queue file: {queue_file}")
    else:
        queue_file = sys.argv[1]

    generate_image(queue_file)