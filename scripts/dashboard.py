import json
import os
import sys
import requests
from datetime import datetime
from flask import Flask, render_template_string, redirect, url_for, request, send_file, jsonify
from dotenv import load_dotenv

load_dotenv()

app         = Flask(__name__)
BASE_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUEUE_DIR   = os.path.join(BASE_DIR, "queue")
SCRIPTS_DIR = os.path.join(BASE_DIR, "scripts")
sys.path.insert(0, SCRIPTS_DIR)

HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Ask Claude — Dashboard</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }

        body {
            font-family: -apple-system, sans-serif;
            background: #0D1117;
            color: #E6EDF3;
            min-height: 100vh;
        }

        .header {
            background: #3730A3;
            border-bottom: 4px solid #D97706;
            padding: 16px 32px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .logo { font-size: 22px; font-weight: 700; color: #FFF3D0; }
        .logo span { color: #D97706; }
        .header-date { font-size: 13px; color: #C4B5FD; }

        .container { max-width: 980px; margin: 0 auto; padding: 32px 24px; }

        .stats {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 16px;
            margin-bottom: 32px;
        }
        .stat {
            background: #161B22;
            border: 1px solid #30363D;
            border-radius: 14px;
            padding: 20px;
            text-align: center;
        }
        .stat-num   { font-size: 36px; font-weight: 700; color: #D97706; }
        .stat-label { font-size: 13px; color: #8B949E; margin-top: 4px; }

        .tabs {
            display: flex;
            gap: 6px;
            margin-bottom: 24px;
            flex-wrap: wrap;
        }
        .tab {
            padding: 8px 20px;
            border-radius: 20px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            text-decoration: none;
            color: #8B949E;
            background: #161B22;
            border: 1px solid #30363D;
        }
        .tab:hover  { border-color: #D97706; color: #D97706; }
        .tab.active { background: #3730A3; color: #FFF3D0; border-color: #3730A3; }

        .section-title {
            font-size: 18px;
            font-weight: 700;
            margin-bottom: 16px;
            color: #E6EDF3;
        }

        .post-card {
            background: #161B22;
            border: 1px solid #30363D;
            border-radius: 16px;
            margin-bottom: 20px;
            overflow: hidden;
        }
        .post-header {
            padding: 14px 20px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            border-bottom: 1px solid #30363D;
            background: #0D1117;
        }
        .post-meta { display: flex; align-items: center; gap: 10px; }

        .badge {
            padding: 4px 14px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 700;
            letter-spacing: .04em;
        }
        .badge-pending      { background: #3730A3; color: #FFF3D0; }
        .badge-approved     { background: #15803D; color: #FFFFFF; }
        .badge-published    { background: #0369A1; color: #FFFFFF; }
        .badge-rejected     { background: #DC2626; color: #FFFFFF; }
        .badge-regenerating { background: #D97706; color: #1E1B4B; }
        .badge-type         { background: #21262D; color: #8B949E; }

        .post-date { font-size: 12px; color: #8B949E; }

        .post-body {
            padding: 20px;
            display: grid;
            grid-template-columns: 300px 1fr;
            gap: 20px;
        }

        .post-image {
            border-radius: 10px;
            overflow: hidden;
            background: #0D1117;
            border: 1px solid #30363D;
        }
        .post-image img   { width: 100%; display: block; border-radius: 10px; }
        .post-image video { width: 100%; display: block; border-radius: 10px; }
        .no-img {
            width: 100%;
            aspect-ratio: 1;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #8B949E;
            font-size: 13px;
        }

        .slide-nav { display: flex; gap: 8px; justify-content: center; margin-top: 8px; align-items: center; }
        .slide-nav button {
            background: #3730A3;
            color: #FFF3D0;
            border: none;
            border-radius: 8px;
            padding: 4px 14px;
            cursor: pointer;
            font-size: 13px;
            font-weight: 600;
        }
        .slide-nav button:hover { background: #4F46E5; }
        .slide-counter { font-size: 12px; color: #8B949E; font-weight: 600; }
        .preview-label { font-size: 11px; color: #8B949E; text-align: center; margin-top: 4px; }

        .regen-img-btn {
            width: 100%;
            margin-top: 8px;
            padding: 7px;
            background: #21262D;
            color: #E6EDF3;
            border: 1px solid #D97706;
            border-radius: 8px;
            font-size: 12px;
            font-weight: 600;
            cursor: pointer;
        }
        .regen-img-btn:hover { background: #D97706; color: #1E1B4B; }

        .post-content { display: flex; flex-direction: column; gap: 12px; }

        .hook    { font-size: 17px; font-weight: 700; color: #D97706; line-height: 1.4; }
        .topic   { font-size: 13px; color: #8B949E; }
        .timing  { font-size: 12px; color: #8B949E; }
        .timing span { color: #D97706; font-weight: 600; }
        .hashtags { font-size: 12px; color: #6B7280; line-height: 1.8; }

        .caption-preview {
            font-size: 13px;
            color: #C9D1D9;
            line-height: 1.7;
            background: #0D1117;
            padding: 12px 14px;
            border-radius: 10px;
            white-space: pre-wrap;
            border: 1px solid #30363D;
        }

        .manual-action-required {
            background: #1C1917;
            border: 1px solid #D97706;
            border-radius: 10px;
            padding: 12px 16px;
            margin-bottom: 8px;
        }
        .manual-action-title { font-size: 12px; font-weight: 700; color: #D97706; margin-bottom: 6px; }
        .manual-action-name  { font-size: 14px; font-weight: 700; color: #E6EDF3; margin-bottom: 6px; }
        .manual-action-step  { font-size: 12px; color: #C9D1D9; margin-bottom: 2px; }

        .manual-action-optional {
            background: #161B22;
            border: 1px solid #30363D;
            border-radius: 10px;
            padding: 8px 14px;
            margin-bottom: 8px;
            font-size: 12px;
            color: #8B949E;
        }
        .audio-suggestion {
            background: #161B22;
            border: 1px solid #30363D;
            border-radius: 10px;
            padding: 8px 14px;
            margin-bottom: 8px;
            font-size: 12px;
            color: #8B949E;
        }

        .actions { display: flex; gap: 8px; margin-top: 8px; flex-wrap: wrap; }
        .btn {
            padding: 9px 22px;
            border-radius: 20px;
            border: none;
            font-size: 14px;
            font-weight: 700;
            cursor: pointer;
            text-decoration: none;
            display: inline-block;
        }
        .btn:hover { opacity: 0.85; }
        .btn-approve  { background: #15803D; color: #FFFFFF; }
        .btn-reject   { background: #DC2626; color: #FFFFFF; }
        .btn-edit     { background: #3730A3; color: #FFF3D0; }
        .btn-feedback { background: #D97706; color: #1E1B4B; }

        .empty {
            text-align: center;
            padding: 60px;
            color: #8B949E;
            background: #161B22;
            border-radius: 16px;
            border: 1px solid #30363D;
        }
        .empty h3 { font-size: 20px; margin-bottom: 8px; color: #E6EDF3; }

        .spinner-overlay {
            display: none;
            position: fixed;
            inset: 0;
            background: rgba(13,17,23,0.85);
            z-index: 200;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            gap: 20px;
        }
        .spinner-overlay.open { display: flex; }
        .spinner {
            width: 52px; height: 52px;
            border: 6px solid #30363D;
            border-top-color: #D97706;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        .spinner-text { color: #E6EDF3; font-size: 16px; font-weight: 600; }

        .modal-overlay {
            display: none;
            position: fixed;
            inset: 0;
            background: rgba(13,17,23,0.8);
            z-index: 100;
            align-items: center;
            justify-content: center;
        }
        .modal-overlay.open { display: flex; }
        .modal {
            background: #161B22;
            border: 1px solid #30363D;
            border-radius: 18px;
            padding: 28px;
            width: 90%;
            max-width: 680px;
            max-height: 88vh;
            overflow-y: auto;
        }
        .modal h2 { font-size: 20px; font-weight: 700; margin-bottom: 20px; }
        .modal h2.gold   { color: #D97706; }
        .modal h2.indigo { color: #A78BFA; }

        .form-group { margin-bottom: 16px; }
        .form-group label {
            display: block;
            font-size: 13px;
            color: #8B949E;
            margin-bottom: 6px;
            font-weight: 600;
        }
        .form-group input,
        .form-group textarea {
            width: 100%;
            background: #0D1117;
            border: 1px solid #30363D;
            border-radius: 10px;
            padding: 10px 14px;
            color: #E6EDF3;
            font-size: 14px;
            font-family: inherit;
            resize: vertical;
        }
        .form-group textarea { min-height: 120px; line-height: 1.6; }
        .form-group input:focus,
        .form-group textarea:focus { outline: none; border-color: #D97706; }

        .modal-actions { display: flex; gap: 10px; justify-content: flex-end; margin-top: 20px; }
        .btn-save    { background: #3730A3; color: #FFF3D0; }
        .btn-rewrite { background: #D97706; color: #1E1B4B; }
        .btn-cancel  { background: #21262D; color: #E6EDF3; }

        .char-count    { font-size: 11px; color: #8B949E; margin-top: 4px; text-align: right; }
        .feedback-hint { font-size: 12px; color: #8B949E; margin-top: 4px; line-height: 1.5; }

        @media (max-width: 640px) {
            .post-body { grid-template-columns: 1fr; }
            .stats { grid-template-columns: repeat(2, 1fr); }
        }
    </style>
</head>
<body>

<div class="spinner-overlay" id="spinner">
    <div class="spinner"></div>
    <div class="spinner-text" id="spinner-text">Processing...</div>
</div>

<div class="header">
    <div class="logo">Ask<span>Claude</span> — Review Dashboard</div>
    <div class="header-date">{{ now }}</div>
</div>

<div class="container">
    <div class="stats">
        <div class="stat"><div class="stat-num">{{ counts.pending }}</div><div class="stat-label">Pending review</div></div>
        <div class="stat"><div class="stat-num">{{ counts.approved }}</div><div class="stat-label">Approved</div></div>
        <div class="stat"><div class="stat-num">{{ counts.published }}</div><div class="stat-label">Published</div></div>
        <div class="stat"><div class="stat-num">{{ counts.total }}</div><div class="stat-label">Total posts</div></div>
    </div>

    <div class="tabs">
        <a href="/?filter=pending"      class="tab {{ 'active' if filter == 'pending'      else '' }}">Pending ({{ counts.pending }})</a>
        <a href="/?filter=approved"     class="tab {{ 'active' if filter == 'approved'     else '' }}">Approved ({{ counts.approved }})</a>
        <a href="/?filter=published"    class="tab {{ 'active' if filter == 'published'    else '' }}">Published ({{ counts.published }})</a>
        <a href="/?filter=regenerating" class="tab {{ 'active' if filter == 'regenerating' else '' }}">Regenerating</a>
        <a href="/?filter=all"          class="tab {{ 'active' if filter == 'all'          else '' }}">All</a>
    </div>

    <div class="section-title">
        {% if filter == 'pending' %}Posts awaiting your review
        {% elif filter == 'approved' %}Approved — queued for publish
        {% elif filter == 'published' %}Published posts
        {% elif filter == 'regenerating' %}Being regenerated — check back soon
        {% else %}All posts{% endif %}
    </div>

    {% if posts %}
        {% for post in posts %}
        <div class="post-card">
            <div class="post-header">
                <div class="post-meta">
                    <span class="badge badge-{{ post.status }}">{{ post.status.upper() }}</span>
                    <span class="badge badge-type">{{ post.content_type }}</span>
                    {% if post.story_type %}
                    <span class="badge badge-type">{{ post.story_type }}</span>
                    {% endif %}
                    <span class="post-date">{{ post.created_at[:10] }}</span>
                </div>
                <div class="post-date">ID: {{ post.id }}</div>
            </div>

            <div class="post-body">
                <div class="post-image">
                    {% if post.content_type == 'reel' and post.cloudinary_video_url %}
                        <video controls style="width:100%;border-radius:10px"
                               poster="{{ post.imgbb_url or '' }}">
                            <source src="{{ post.cloudinary_video_url }}" type="video/mp4">
                        </video>
                        <div class="preview-label">Full reel preview</div>

                    {% elif post.content_type == 'carousel' and post.imgbb_slide_urls %}
                        {% for url in post.imgbb_slide_urls %}
                            {% if url %}
                            <img src="{{ url }}"
                                 class="carousel-slide-{{ post.id }}"
                                 data-index="{{ loop.index0 }}"
                                 style="width:100%;border-radius:10px;display:{% if loop.first %}block{% else %}none{% endif %}">
                            {% endif %}
                        {% endfor %}
                        <div class="slide-nav">
                            <button onclick="prevSlide('{{ post.id }}')">←</button>
                            <span class="slide-counter" id="slide-counter-{{ post.id }}">
                                1 / {{ post.imgbb_slide_urls | length }}
                            </span>
                            <button onclick="nextSlide('{{ post.id }}')">→</button>
                        </div>
                        <div class="preview-label">Swipe through all slides</div>

                    {% elif post.content_type == 'story' and post.cloudinary_story_urls %}
                        {% for url in post.cloudinary_story_urls %}
                            {% if url %}
                            <img src="{{ url }}"
                                 class="story-slide-{{ post.id }}"
                                 data-index="{{ loop.index0 }}"
                                 style="width:100%;border-radius:10px;aspect-ratio:9/16;object-fit:cover;display:{% if loop.first %}block{% else %}none{% endif %}">
                            {% endif %}
                        {% endfor %}
                        {% if post.cloudinary_story_urls | length > 1 %}
                        <div class="slide-nav">
                            <button onclick="prevSlide('{{ post.id }}')">←</button>
                            <span class="slide-counter" id="slide-counter-{{ post.id }}">
                                1 / {{ post.cloudinary_story_urls | length }}
                            </span>
                            <button onclick="nextSlide('{{ post.id }}')">→</button>
                        </div>
                        {% endif %}
                        <div class="preview-label">Story preview</div>

                    {% elif post.image_path %}
                        {% if post.image_path.startswith('http') %}
                            <img src="{{ post.image_path }}" alt="Post image" id="img-{{ post.id }}">
                        {% else %}
                            <img src="/image/{{ post.id }}?t={{ post.created_at }}" alt="Post image" id="img-{{ post.id }}">
                        {% endif %}

                    {% else %}
                        <div class="no-img">No preview yet</div>
                    {% endif %}

                    <button class="regen-img-btn" onclick="regenImageOnly('{{ post.id }}')">
                        Regenerate image only
                    </button>
                </div>

                <div class="post-content">
                    <div class="hook">{{ post.post.hook }}</div>
                    <div class="topic">Topic: {{ post.post.topic }}</div>
                    <div class="caption-preview">{{ post.post.caption[:400] }}{% if post.post.caption|length > 400 %}...{% endif %}</div>
                    <div class="hashtags">{{ post.post.hashtags | join(' ') }}</div>
                    <div class="timing">Recommended: <span>{{ post.scheduling.recommended_day }} at {{ post.scheduling.recommended_time_utc }} UTC</span></div>

                    {% if post.manual_action and post.manual_action.required %}
                    <div class="manual-action-required">
                        <div class="manual-action-title">⚠️ Manual action required after posting</div>
                        <div class="manual-action-name">{{ post.manual_action.action }}</div>
                        {% for step in post.manual_action.steps %}
                        <div class="manual-action-step">{{ loop.index }}. {{ step }}</div>
                        {% endfor %}
                    </div>
                    {% elif post.manual_action and not post.manual_action.required and post.manual_action.action %}
                    <div class="manual-action-optional">
                        💡 Optional: {{ post.manual_action.action }}
                    </div>
                    {% endif %}

                    {% if post.content_type == 'reel' and post.post.audio_suggestion %}
                    <div class="audio-suggestion">
                        🎵 Suggested audio: <strong style="color:#D97706">{{ post.post.audio_suggestion }}</strong>
                        — add in Instagram app after posting
                    </div>
                    {% endif %}

                    <div class="actions">
                        {% if post.status == 'pending' %}
                        <a href="/approve/{{ post.id }}" class="btn btn-approve"
                           onclick="showSpinner('Publishing to Instagram...')">Approve</a>
                        <a href="/reject/{{ post.id }}"  class="btn btn-reject"
                           onclick="showSpinner('Deleting and regenerating...')">Reject</a>
                        {% endif %}
                        <button class="btn btn-edit" onclick="openEdit(
                            '{{ post.id }}',
                            {{ (post.post.hook or '') | tojson }},
                            {{ (post.post.caption or '') | tojson }},
                            {{ (post.post.hashtags | join(' ')) | tojson }},
                            {{ (post.scheduling.recommended_day or '') | tojson }},
                            {{ (post.scheduling.recommended_time_utc or '') | tojson }}
                        )">Edit post</button>
                        <button class="btn btn-feedback" onclick="openFeedback('{{ post.id }}')">Give feedback</button>
                    </div>
                </div>
            </div>
        </div>
        {% endfor %}
    {% else %}
        <div class="empty">
            <h3>No posts here</h3>
            <p>{% if filter == 'regenerating' %}Posts being regenerated will appear here.
               {% else %}Run a generate script to create new posts.{% endif %}</p>
        </div>
    {% endif %}
</div>

<!-- Edit Modal -->
<div class="modal-overlay" id="editModal">
    <div class="modal">
        <h2 class="gold">Edit post</h2>
        <form method="POST" action="/edit" onsubmit="showSpinner('Saving...')">
            <input type="hidden" name="post_id" id="edit_post_id">
            <div class="form-group">
                <label>Hook (max 90 chars)</label>
                <input type="text" name="hook" id="edit_hook" maxlength="120"
                       oninput="updateCount('edit_hook','hook_count')">
                <div class="char-count"><span id="hook_count">0</span> / 90</div>
            </div>
            <div class="form-group">
                <label>Caption body</label>
                <textarea name="caption" id="edit_caption" rows="8"
                          oninput="updateCount('edit_caption','caption_count')"></textarea>
                <div class="char-count"><span id="caption_count">0</span> words</div>
            </div>
            <div class="form-group">
                <label>Hashtags (space-separated)</label>
                <textarea name="hashtags" id="edit_hashtags" rows="3"></textarea>
            </div>
            <div class="form-group">
                <label>Recommended day</label>
                <input type="text" name="recommended_day" id="edit_day">
            </div>
            <div class="form-group">
                <label>Recommended time UTC (e.g. 13:00)</label>
                <input type="text" name="recommended_time_utc" id="edit_time">
            </div>
            <div class="modal-actions">
                <button type="button" class="btn btn-cancel" onclick="closeEdit()">Cancel</button>
                <button type="submit" class="btn btn-save">Save &amp; regenerate image</button>
            </div>
        </form>
    </div>
</div>

<!-- Feedback Modal -->
<div class="modal-overlay" id="feedbackModal">
    <div class="modal">
        <h2 class="indigo">Give feedback to Claude</h2>
        <form method="POST" action="/feedback"
              onsubmit="showSpinner('Queuing regeneration — email when ready...')">
            <input type="hidden" name="post_id" id="feedback_post_id">
            <div class="form-group">
                <label>Your feedback</label>
                <textarea name="feedback" id="feedback_text" rows="6"
                    placeholder="e.g. Make it more beginner friendly. Add a code example. Shorten the caption."></textarea>
                <div class="feedback-hint">
                    Claude will rewrite the post in the background.
                    You will receive an email when ready to review.
                </div>
            </div>
            <div class="modal-actions">
                <button type="button" class="btn btn-cancel" onclick="closeFeedback()">Cancel</button>
                <button type="submit" class="btn btn-rewrite">Send to Claude →</button>
            </div>
        </form>
    </div>
</div>

<script>
function showSpinner(text) {
    document.getElementById('spinner-text').textContent = text || 'Processing...';
    document.getElementById('spinner').classList.add('open');
}
function hideSpinner() {
    document.getElementById('spinner').classList.remove('open');
}

var slideIndexes = {};

function getSlides(postId) {
    var slides = document.querySelectorAll('.carousel-slide-' + postId);
    if (!slides.length) slides = document.querySelectorAll('.story-slide-' + postId);
    return slides;
}

function showSlide(postId, index) {
    var slides  = getSlides(postId);
    var counter = document.getElementById('slide-counter-' + postId);
    if (!slides.length) return;
    slides.forEach(function(s) { s.style.display = 'none'; });
    slides[index].style.display = 'block';
    if (counter) counter.textContent = (index + 1) + ' / ' + slides.length;
    slideIndexes[postId] = index;
}

function nextSlide(postId) {
    var slides = getSlides(postId);
    var cur    = slideIndexes[postId] || 0;
    showSlide(postId, (cur + 1) % slides.length);
}

function prevSlide(postId) {
    var slides = getSlides(postId);
    var cur    = slideIndexes[postId] || 0;
    showSlide(postId, (cur - 1 + slides.length) % slides.length);
}

function openEdit(id, hook, caption, hashtags, day, time) {
    document.getElementById('edit_post_id').value  = id;
    document.getElementById('edit_hook').value     = hook;
    document.getElementById('edit_caption').value  = caption;
    document.getElementById('edit_hashtags').value = hashtags;
    document.getElementById('edit_day').value      = day;
    document.getElementById('edit_time').value     = time;
    updateCount('edit_hook', 'hook_count');
    updateCount('edit_caption', 'caption_count');
    document.getElementById('editModal').classList.add('open');
}
function closeEdit() { document.getElementById('editModal').classList.remove('open'); }

function openFeedback(id) {
    document.getElementById('feedback_post_id').value = id;
    document.getElementById('feedback_text').value    = '';
    document.getElementById('feedbackModal').classList.add('open');
}
function closeFeedback() { document.getElementById('feedbackModal').classList.remove('open'); }

function updateCount(fieldId, countId) {
    var val = document.getElementById(fieldId).value;
    if (fieldId === 'edit_caption') {
        document.getElementById(countId).textContent =
            val.trim() ? val.trim().split(/\s+/).length : 0;
    } else {
        document.getElementById(countId).textContent = val.length;
    }
}

function regenImageOnly(postId) {
    showSpinner('Regenerating image...');
    fetch('/regen_image/' + postId, { method: 'POST' })
        .then(r => r.json())
        .then(data => {
            hideSpinner();
            if (data.ok) {
                var img = document.getElementById('img-' + postId);
                if (img) img.src = img.src.split('?')[0] + '?t=' + Date.now();
            } else {
                alert('Regeneration failed: ' + (data.error || 'unknown'));
            }
        })
        .catch(() => { hideSpinner(); alert('Request failed.'); });
}

['editModal','feedbackModal'].forEach(function(id) {
    document.getElementById(id).addEventListener('click', function(e) {
        if (e.target === this) this.classList.remove('open');
    });
});
</script>
</body>
</html>
"""

def fetch_posts_from_github():
    """Fetch all queue JSON files directly from GitHub API."""
    github_token = os.getenv("GITHUB_TOKEN_PAT") or os.getenv("GITHUB_TOKEN")
    github_repo  = os.getenv("GITHUB_REPO")
    if not github_token or not github_repo:
        return None

    headers = {
        "Authorization": f"token {github_token}",
        "Accept":        "application/vnd.github.v3+json"
    }

    posts = []
    for folder in ["queue", "queue/stories"]:
        try:
            r = requests.get(
                f"https://api.github.com/repos/{github_repo}/contents/{folder}",
                headers=headers,
                timeout=5
            )
            if r.status_code != 200:
                continue
            for item in r.json():
                if not isinstance(item, dict): continue
                if not item.get("name","").endswith(".json"): continue
                if item.get("type") != "file": continue
                try:
                    r2   = requests.get(item["download_url"], timeout=5)
                    post = json.loads(r2.text)
                    posts.append(post)
                except:
                    continue
        except:
            continue
    return posts if posts else None

def load_posts(filter_status=None):
    raw_posts = fetch_posts_from_github()

    # Fall back to local files if GitHub fetch fails
    if raw_posts is None:
        raw_posts = []
        all_files = []
        if os.path.exists(QUEUE_DIR):
            for fname in os.listdir(QUEUE_DIR):
                if fname.endswith(".json"):
                    all_files.append(os.path.join(QUEUE_DIR, fname))
        stories_dir = os.path.join(QUEUE_DIR, "stories")
        if os.path.exists(stories_dir):
            for fname in os.listdir(stories_dir):
                if fname.endswith(".json"):
                    all_files.append(os.path.join(stories_dir, fname))
        for path in all_files:
            try:
                with open(path) as f:
                    raw_posts.append(json.load(f))
            except:
                continue

    posts = []
    for post in raw_posts:
        try:
            if post.get("status") == "ready_to_post":
                post["status"] = "pending"

            cloudinary_img = post.get("cloudinary_image_url")
            imgbb          = post.get("imgbb_url", "")
            if cloudinary_img:
                post["image_path"] = cloudinary_img
            elif imgbb and "cloudinary" in imgbb:
                post["image_path"] = imgbb
            elif imgbb:
                post["image_path"] = imgbb
            else:
                local = os.path.join(QUEUE_DIR, "images", f"{post.get('id','')}.png")
                post["image_path"] = local if os.path.exists(local) else None

            post["cloudinary_video_url"]  = post.get("cloudinary_video_url")
            post["cloudinary_story_urls"] = post.get("cloudinary_story_urls", [])
            post["imgbb_slide_urls"]       = post.get("imgbb_slide_urls", [])
            post["manual_action"]          = post.get("manual_action", {})
            post["story_type"]             = post.get("story_type", "")

            if "post" not in post:
                post["post"] = {}
            post["post"].setdefault("hook", "")
            post["post"].setdefault("caption", "")
            post["post"].setdefault("hashtags", [])
            if "scheduling" not in post:
                post["scheduling"] = {}
            post["scheduling"].setdefault("recommended_day", "")
            post["scheduling"].setdefault("recommended_time_utc", "")

            if filter_status and filter_status != "all":
                if post.get("status") == filter_status:
                    posts.append(post)
            else:
                posts.append(post)
        except:
            continue

    posts.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return posts

def count_posts():
    all_posts = load_posts()
    return {
        "total":        len(all_posts),
        "pending":      sum(1 for p in all_posts if p.get("status") == "pending"),
        "approved":     sum(1 for p in all_posts if p.get("status") == "approved"),
        "published":    sum(1 for p in all_posts if p.get("status") == "published"),
        "rejected":     sum(1 for p in all_posts if p.get("status") == "rejected"),
        "regenerating": sum(1 for p in all_posts if p.get("status") == "regenerating"),
    }

def find_post_file(post_id):
    for fname in os.listdir(QUEUE_DIR):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(QUEUE_DIR, fname)
        try:
            with open(path, "r") as f:
                post = json.load(f)
            if post.get("id") == post_id:
                return path, post
        except:
            continue
    return None, None

def update_status_github(post_id, new_status):
    """Update post status directly on GitHub — works on Render's ephemeral filesystem."""
    github_token = os.getenv("GITHUB_TOKEN_PAT") or os.getenv("GITHUB_TOKEN")
    github_repo  = os.getenv("GITHUB_REPO")
    if not github_token or not github_repo:
        return False

    headers = {
        "Authorization": f"token {github_token}",
        "Accept":        "application/vnd.github.v3+json"
    }

    for folder in ["queue", "queue/stories"]:
        r = requests.get(
            f"https://api.github.com/repos/{github_repo}/contents/{folder}",
            headers=headers
        )
        if r.status_code != 200:
            continue
        for item in r.json():
            if item.get("type") == "file" and post_id in item.get("name", ""):
                r2      = requests.get(item["download_url"])
                data    = json.loads(r2.text)
                data["status"] = new_status
                import base64
                r_put = requests.put(
                    f"https://api.github.com/repos/{github_repo}/contents/{item['path']}",
                    headers=headers,
                    json={
                        "message": f"Set {post_id} to {new_status}",
                        "content": base64.b64encode(
                            json.dumps(data, indent=2).encode()
                        ).decode(),
                        "sha":    item["sha"],
                        "branch": "main"
                    }
                )
                return r_put.status_code in (200, 201)
    return False

def update_status(post_id, new_status):
    # Try GitHub API first (works on Render), fall back to local
    if update_status_github(post_id, new_status):
        return True
    path, post = find_post_file(post_id)
    if post:
        post["status"] = new_status
        with open(path, "w") as f:
            json.dump(post, f, indent=2)
        return True
    return False 

@app.route("/")
def index():
    filter_status = request.args.get("filter", "pending")
    posts  = load_posts(filter_status)
    counts = count_posts()
    now    = datetime.now().strftime("%A %d %B %Y  %H:%M")
    return render_template_string(HTML,
        posts=posts, counts=counts,
        filter=filter_status, now=now)

@app.route("/approve/<post_id>")
def approve(post_id):
    github_token = os.getenv("GITHUB_TOKEN_PAT") or os.getenv("GITHUB_TOKEN")
    github_repo  = os.getenv("GITHUB_REPO")

    if not github_token or not github_repo:
        update_status(post_id, "approved")
        return redirect(url_for("index", filter="approved"))

    headers = {
        "Authorization": f"token {github_token}",
        "Accept":        "application/vnd.github.v3+json"
    }

    # Search for the queue file on GitHub directly
    github_path = None
    sha         = None
    content_str = None

    for prefix in [f"queue/{post_id}", f"queue/stories/{post_id}"]:
        # List queue files to find the right one
        pass

    # Search all queue files on GitHub
    for folder in ["queue", "queue/stories"]:
        r = requests.get(
            f"https://api.github.com/repos/{github_repo}/contents/{folder}",
            headers=headers
        )
        if r.status_code != 200:
            continue
        for item in r.json():
            if item.get("type") == "file" and post_id in item["name"]:
                github_path = item["path"]
                sha         = item["sha"]
                # Get file content
                r2 = requests.get(item["download_url"])
                content_str = r2.text
                break
        if github_path:
            break

    if not github_path or not content_str:
        print(f"Post {post_id} not found on GitHub")
        update_status(post_id, "approved")
    else:
        try:
            import base64
            data = json.loads(content_str)
            data["status"] = "approved"
            updated = json.dumps(data, indent=2)

            r_put = requests.put(
                f"https://api.github.com/repos/{github_repo}/contents/{github_path}",
                headers=headers,
                json={
                    "message": f"Approved post {post_id}",
                    "content": base64.b64encode(updated.encode()).decode(),
                    "sha":     sha,
                    "branch":  "main"
                }
            )
            if r_put.status_code in (200, 201):
                print(f"Committed approved status to GitHub: {github_path}")
            else:
                print(f"GitHub commit failed: {r_put.status_code} {r_put.text}")
        except Exception as e:
            print(f"Error updating GitHub file: {e}")

    # Wait for GitHub to process then dispatch
    import time
    time.sleep(5)

    try:
        r = requests.post(
            f"https://api.github.com/repos/{github_repo}/dispatches",
            headers=headers,
            json={
                "event_type":     "publish_approved_post",
                "client_payload": {"post_id": post_id}
            }
        )
        print(f"Dispatch status: {r.status_code}")
    except Exception as e:
        print(f"Dispatch failed: {e}")

    return redirect(url_for("index", filter="approved"))

@app.route("/reject/<post_id>")
def reject(post_id):
    github_token = os.getenv("GITHUB_TOKEN_PAT") or os.getenv("GITHUB_TOKEN")
    github_repo  = os.getenv("GITHUB_REPO")
    content_type = "static"
    story_type   = None

    headers = {
        "Authorization": f"token {github_token}",
        "Accept":        "application/vnd.github.v3+json"
    }

    # Find and delete the file on GitHub
    for folder in ["queue", "queue/stories"]:
        try:
            r = requests.get(
                f"https://api.github.com/repos/{github_repo}/contents/{folder}",
                headers=headers
            )
            if r.status_code != 200:
                continue
            for item in r.json():
                if item.get("type") == "file" and post_id in item.get("name", ""):
                    # Get content to extract content_type
                    try:
                        r2   = requests.get(item["download_url"])
                        data = json.loads(r2.text)
                        content_type = data.get("content_type", "static")
                        story_type   = data.get("story_type")
                    except: pass
                    # Delete file on GitHub
                    requests.delete(
                        f"https://api.github.com/repos/{github_repo}/contents/{item['path']}",
                        headers=headers,
                        json={
                            "message": f"Rejected post {post_id}",
                            "sha":     item["sha"],
                            "branch":  "main"
                        }
                    )
                    print(f"Deleted {item['path']} from GitHub")
                    break
        except Exception as e:
            print(f"Error deleting from GitHub: {e}")

    # Also delete locally if exists
    path, post = find_post_file(post_id)
    if path:
        try: os.remove(path)
        except: pass

    # Trigger regeneration
    if github_token and github_repo:
        try:
            requests.post(
                f"https://api.github.com/repos/{github_repo}/dispatches",
                headers=headers,
                json={
                    "event_type": "regenerate_content",
                    "client_payload": {
                        "content_type": content_type,
                        "story_type":   story_type
                    }
                }
            )
        except Exception as e:
            print(f"Could not trigger regeneration: {e}")

    return redirect(url_for("index", filter="pending"))

@app.route("/edit", methods=["POST"])
def edit_post():
    post_id    = request.form.get("post_id")
    path, post = find_post_file(post_id)
    if not post:
        return "Post not found", 404
    post["post"]["hook"]    = request.form.get("hook",    post["post"]["hook"])
    post["post"]["caption"] = request.form.get("caption", post["post"]["caption"])
    raw_tags = request.form.get("hashtags", "")
    post["post"]["hashtags"] = [t.strip() for t in raw_tags.split() if t.strip()]
    post["scheduling"]["recommended_day"]      = request.form.get("recommended_day")
    post["scheduling"]["recommended_time_utc"] = request.form.get("recommended_time_utc")
    with open(path, "w") as f:
        json.dump(post, f, indent=2)
    try:
        from regenerate_post import regenerate_post
        regenerate_post(post_id, feedback=None)
    except Exception as e:
        print(f"Image regen failed: {e}")
    return redirect(url_for("index", filter=post.get("status", "pending")))

@app.route("/feedback", methods=["POST"])
def feedback_post():
    post_id  = request.form.get("post_id")
    feedback = request.form.get("feedback", "").strip()
    if not feedback:
        return redirect(url_for("index", filter="pending"))
    path, post = find_post_file(post_id)
    if post:
        post["pending_feedback"] = feedback
        post["status"]           = "regenerating"
        with open(path, "w") as f:
            json.dump(post, f, indent=2)
    github_token = os.getenv("GITHUB_TOKEN_PAT") or os.getenv("GITHUB_TOKEN")
    github_repo  = os.getenv("GITHUB_REPO")
    if github_token and github_repo:
        try:
            requests.post(
                f"https://api.github.com/repos/{github_repo}/dispatches",
                headers={
                    "Authorization": f"token {github_token}",
                    "Accept":        "application/vnd.github.v3+json"
                },
                json={
                    "event_type": "regenerate_content",
                    "client_payload": {
                        "post_id":      post_id,
                        "feedback":     feedback,
                        "content_type": post.get("content_type","static") if post else "static",
                        "story_type":   post.get("story_type") if post else None
                    }
                }
            )
            print(f"Async regeneration triggered for {post_id}")
        except Exception as e:
            print(f"Could not trigger regeneration: {e}")
    return redirect(url_for("index", filter="regenerating"))

@app.route("/regen_image/<post_id>", methods=["POST"])
def regen_image(post_id):
    try:
        from regenerate_post import regenerate_post
        success = regenerate_post(post_id, feedback=None)
        return jsonify({"ok": success})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

@app.route("/image/<post_id>")
def serve_image(post_id):
    path = os.path.join(QUEUE_DIR, "images", f"{post_id}.png")
    if os.path.exists(path):
        return send_file(path, mimetype="image/png")
    return "No image", 404
@app.route("/test_dispatch")
def test_dispatch():
    github_token = os.getenv("GITHUB_TOKEN_PAT") or os.getenv("GITHUB_TOKEN")
    github_repo  = os.getenv("GITHUB_REPO")
    if not github_token:
        return f"ERROR: No GitHub token found in environment", 500
    if not github_repo:
        return f"ERROR: No GitHub repo found in environment", 500
    try:
        r = requests.post(
            f"https://api.github.com/repos/{github_repo}/dispatches",
            headers={
                "Authorization": f"token {github_token}",
                "Accept":        "application/vnd.github.v3+json"
            },
            json={
                "event_type":     "publish_approved_post",
                "client_payload": {"post_id": "test_from_render"}
            }
        )
        return f"Status: {r.status_code} | Token starts with: {github_token[:8]} | Repo: {github_repo} | Response: {r.text}"
    except Exception as e:
        return f"ERROR: {e}", 500
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)