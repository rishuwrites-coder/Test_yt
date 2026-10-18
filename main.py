import asyncio, html, re, shutil, subprocess
from datetime import datetime, timezone
from pathlib import Path
import feedparser, edge_tts
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output"
OUT.mkdir(exist_ok=True)
VOICE = "hi-IN-SwaraNeural"
FEEDS = [
    ("Google News Hindi", "https://news.google.com/rss?hl=hi&gl=IN&ceid=IN:hi"),
    ("BBC Hindi", "https://feeds.bbci.co.uk/hindi/rss.xml"),
    ("Google News India Tech", "https://news.google.com/rss/search?q=India+technology+OR+AI&hl=en-IN&gl=IN&ceid=IN:en"),
]

def clean(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", str(s or "")))).strip()

def font_path():
    for p in [
        "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansDevanagariUI-Regular.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansDevanagari-Regular.ttf",
        "C:/Windows/Fonts/Nirmala.ttf",
    ]:
        if Path(p).exists(): return p
    raise RuntimeError("Hindi font missing. Ubuntu: install fonts-noto-core.")

def fetch_story():
    now = datetime.now(timezone.utc)
    stories = []
    for source, url in FEEDS:
        feed = feedparser.parse(url)
        for e in feed.entries[:25]:
            title, summary, link = clean(e.get("title")), clean(e.get("summary")), e.get("link", "")
            if len(title) < 12 or not link.startswith("http"): continue
            published = e.get("published_parsed") or e.get("updated_parsed")
            age = 9999
            if published:
                try: age = max(0, (now - datetime(*published[:6], tzinfo=timezone.utc)).total_seconds()/3600)
                except Exception: pass
            if age <= 48:
                stories.append({"source": source, "title": title, "summary": summary[:400],
                                "url": link, "age": round(age, 1)})
    if not stories: raise RuntimeError("No recent RSS story found. Check feeds or retry later.")
    stories.sort(key=lambda x: x["age"])
    return stories[0]

def make_script(s):
    summary = s["summary"].rstrip("।. ")
    if not summary or summary.lower() in s["title"].lower():
        summary = "इस खबर की पूरी जानकारी के लिए मूल रिपोर्ट पढ़ें"
    return (f"आज की खबर। {s['title']}। {summary}। "
            f"यह संक्षेप {s['source']} पर उपलब्ध रिपोर्ट के आधार पर तैयार किया गया है। "
            "महत्वपूर्ण जानकारी के लिए मूल स्रोत और आधिकारिक पुष्टि देखें।")

async def tts(script, path):
    await edge_tts.Communicate(script, VOICE).save(str(path))

def wrap(draw, text, font, width):
    lines, line = [], ""
    for word in text.split():
        candidate = (line + " " + word).strip()
        if draw.textbbox((0, 0), candidate, font=font)[2] <= width or not line:
            line = candidate
        else:
            lines.append(line); line = word
    if line: lines.append(line)
    return lines

def make_card(story, path):
    fp = font_path()
    im = Image.new("RGB", (1080, 1920), (12, 20, 42))
    d = ImageDraw.Draw(im)
    label = ImageFont.truetype(fp, 34)
    title = ImageFont.truetype(fp, 64)
    body = ImageFont.truetype(fp, 37)
    small = ImageFont.truetype(fp, 28)
    d.rounded_rectangle((55, 70, 1025, 165), radius=25, fill=(190, 35, 48))
    d.text((82, 90), "हिंदी न्यूज़ • टेस्ट वीडियो", font=label, fill="white")
    d.text((65, 225), "आज की मुख्य खबर", font=label, fill=(115, 208, 255))
    y = 325
    for line in wrap(d, story["title"], title, 930)[:7]:
        d.text((65, y), line, font=title, fill="white"); y += 94
    d.rounded_rectangle((60, 1060, 1020, 1515), radius=28, fill=(25, 40, 72))
    y = 1115
    for line in wrap(d, story["summary"][:320] or "पूरी जानकारी के लिए मूल रिपोर्ट देखें।", body, 850)[:6]:
        d.text((100, y), line, font=body, fill=(225, 235, 250)); y += 61
    d.text((65, 1600), f"स्रोत: {story['source']}", font=small, fill=(135, 215, 255))
    d.text((65, 1660), "मूल स्रोत लिंक साथ की TXT फ़ाइल में है", font=small, fill=(215, 225, 240))
    d.text((65, 1790), "संदर्भ देखें • पुष्टि करें", font=small, fill=(255, 205, 110))
    im.save(path)

def timecode(sec):
    ms = int(max(0, sec)*1000)
    h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"

def make_srt(script, duration, path):
    words, chunks, chunk = script.split(), [], []
    for word in words:
        chunk.append(word)
        if len(chunk) >= 6: chunks.append(" ".join(chunk)); chunk=[]
    if chunk: chunks.append(" ".join(chunk))
    elapsed, entries = 0.0, []
    for i, c in enumerate(chunks, 1):
        start = elapsed
        elapsed += duration * len(c.split()) / max(1, len(words))
        entries.append(f"{i}\n{timecode(start)} --> {timecode(min(duration, elapsed))}\n{c}\n")
    path.write_text("\n".join(entries), encoding="utf-8")

def render(story, script, audio, video, card):
    ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if not ffmpeg or not ffprobe: raise RuntimeError("Install FFmpeg and ffprobe first.")
    make_card(story, card)
    result = subprocess.run([ffprobe, "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(audio)], capture_output=True, text=True, check=True)
    duration = float(result.stdout.strip())
    srt = video.with_suffix(".srt")
    make_srt(script, duration, srt)
    subpath = str(srt.resolve()).replace("\\", "/").replace(":", r"\:")
    vf = f"scale=1080:1920,subtitles='{subpath}':force_style='FontName=Noto Sans Devanagari,FontSize=18,Outline=2,Shadow=1,Alignment=2,MarginV=240',format=yuv420p"
    subprocess.run([ffmpeg, "-y", "-loop", "1", "-framerate", "25", "-i", str(card),
        "-i", str(audio), "-vf", vf, "-c:v", "libx264", "-preset", "veryfast",
        "-tune", "stillimage", "-c:a", "aac", "-b:a", "128k", "-shortest",
        "-movflags", "+faststart", str(video)], check=True)
    srt.unlink(missing_ok=True)

def main():
    story = fetch_story()
    script = make_script(story)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    video, audio, card = OUT/f"test-short-{stamp}.mp4", OUT/f"voice-{stamp}.mp3", OUT/f"card-{stamp}.png"
    info = OUT/f"test-short-{stamp}.txt"
    info.write_text(
        f"TEST ONLY — NOT PUBLISHED\nHeadline: {story['title']}\n"
        f"Source: {story['source']}\nURL: {story['url']}\nAge hours: {story['age']}\n\n"
        f"SCRIPT:\n{script}\n", encoding="utf-8")
    print("Selected:", story["title"]); print("Source:", story["url"])
    asyncio.run(tts(script, audio))
    render(story, script, audio, video, card)
    print("SUCCESS. Video:", video)
    print("Source/script details:", info)

if __name__ == "__main__":
    main()
