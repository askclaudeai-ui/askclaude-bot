import json
import os
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
GRID    = (210, 180,  80)   # subtle grid lines
WHITE   = (255, 255, 255)
GREEN   = (16,  185, 129)

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

def draw_logo_bubble(d, x, y, w, h, radius=18, sw=5):
    """Speech bubble logo in indigo."""
    cx     = x + w // 2
    t_half = int(w * 0.12)
    t_tip  = y + h + int(h * 0.26)
    # Tail
    d.polygon([(cx-t_half, y+h),(cx+t_half, y+h),(cx, t_tip)], fill=INDIGO)
    # Body
    d.rounded_rectangle([x, y, x+w, y+h], radius=radius, fill=BG2)
    d.rounded_rectangle([x, y, x+w, y+h], radius=radius, outline=INDIGO, width=sw)
    # Top bar
    pad = int(w * 0.12)
    d.rounded_rectangle([x+pad, y+pad, x+w-pad, y+pad+10],
                         radius=5, fill=INDIGO)
    # Content bars
    yb = y + pad + 10 + 7
    for op in [1.0, 0.65, 0.40]:
        c = tuple(int(GOLD[i]*op + BG2[i]*(1-op)) for i in range(3))
        bw2 = int((w - pad*2) * (0.85 if op == 1.0 else 0.65 if op == 0.65 else 0.45))
        d.rounded_rectangle([x+pad, yb, x+pad+bw2, yb+8],
                             radius=4, fill=c)
        yb += 8 + 6

def generate_image(queue_file):
    with open(queue_file, "r") as f:
        post = json.load(f)

    image_text    = post["post"].get("image_text", "Claude API Tip")
    image_subtext = post["post"].get("image_subtext", "")
    post_id       = post["id"]

    S = 1080
    img = Image.new("RGB", (S, S), BG)
    d   = ImageDraw.Draw(img)

    # ── Subtle grid ───────────────────────────────────────────────────
    sp = S // 4
    for x in range(0, S, sp): d.line([(x,0),(x,S)], fill=GRID, width=1)
    for y in range(0, S, sp): d.line([(0,y),(S,y)], fill=GRID, width=1)

    # ── Border ────────────────────────────────────────────────────────
    d.rectangle([0,   0,   8,   S], fill=INDIGO)
    d.rectangle([0,   0,   S,   8], fill=INDIGO)
    d.rectangle([S-8, 0,   S,   S], fill=GOLD)
    d.rectangle([0,   S-8, S,   S], fill=GOLD)

    # ── Logo + handle top left ────────────────────────────────────────
    bx, by, bw, bh = 56, 48, 148, 104
    draw_logo_bubble(d, bx, by, bw, bh, radius=20, sw=6)

    d.text((224, 88),  "Ask",           font=get_font(32, True), fill=TEXT,   anchor="lm")
    d.text((276, 88),  "Claude",        font=get_font(32),       fill=INDIGO, anchor="lm")
    d.text((224, 128), "@ask.claudeai", font=get_mono(20),       fill=MID,    anchor="lm")

    # ── Tip label pill ────────────────────────────────────────────────
    d.rounded_rectangle([S//2-140, 210, S//2+140, 264],
                         radius=27, fill=INDIGO)
    d.text((S//2, 237), "CLAUDE API TIP",
           font=get_font(26, True), fill=BG, anchor="mm")

    # ── Main image text ───────────────────────────────────────────────
    f_main = get_font(78, True)
    lines  = wrap_text(image_text, f_main, S - 120, d)
    y_text = 310
    for i, line in enumerate(lines[:3]):
        bbox = d.textbbox((0, 0), line, font=f_main)
        tw   = bbox[2] - bbox[0]
        col  = INDIGO if i >= len(lines) // 2 else TEXT
        d.text(((S - tw) // 2, y_text), line, font=f_main, fill=col)
        y_text += 96

    # ── Subtext ───────────────────────────────────────────────────────
    if image_subtext:
        f_sub  = get_font(38)
        lines2 = wrap_text(image_subtext, f_sub, S - 160, d)
        y_sub  = y_text + 20
        for line in lines2[:2]:
            bbox = d.textbbox((0, 0), line, font=f_sub)
            tw   = bbox[2] - bbox[0]
            d.text(((S - tw) // 2, y_sub), line, font=f_sub, fill=MID)
            y_sub += 54

    # ── Divider ───────────────────────────────────────────────────────
    d.rectangle([76, 630, S-84, 634], fill=GRID)
    d.rectangle([76, 630, 260, 634],  fill=INDIGO)

    # ── Code card rows ────────────────────────────────────────────────
    code_rows = [
        (670, GREEN,   (16, 185, 129)),
        (750, GOLD,    (217, 119, 6)),
        (830, INDIGO2, (79, 70, 229)),
    ]
    for ry, acc, _ in code_rows:
        d.rounded_rectangle([76, ry, S-84, ry+68],
                             radius=12, fill=BG2)
        d.rounded_rectangle([76, ry, 84, ry+68],
                             radius=0, fill=acc)
        d.rounded_rectangle([76, ry, 84, ry+68],
                             radius=6, fill=acc)
        # Simulated code line
        d.rounded_rectangle([100, ry+18, 320, ry+34],
                             radius=7, fill=acc)
        d.rounded_rectangle([100, ry+42, 720, ry+55],
                             radius=6, fill=TEXT)

    # ── Bottom branding ───────────────────────────────────────────────
    d.text((76, 990), "New post every  Mon  ·  Wed  ·  Thu",
           font=get_mono(22), fill=MID, anchor="lm")

    # Save CTA pill
    d.rounded_rectangle([680, 952, 1004, 1016], radius=32, fill=INDIGO)
    d.text((842, 984), "Save this post",
           font=get_font(26, True), fill=BG, anchor="mm")

    # ── Save ──────────────────────────────────────────────────────────
    os.makedirs("queue/images", exist_ok=True)
    out_path = f"queue/images/{post_id}.png"
    img.save(out_path, "PNG", optimize=True)
    print(f"Image saved to {out_path}")

    # Upload to Cloudinary immediately — needed for email preview and Late API publishing
    try:
        import sys
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from upload_media import upload_image_cloudinary_feed
        cloudinary_url = upload_image_cloudinary_feed(out_path)
        print(f"Uploaded to Cloudinary: {cloudinary_url}")

        # Update queue file with Cloudinary URL
        queue_file_path = queue_file.replace("queue/images/", "queue/") \
                                    .replace(f"/{post_id}.png", ".json")
        # Find the correct queue file
        for qf in os.listdir("queue"):
            if qf.endswith(".json") and not qf.startswith("."):
                qpath = f"queue/{qf}"
                try:
                    with open(qpath) as f:
                        qdata = json.load(f)
                    if qdata.get("id") == post_id:
                        qdata["cloudinary_image_url"] = cloudinary_url
                        qdata["imgbb_url"]             = cloudinary_url
                        with open(qpath, "w") as f:
                            json.dump(qdata, f, indent=2)
                        print(f"Queue file updated: {qpath}")
                        # Send email notification now that image is ready
                        try:
                            from notify import notify_post_ready
                            notify_post_ready(qdata)
                        except Exception as e:
                            print(f"Notification skipped: {e}")
                        break
                except:
                    continue
    except Exception as e:
        print(f"Cloudinary upload skipped: {e}")
    # Auto-commit and push queue file so Render dashboard can see it
    try:
        import subprocess
        subprocess.run(["git", "add", "queue/", "data/"], cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))), check=False)
        subprocess.run(["git", "commit", "-m", f"Generated post {post_id}"], cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))), check=False)
        subprocess.run(["git", "push"], cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))), check=False)
        print("Queue file pushed to GitHub — visible on Render dashboard")
    except Exception as e:
        print(f"Git push skipped: {e}")

    return out_path

if __name__ == "__main__":
    if len(sys.argv) < 2:
        files = sorted([
            f for f in os.listdir("queue")
            if f.endswith(".json") and not f.startswith(".")
               and os.path.isfile(f"queue/{f}")
        ])
        static = [f for f in files
                  if json.load(open(f"queue/{f}")).get("content_type") == "static"]
        if not static:
            print("No static posts found.")
            sys.exit(1)
        queue_file = f"queue/{static[-1]}"
        print(f"Using most recent queue file: {queue_file}")
    else:
        queue_file = sys.argv[1]

    generate_image(queue_file)