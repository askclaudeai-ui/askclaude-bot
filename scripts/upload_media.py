import os
import base64
import requests
import hashlib
import time
from dotenv import load_dotenv

load_dotenv()

IMGBB_KEY          = os.getenv("IMGBB_API_KEY")
CLOUDINARY_CLOUD   = os.getenv("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
CLOUDINARY_SECRET  = os.getenv("CLOUDINARY_API_SECRET")

def upload_image_imgbb(image_path):
    """Upload image to ImgBB. Returns public URL."""
    with open(image_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")
    r = requests.post("https://api.imgbb.com/1/upload",
                      data={"key": IMGBB_KEY, "image": encoded})
    result = r.json()
    if result.get("success"):
        return result["data"]["url"]
    raise Exception(f"ImgBB upload failed: {result}")

def upload_video_cloudinary(video_path):
    """Upload MP4 to Cloudinary. Returns public URL."""
    if not CLOUDINARY_CLOUD:
        raise Exception("Cloudinary not configured")

    timestamp  = str(int(time.time()))
    public_id  = f"askclaude_reels/{os.path.basename(video_path).replace('.mp4','')}"

    # Build signature
    params_to_sign = f"public_id={public_id}&timestamp={timestamp}"
    sig = hashlib.sha1(
        (params_to_sign + CLOUDINARY_SECRET).encode()
    ).hexdigest()

    with open(video_path, "rb") as f:
        r = requests.post(
            f"https://api.cloudinary.com/v1_1/{CLOUDINARY_CLOUD}/video/upload",
            data={
                "api_key":   CLOUDINARY_API_KEY,
                "timestamp": timestamp,
                "public_id": public_id,
                "signature": sig,
            },
            files={"file": f}
        )

    result = r.json()
    if "secure_url" in result:
        return result["secure_url"]
    raise Exception(f"Cloudinary upload failed: {result}")

def upload_image_cloudinary(image_path):
    """Upload image to Cloudinary. Returns public URL."""
    if not CLOUDINARY_CLOUD:
        raise Exception("Cloudinary not configured")

    timestamp  = str(int(time.time()))
    public_id  = f"askclaude_stories/{os.path.basename(image_path).replace('.png','')}"

    params_to_sign = f"public_id={public_id}&timestamp={timestamp}"
    sig = hashlib.sha1(
        (params_to_sign + CLOUDINARY_SECRET).encode()
    ).hexdigest()

    with open(image_path, "rb") as f:
        r = requests.post(
            f"https://api.cloudinary.com/v1_1/{CLOUDINARY_CLOUD}/image/upload",
            data={
                "api_key":   CLOUDINARY_API_KEY,
                "timestamp": timestamp,
                "public_id": public_id,
                "signature": sig,
            },
            files={"file": f}
        )

    result = r.json()
    if "secure_url" in result:
        return result["secure_url"]
    raise Exception(f"Cloudinary image upload failed: {result}")

def upload_all_slides_imgbb(image_paths):
    """Upload all carousel slides. Returns list of URLs."""
    urls = []
    for path in image_paths:
        try:
            url = upload_image_imgbb(path)
            urls.append(url)
            print(f"  Uploaded slide: {url}")
        except Exception as e:
            print(f"  Slide upload failed: {e}")
            urls.append(None)
    return urls

def upload_all_story_images(image_paths):
    """Upload all story slides to Cloudinary. Returns list of URLs."""
    urls = []
    for path in image_paths:
        try:
            url = upload_image_cloudinary(path)
            urls.append(url)
            print(f"  Uploaded story slide: {url}")
        except Exception as e:
            print(f"  Story slide upload failed: {e}")
            urls.append(None)
    return urls

def upload_image_cloudinary_feed(image_path):
    """Upload feed/carousel preview image to Cloudinary (works in emails)."""
    if not CLOUDINARY_CLOUD:
        raise Exception("Cloudinary not configured")
    import time, hashlib
    timestamp  = str(int(time.time()))
    fname      = os.path.basename(image_path).replace('.png','').replace('.jpg','')
    public_id  = f"askclaude_feed/{fname}_{timestamp}"
    params_str = f"public_id={public_id}&timestamp={timestamp}"
    sig = hashlib.sha1((params_str + CLOUDINARY_SECRET).encode()).hexdigest()
    with open(image_path, "rb") as f:
        r = requests.post(
            f"https://api.cloudinary.com/v1_1/{CLOUDINARY_CLOUD}/image/upload",
            data={
                "api_key":   CLOUDINARY_API_KEY,
                "timestamp": timestamp,
                "public_id": public_id,
                "signature": sig,
            },
            files={"file": f}
        )
    result = r.json()
    if "secure_url" in result:
        return result["secure_url"]
    raise Exception(f"Cloudinary feed image upload failed: {result}")