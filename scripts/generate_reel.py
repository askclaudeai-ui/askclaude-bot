import anthropic
import json
import os
import re
import uuid
import requests
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from strategy_summary import get_strategy_summary
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from dotenv import load_dotenv

load_dotenv()

BG       = (13,  17,  23)
VSCODE   = (30,  30,  30)
ORANGE   = (249, 115, 22)
ORANGE2  = (251, 146, 60)
WHITE    = (255, 255, 255)
GRAY     = (128, 128, 128)

C_KW  = (86,  156, 214)
C_FN  = (220, 220, 170)
C_STR = (206, 145, 120)
C_CMT = (106, 153,  85)
C_VAR = (156, 220, 254)
C_NUM = (181, 206, 168)
C_OP  = (212, 212, 212)
C_HL  = (38,  79,  120)

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

def tokenize_python(line):
    keywords = {'import','from','def','class','with','for','in',
                'if','else','elif','return','as','try','except',
                'True','False','None','and','or','not','pass',
                'while','break','continue','raise','yield'}
    tokens = []
    if line.lstrip().startswith('#'):
        tokens.append((line, C_CMT))
        return tokens
    i = 0
    while i < len(line):
        if line[i] == '#':
            tokens.append((line[i:], C_CMT))
            break
        if line[i] in ('"', "'"):
            q = line[i]
            if line[i:i+3] in ('"""', "'''"):
                q = line[i:i+3]
            j = i + len(q)
            while j < len(line):
                if line[j:j+len(q)] == q and line[j-1:j] != '\\':
                    j += len(q)
                    break
                j += 1
            tokens.append((line[i:j], C_STR))
            i = j
            continue
        if line[i].isdigit():
            j = i
            while j < len(line) and (line[j].isdigit() or line[j] == '.'):
                j += 1
            tokens.append((line[i:j], C_NUM))
            i = j
            continue
        if line[i].isalpha() or line[i] == '_':
            j = i
            while j < len(line) and (line[j].isalnum() or line[j] == '_'):
                j += 1
            word = line[i:j]
            after = line[j:].lstrip()
            if word in keywords:
                tokens.append((word, C_KW))
            elif after.startswith('('):
                tokens.append((word, C_FN))
            else:
                tokens.append((word, C_VAR))
            i = j
            continue
        if line[i] in '()[]{}':
            tokens.append((line[i], (255, 215, 0)))
            i += 1
            continue
        tokens.append((line[i], C_OP))
        i += 1
    return tokens

def render_code_line(d, x, y, line, font, highlight=False, line_h=44):
    if highlight:
        d.rectangle([0, y, 1080, y + line_h], fill=C_HL)
    tokens = tokenize_python(line)
    cx = x
    for text, colour in tokens:
        if not text:
            continue
        d.text((cx, y + 5), text, font=font, fill=colour)
        bbox = d.textbbox((cx, y + 5), text, font=font)
        cx += bbox[2] - bbox[0]

def render_cover_frame(hook, topic, W=1080, H=1920):
    """Branded cover frame in cream+indigo palette — first frame = Instagram thumbnail."""
    BG_C   = (255, 243, 208)
    BG2    = (255, 232, 150)
    INDIGO = (55,  48,  163)
    GOLD   = (217, 119,   6)
    TEXT   = (30,  27,   75)
    MID    = (61,  56,  120)
    GRID   = (210, 180,  80)

    img = Image.new("RGB", (W, H), BG_C)
    d   = ImageDraw.Draw(img)

    for x in range(0, W, W//4): d.line([(x,0),(x,H)], fill=GRID, width=1)
    for y in range(0, H, H//6): d.line([(0,y),(W,y)], fill=GRID, width=1)

    d.rectangle([0, 0,    W, 12], fill=INDIGO)
    d.rectangle([0, H-12, W, H],  fill=GOLD)
    d.rectangle([0, 0,   12, H],  fill=INDIGO)

    def draw_logo(cx, y, size=220):
        bw  = size
        bh  = int(size * 0.65)
        bx  = cx - bw//2
        rad = int(bw * 0.15)
        sw  = max(4, size//20)
        pad = int(bw * 0.13)
        t   = int(bw * 0.11)
        tip = y + bh + int(bh * 0.30)
        d.polygon([(cx-t,y+bh),(cx+t,y+bh),(cx,tip)], fill=INDIGO)
        d.rounded_rectangle([bx,y,bx+bw,y+bh], radius=rad, fill=BG2)
        d.rounded_rectangle([bx,y,bx+bw,y+bh], radius=rad, outline=INDIGO, width=sw)
        bar_h = int(bh*0.18)
        d.rounded_rectangle([bx+pad,y+pad,bx+bw-pad,y+pad+bar_h],
                             radius=bar_h//2, fill=INDIGO)
        yb = y+pad+bar_h+int(bh*0.08)
        for op, wr in [(1.0,0.9),(0.65,0.7),(0.40,0.5)]:
            bh2 = int(bh*0.10)
            bw2 = int((bw-pad*2)*wr)
            c   = tuple(int(GOLD[i]*op+BG2[i]*(1-op)) for i in range(3))
            d.rounded_rectangle([bx+pad,yb,bx+pad+bw2,yb+bh2],
                                 radius=bh2//2, fill=c)
            yb += bh2+int(bh*0.07)

    draw_logo(W//2, 280)

    d.text((W//2, 660), "ASK CLAUDE", font=get_font(36, True), fill=INDIGO, anchor="mm")

    pill_w = 200
    d.rounded_rectangle([(W-pill_w)//2, 710, (W+pill_w)//2, 766],
                         radius=28, fill=INDIGO)
    d.text((W//2, 738), "NEW REEL", font=get_font(28, True), fill=BG_C, anchor="mm")

    f_hook = get_font(80, True)
    words  = hook.split()
    lines, current = [], []
    for word in words:
        test = " ".join(current + [word])
        bbox = d.textbbox((0,0), test, font=f_hook)
        if bbox[2]-bbox[0] <= W-120:
            current.append(word)
        else:
            if current: lines.append(" ".join(current))
            current = [word]
    if current: lines.append(" ".join(current))

    y_hook = 840
    for i, line in enumerate(lines[:4]):
        bbox = d.textbbox((0,0), line, font=f_hook)
        tw   = bbox[2]-bbox[0]
        col  = INDIGO if i >= len(lines)//2 else TEXT
        d.text(((W-tw)//2, y_hook), line, font=f_hook, fill=col)
        y_hook += 96

    f_sub  = get_font(44)
    words2 = topic.split()
    lines2, cur2 = [], []
    for word in words2:
        test = " ".join(cur2+[word])
        bbox = d.textbbox((0,0), test, font=f_sub)
        if bbox[2]-bbox[0] <= W-160:
            cur2.append(word)
        else:
            if cur2: lines2.append(" ".join(cur2))
            cur2 = [word]
    if cur2: lines2.append(" ".join(cur2))
    y_sub = y_hook + 40
    for line in lines2[:2]:
        bbox = d.textbbox((0,0), line, font=f_sub)
        tw   = bbox[2]-bbox[0]
        d.text(((W-tw)//2, y_sub), line, font=f_sub, fill=MID)
        y_sub += 56

    d.text((W//2, 1600), "Watch to learn →", font=get_font(40, True), fill=GOLD, anchor="mm")
    d.text((W//2, 1720), "@ask.claudeai",    font=get_mono(32),        fill=MID,  anchor="mm")
    d.text((W//2, 1780), "New reel every Thu",font=get_mono(28),       fill=GRID, anchor="mm")

    return img

def render_reel_frame(scene, post_id, scene_num, total_scenes,
                      full_code, visible_lines):
    W, H = 1080, 1920
    img = Image.new("RGB", (W, H), VSCODE)
    d   = ImageDraw.Draw(img)

    CODE_Y   = 320
    GUTTER_W = 72
    LINE_H   = 48
    MAX_LINES = 18
    f_code   = get_mono(30)
    f_ln     = get_mono(22)

    code_to_show = full_code[:visible_lines]
    highlight_ln = scene.get("highlight_line", visible_lines)

    # Callout box — calculate position first so MAX_LINES can be clamped
    text_overlay = scene.get("text_overlay", "")
    tip_label    = scene.get("tip_label", f"Step {scene_num} of {total_scenes}")
    OV_PAD       = 24
    f_lbl        = get_font(24, True)
    f_ov         = get_font(46, True)
    ov_lines     = wrap_text(text_overlay, f_ov, W - OV_PAD*2, d)
    line_h_ov    = 58
    OV_H         = OV_PAD + 30 + 8 + len(ov_lines)*line_h_ov + OV_PAD
    HANDLE_H     = 52
    INSTAGRAM_BOTTOM_UI = 320
    OV_Y         = H - HANDLE_H - OV_H - INSTAGRAM_BOTTOM_UI

    # Clamp MAX_LINES so code doesn't overlap callout
    available_h = OV_Y - CODE_Y - 20
    MAX_LINES   = max(4, min(MAX_LINES, available_h // LINE_H))

    # Gutter
    d.rectangle([0, CODE_Y, GUTTER_W, H], fill=(28, 28, 28))
    d.line([(GUTTER_W, CODE_Y), (GUTTER_W, H)], fill=(55, 55, 55), width=1)

    for i, line in enumerate(code_to_show[:MAX_LINES]):
        ly     = CODE_Y + 8 + i * LINE_H
        ln_num = i + 1
        is_hl  = (ln_num == highlight_ln)
        ln_col = (220, 220, 220) if is_hl else (90, 90, 90)
        d.text((GUTTER_W - 8, ly + 5), str(ln_num),
               font=f_ln, fill=ln_col, anchor="rt")
        render_code_line(d, GUTTER_W + 10, ly, line,
                         font=f_code, highlight=is_hl, line_h=LINE_H)

    # Cursor
    if visible_lines <= MAX_LINES and code_to_show:
        cur_y = CODE_Y + 8 + (min(visible_lines, MAX_LINES) - 1) * LINE_H
        last  = code_to_show[-1]
        bbox  = d.textbbox((0, 0), last, font=f_code)
        cur_x = GUTTER_W + 10 + (bbox[2]-bbox[0])
        d.rectangle([cur_x+2, cur_y+8, cur_x+14, cur_y+LINE_H-8],
                    fill=(204, 204, 204))

    # Draw callout box
    d.rectangle([0, OV_Y, W, OV_Y+OV_H], fill=(13, 17, 23))
    d.line([(0, OV_Y), (W, OV_Y)], fill=ORANGE, width=3)
    d.text((OV_PAD, OV_Y+OV_PAD), tip_label, font=f_lbl, fill=ORANGE)
    y_ov = OV_Y + OV_PAD + 30 + 8
    for line in ov_lines:
        d.text((OV_PAD, y_ov), line, font=f_ov, fill=WHITE)
        y_ov += line_h_ov

    # Handle strip
    BOT_Y = H - HANDLE_H - INSTAGRAM_BOTTOM_UI
    d.rectangle([0, BOT_Y, W, H], fill=(13, 17, 23))
    d.line([(0, BOT_Y), (W, BOT_Y)], fill=(30, 30, 30), width=1)
    d.text((W//2, BOT_Y + HANDLE_H//2),
           "Ask Claude  ·  @ask.claudeai  ·  Mon · Wed · Thu",
           font=get_mono(22), fill=(80, 80, 80), anchor="mm")

    return img

def generate_voiceover_script(client, trends, recent_topics=None):
    strategy_summary = get_strategy_summary()
    trend_ctx = ""
    if trends:
        trend_ctx = f"Trending: {', '.join(trends.get('trending_topics',[])[:3])}"

    avoid_str = ""
    if recent_topics:
        avoid_str = f"""
RECENTLY USED TOPICS (do NOT repeat these):
{chr(10).join(f'- {t}' for t in recent_topics[:6])}


    prompt = f"""You are writing a calm, educational voiceover for a 28-32 second Instagram Reel for @ask.claudeai.
The reel teaches ONE Claude API technique as a live coding tutorial.

STRATEGY:
{strategy_summary}

{trend_ctx}

CONCEPT:
The screen shows ONE Python file being written from scratch.
Each scene reveals more lines — like watching someone type live.
Each scene has its OWN voiceover narration describing exactly what is visible.

VOICEOVER RULES PER SCENE:
- Each scene narration: 12-18 words minimum
- Calm, measured pace
- Describe what the highlighted line DOES
- No symbols, no markdown
- Numbers spelled out
- Code terms spoken naturally
- Last scene must end with a calm closing sentence

CODE RULES:
- Max 30 characters per line
- Max 18 lines total
- 4-space indentation
- Keep strings under 20 chars

{avoid_str}

Choose ONE topic from this list — pick whichever is most interesting and NOT in the recently used list above:
- Streaming Claude responses in real time
- Using system prompts for consistent behaviour
- Multi-turn conversation with message history
- Counting tokens before sending a request
- Handling errors and retries gracefully
- Extracting structured JSON from Claude responses
- Using tool use / function calling with Claude
- Prompt caching to reduce API costs
- Building a simple chatbot with Claude
- Vision: sending images to Claude
- Batch processing multiple requests efficiently
- Setting max tokens and understanding stop reasons
- Using temperature and top_p for creativity control
- Building an AI agent with Claude
- Generating embeddings and semantic search

Return ONLY valid JSON:
{{
  "topic": "specific tutorial topic",
  "topic_cluster": "claude_api",
  "hook": "hook for caption (max 90 chars)",
  "full_code": [
    "import anthropic",
    "",
    "client = anthropic.Anthropic()",
    "# rest of script max 18 lines"
  ],
  "filename": "short_name.py",
  "scenes": [
    {{
      "scene_number": 1,
      "visible_lines": 3,
      "highlight_line": 3,
      "tip_label": "Step 1 of 5",
      "text_overlay": "Set up your client",
      "filename": "streaming_demo.py",
      "narration": "First we import anthropic and create our client. This one line gives us access to the entire Claude API."
    }},
    {{
      "scene_number": 2,
      "visible_lines": 7,
      "highlight_line": 6,
      "tip_label": "Step 2 of 5",
      "text_overlay": "Open the stream",
      "filename": "streaming_demo.py",
      "narration": "Now we call messages dot stream instead of messages dot create. This opens a live connection to Claude."
    }},
    {{
      "scene_number": 3,
      "visible_lines": 11,
      "highlight_line": 10,
      "tip_label": "Step 3 of 5",
      "text_overlay": "Pass your message",
      "filename": "streaming_demo.py",
      "narration": "We pass the model name, max tokens, and our messages array. Same parameters as a normal request."
    }},
    {{
      "scene_number": 4,
      "visible_lines": 14,
      "highlight_line": 13,
      "tip_label": "Step 4 of 5",
      "text_overlay": "Iterate chunks live",
      "filename": "streaming_demo.py",
      "narration": "Inside the with block we iterate over stream dot text stream. Each iteration gives us the next chunk of text as it arrives."
    }},
    {{
      "scene_number": 5,
      "visible_lines": 18,
      "highlight_line": 16,
      "tip_label": "Step 5 of 5",
      "text_overlay": "Print as it arrives",
      "filename": "streaming_demo.py",
      "narration": "We print each chunk immediately with flush equals true. Your users see text appear in real time. That is all you need."
    }}
  ],
  "audio_suggestion": "lo-fi or original audio",
  "hashtags": ["#claudeai","#anthropic","#aidev","#llm","#pythondev","#apidevelopment","#aiintegration","#machinelearning","#codinglife","#devtips","#programming","#artificialintelligence","#developer","#techstack","#buildwithclaude","#promptengineering","#automation","#aitools"],
  "recommended_day": "thursday",
  "recommended_time_utc": "13:00"
}}

Include exactly 5 scenes.
Each narration must be 12-18 words minimum.
full_code must be 14-18 lines, each max 30 characters.
visible_lines must increase strictly across scenes.
Last scene visible_lines must equal len(full_code)."""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}]
    )
    return parse_claude_json(message.content[0].text)

def generate_tts_segment(narration, output_path, voice_id, api_key):
    response = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
        headers={"xi-api-key": api_key, "Content-Type": "application/json"},
        json={
            "text": narration.rstrip('.') + '.',
            "model_id": "eleven_turbo_v2_5",
            "voice_settings": {
                "stability":         0.85,
                "similarity_boost":  0.75,
                "style":             0.0,
                "use_speaker_boost": True
            }
        }
    )
    if response.status_code != 200:
        raise Exception(f"ElevenLabs {response.status_code}: {response.text[:200]}")
    with open(output_path, "wb") as f:
        f.write(response.content)
    return output_path

def get_audio_duration(path, trim_end=0.15):
    from moviepy.editor import AudioFileClip
    clip = AudioFileClip(path)
    dur  = clip.duration
    trimmed_dur = max(dur - trim_end, dur * 0.85)
    clip = clip.subclip(0, trimmed_dur)
    clip.write_audiofile(path, logger=None)
    actual = clip.duration
    clip.close()
    return actual

def concatenate_audio(segment_paths, output_path):
    from moviepy.editor import AudioFileClip, concatenate_audioclips, AudioClip
    import numpy as np

    SILENCE_S = 0.3

    def make_silence(duration, fps=44100):
        return AudioClip(
            lambda t: np.zeros((len(np.atleast_1d(t)), 2)),
            duration=duration
        ).set_fps(fps)

    clips = []
    for i, p in enumerate(segment_paths):
        clips.append(AudioFileClip(p))
        if i < len(segment_paths) - 1:
            clips.append(make_silence(SILENCE_S))

    final = concatenate_audioclips(clips)
    final.write_audiofile(output_path, logger=None)
    for c in clips:
        c.close()
    final.close()
    return output_path

def assemble_reel(frame_paths, segment_durations, combined_audio_path, output_path):
    print("Assembling reel...")
    try:
        from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips

        clips = []
        for frame_path, dur in zip(frame_paths, segment_durations):
            clips.append(ImageClip(frame_path).set_duration(dur))

        video      = concatenate_videoclips(clips, method="compose")
        audio_clip = AudioFileClip(combined_audio_path)
        if audio_clip.duration > 0.5:
            audio_clip = audio_clip.subclip(0, audio_clip.duration - 0.3)
        video = video.set_audio(audio_clip)

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        video.write_videofile(
            output_path, fps=30,
            codec="libx264", audio_codec="aac",
            preset="fast", logger=None
        )
        video.close()
        audio_clip.close()
        print(f"Reel saved: {output_path}")
        return output_path

    except Exception as e:
        print(f"Assembly error: {e}")
        return None

def generate_reel():
    client   = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    strategy = json.load(open("data/strategy.json"))

    trend_files = sorted([f for f in os.listdir("data") if f.startswith("trends_")])
    trends = json.load(open(f"data/{trend_files[-1]}")) if trend_files else {}

    voice_id  = os.getenv("ELEVENLABS_VOICE_ID", "")
    api_key   = os.getenv("ELEVENLABS_API_KEY", "")
    evergreen = strategy["hashtags"]["evergreen_tags"]
    rec_day   = strategy["timing"]["preferred_days"][0]["day"]
    rec_hour  = f"{strategy['timing']['preferred_hours_utc'][0]:02d}:00"

    print("Generating reel script...")
    # Get recent reel topics to avoid repetition
    recent_reel_topics = []
    try:
        for f in sorted(os.listdir("queue"), reverse=True)[:20]:
            if not f.endswith(".json"): continue
            d = json.load(open(f"queue/{f}"))
            if d.get("content_type") == "reel":
                t = d.get("post", {}).get("topic", "")
                if t: recent_reel_topics.append(t.lower())
    except:
        pass

    data = generate_voiceover_script(client, trends, recent_reel_topics)
    scenes    = data.get("scenes", [])
    full_code = data.get("full_code", ["import anthropic"])

    print(f"\nTopic:  {data.get('topic','')}")
    print(f"Hook:   {data.get('hook','')}")
    print(f"Code lines: {len(full_code)}")
    print(f"Scenes: {len(scenes)}")

    post_id   = str(uuid.uuid4())[:8]
    audio_dir = f"queue/reels/{post_id}"
    os.makedirs(audio_dir, exist_ok=True)

    # Generate per-scene TTS
    print("\nGenerating per-scene voiceovers...")
    segment_paths     = []
    segment_durations = []
    audio_ok          = True

    for i, scene in enumerate(scenes):
        narration = scene.get("narration", "")
        seg_path  = f"{audio_dir}/segment_{i+1:02d}.mp3"
        try:
            generate_tts_segment(narration, seg_path, voice_id, api_key)
            dur = get_audio_duration(seg_path)
            segment_paths.append(seg_path)
            segment_durations.append(dur)
            print(f"  Scene {i+1}: {dur:.1f}s")
        except Exception as e:
            print(f"  Scene {i+1} TTS failed: {e}")
            audio_ok = False
            break

    total_dur = sum(segment_durations)
    print(f"Total audio: {total_dur:.1f}s")

    combined_audio = None
    if audio_ok:
        combined_audio = f"{audio_dir}/voiceover.mp3"
        try:
            concatenate_audio(segment_paths, combined_audio)
        except Exception as e:
            print(f"Audio concatenation failed: {e}")
            audio_ok = False

    # Render frames
    frames_dir = f"queue/images/{post_id}"
    os.makedirs(frames_dir, exist_ok=True)
    frame_paths = []

    # Render branded cover as first frame — Instagram uses first frame as thumbnail
    hook_text  = data.get("hook", data.get("topic", "Claude API"))
    topic_text = data.get("topic", "Claude API")
    cover_img  = render_cover_frame(hook_text, topic_text)
    cover_path = f"{frames_dir}/frame_00_cover.png"
    cover_img.save(cover_path, "PNG", optimize=True)
    frame_paths.insert(0, cover_path)
    segment_durations.insert(0, 0.1)
    print(f"\n  Cover frame added (0.1s thumbnail)")

    print(f"Rendering {len(scenes)} code frames...")
    for i, scene in enumerate(scenes):
        visible = scene.get("visible_lines", len(full_code))
        img     = render_reel_frame(
            scene, post_id, i+1, len(scenes),
            full_code=full_code,
            visible_lines=visible
        )
        path = f"{frames_dir}/frame_{i+1:02d}.png"
        img.save(path, "PNG", optimize=True)
        frame_paths.append(path)
        print(f"  Frame {i+1}/{len(scenes)} — {visible} lines visible")

    # Assemble video
    video_path = None
    if audio_ok and combined_audio:
        video_path = f"{audio_dir}/reel.mp4"
        video_path = assemble_reel(
            frame_paths, segment_durations,
            combined_audio, video_path
        )

    full_script = " ".join(s.get("narration","") for s in scenes)

    # Build queue entry
    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"queue/{date_str}_{post_id}.json"

    queue_entry = {
        "id":               post_id,
        "content_type":     "reel",
        "status":           "pending",
        "created_at":       datetime.now().isoformat(),
        "published_at":     None,
        "instagram_media_id": None,
        "imgbb_url":        None,
        "cloudinary_video_url": video_path,
        "generation_inputs": {
            "strategy_snapshot": {
                "model_phase":    strategy["meta"]["model_phase"],
                "timing":         strategy["timing"],
                "content_format": strategy["content_format"]
            },
            "trend_report":    trends,
            "topic_cluster":   data.get("topic_cluster", "claude_api"),
            "hook_style_used": "bold_statement"
        },
        "post": {
            "topic":            data.get("topic", ""),
            "hook":             data.get("hook", ""),
            "caption":          data.get("hook","") + "\n\nFollow @ask.claudeai for Claude API tips every week.",
            "hashtags":         data.get("hashtags", evergreen),
            "audio_suggestion": data.get("audio_suggestion", "original audio"),
            "reel_script": {
                "full_script":       full_script,
                "word_count":        len(full_script.split()),
                "total_duration_s":  total_dur,
                "full_code":         full_code,
                "scenes":            scenes,
                "segment_paths":     segment_paths,
                "segment_durations": segment_durations,
                "combined_audio":    combined_audio,
                "video_path":        video_path,
                "frame_paths":       frame_paths
            }
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

    # Upload video to Cloudinary
    if video_path and os.path.exists(video_path):
        try:
            from upload_media import upload_video_cloudinary, upload_image_cloudinary_feed
            print("\nUploading reel to Cloudinary...")
            queue_entry["cloudinary_video_url"] = upload_video_cloudinary(video_path)
            print(f"Video uploaded: {queue_entry['cloudinary_video_url']}")
            # Upload cover frame to Cloudinary for dashboard preview
            if os.path.exists(cover_path):
                cover_url = upload_image_cloudinary_feed(cover_path)
                queue_entry["imgbb_url"] = cover_url
                queue_entry["cloudinary_image_url"] = cover_url
                print(f"Cover uploaded: {cover_url}")
        except Exception as e:
            print(f"Upload failed: {e}")

    # Send email notification
    try:
        from notify import notify_post_ready
        notify_post_ready(queue_entry)
    except Exception as e:
        print(f"Notification skipped: {e}")

    # Save queue entry
    os.makedirs("queue", exist_ok=True)
    with open(filename, "w") as f:
        json.dump(queue_entry, f, indent=2)

    print(f"\nQueue entry: {filename}")
    if video_path:
        print(f"Preview: open {video_path}")

    # Auto-commit and push
    try:
        import subprocess
        repo_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        subprocess.run(["git", "add", "queue/", "data/"], cwd=repo_dir, check=False)
        subprocess.run(["git", "commit", "-m", f"Generated reel {post_id}"], cwd=repo_dir, check=False)
        subprocess.run(["git", "pull", "--rebase"], cwd=repo_dir, check=False)
        subprocess.run(["git", "push"], cwd=repo_dir, check=False)
        print("Queue file pushed to GitHub")
    except Exception as e:
        print(f"Git push skipped: {e}")

    return filename, queue_entry

if __name__ == "__main__":
    generate_reel()