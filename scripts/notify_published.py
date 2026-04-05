import json
import os
import sys
import glob

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from notify import notify_post_published

posts = []
for f in glob.glob('queue/*.json'):
    try:
        d = json.load(open(f))
        if d.get('status') == 'published':
            posts.append(d)
    except:
        pass

if posts:
    posts.sort(key=lambda x: x.get('published_at', ''), reverse=True)
    p = posts[0]
    notify_post_published(p, p.get('instagram_media_id', ''))
    print(f"Published notification sent for {p.get('id')}")
else:
    print("No published posts found")
