import os
import requests
import google.generativeai as genai
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
import tempfile
import sys

GEMINI_API_KEY     = os.environ["GEMINI_API_KEY"]
PEXELS_API_KEY     = os.environ["PEXELS_API_KEY"]
TELEGRAM_TOKEN     = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID   = os.environ["TELEGRAM_CHAT_ID"]
YT_CLIENT_ID       = os.environ["YT_CLIENT_ID"]
YT_CLIENT_SECRET   = os.environ["YT_CLIENT_SECRET"]
YT_REFRESH_TOKEN   = os.environ["YT_REFRESH_TOKEN"]
LANG_MODE          = os.environ.get("LANG_MODE", "ar")

def generate_content():
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-2.0-flash")
    prompt = """
أنت منشئ محتوى يوتيوب محترف.
اكتب بالعربية الفصحى البسيطة:
1. عنوان فيديو جذاب (بدون علامات اقتباس)
2. وصف فيديو من 3 أسطر
3. 5 وسوم (tags) مفصولة بفاصلة
4. كلمة بحث واحدة بالإنجليزية لفيديوهات Pexels (مثل: nature, city, ocean)

أجب فقط بهذا الشكل:
TITLE: ...
DESCRIPTION: ...
TAGS: ...
SEARCH: ...
"""
    response = model.generate_content(prompt)
    text = response.text.strip()
    lines = {}
    for line in text.split("\n"):
        if ":" in line:
            key, _, val = line.partition(":")
            lines[key.strip()] = val.strip()
    title       = lines.get("TITLE", "فيديو يومي مميز")
    description = lines.get("DESCRIPTION", "محتوى يومي رائع")
    tags        = [t.strip() for t in lines.get("TAGS", "يوتيوب,عربي").split(",")]
    search      = lines.get("SEARCH", "nature")
    print(f"✅ العنوان: {title}")
    return title, description, tags, search

def download_pexels_video(query):
    headers = {"Authorization": PEXELS_API_KEY}
    url = f"https://api.pexels.com/videos/search?query={query}&per_page=5&min_duration=30&max_duration=180"
    res = requests.get(url, headers=headers)
    data = res.json()
    if not data.get("videos"):
        raise Exception(f"لم يتم العثور على فيديوهات لـ: {query}")
    video = data["videos"][0]
    video_files = sorted(video["video_files"], key=lambda x: x.get("width", 0), reverse=True)
    best_file = None
    for f in video_files:
        if f.get("width", 0) >= 1280:
            best_file = f
            break
    if not best_file:
        best_file = video_files[0]
    video_url = best_file["link"]
    tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    with requests.get(video_url, stream=True) as r:
        for chunk in r.iter_content(chunk_size=8192):
            tmp.write(chunk)
    tmp.close()
    print(f"✅ تم تحميل الفيديو")
    return tmp.name

def upload_to_youtube(video_path, title, description, tags):
    creds = Credentials(
        token=None,
        refresh_token=YT_REFRESH_TOKEN,
        client_id=YT_CLIENT_ID,
        client_secret=YT_CLIENT_SECRET,
        token_uri="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/youtube.upload"]
    )
    youtube = build("youtube", "v3", credentials=creds)
    body = {
        "snippet": {
            "title": title,
            "description": description + "\n\n#يوتيوب #محتوى_عربي #يومي",
            "tags": tags,
            "categoryId": "22",
            "defaultLanguage": "ar",
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
        }
    }
    media = MediaFileUpload(video_path, mimetype="video/mp4", resumable=True, chunksize=1024*1024*5)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"⬆️ رفع: {int(status.progress() * 100)}%")
    video_id = response["id"]
    video_link = f"https://youtube.com/watch?v={video_id}"
    print(f"✅ تم الرفع: {video_link}")
    return video_id, video_link

def send_telegram(title, video_link, status="✅ نجح"):
    message = (
        f"🎬 *YT-AUTO*\n"
        f"━━━━━━━━━━━━━━\n"
        f"📌 *العنوان:* {title}\n"
        f"🔗 *الرابط:* {video_link}\n"
        f"📊 *الحالة:* {status}"
    )
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    })
    print("✅ تم إرسال الإشعار على Telegram")

def main():
    print("🚀 بدء YT-AUTO...")
    video_path = None
    try:
        title, description, tags, search = generate_content()
        video_path = download_pexels_video(search)
        video_id, video_link = upload_to_youtube(video_path, title, description, tags)
        send_telegram(title, video_link, "✅ نُشر بنجاح")
        print(f"\n🎉 اكتمل! الفيديو: {video_link}")
    except Exception as e:
        print(f"❌ خطأ: {e}")
        send_telegram("خطأ في النشر", "—", f"❌ {str(e)[:200]}")
        sys.exit(1)
    finally:
        if video_path:
            try:
                os.remove(video_path)
            except:
                pass

if __name__ == "__main__":
    main()
