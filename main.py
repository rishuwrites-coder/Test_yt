"""Premium Hindi news Short generator. Test-only: never uploads or publishes."""
from __future__ import annotations
import asyncio, html, json, math, os, re, shutil, subprocess, textwrap, urllib.parse, urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import feedparser
import edge_tts
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output"
OUT.mkdir(exist_ok=True)
W, H = 1080, 1920
VOICE = os.getenv("HINDI_VOICE", "hi-IN-MadhurNeural")
VOICE_RATE = os.getenv("HINDI_VOICE_RATE", "-8%")
MIN_AGE_HOURS = 0
MAX_AGE_HOURS = 36
TARGET_SECONDS = 35
FEEDS = [
    ("BBC Hindi", "https://feeds.bbci.co.uk/hindi/rss.xml"),
    ("Google News Hindi", "https://news.google.com/rss?hl=hi&gl=IN&ceid=IN:hi"),
    ("Google News India", "https://news.google.com/rss?hl=en-IN&gl=IN&ceid=IN:en"),
]
STOP = set("और लेकिन ताकि इसके इसके लिए इस इसपर इसपर आज कल अब एक यह वह की का के को से में पर है हैं था थी थे होगा होगी होंगे कहा अनुसार खबर रिपोर्ट जानकारी भारत इंडिया सरकार लोगों देश दुनिया नई नया नए बड़ी बड़ा बड़े हुआ हुई हुए नहीं साथ तक द्वारा कारण क्योंकि अगर जब जहां जो भी क्या क्यों कैसे".split())


def clean(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", str(value or "")))).strip()


def tokens(s: str) -> set[str]:
    return {x.lower() for x in re.findall(r"[\w\u0900-\u097f]+", s) if len(x) > 2 and x.lower() not in STOP}


def similarity(a: str, b: str) -> float:
    x, y = tokens(a), tokens(b)
    return len(x & y) / max(1, len(x | y))


def get_json(url: str, timeout=12):
    req = urllib.request.Request(url, headers={"User-Agent": "HindiShortsResearch/1.0 (personal test project)"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8", "replace"))


def collect_stories():
    now = datetime.now(timezone.utc)
    stories = []
    for source, url in FEEDS:
        try:
            feed = feedparser.parse(url)
            if getattr(feed, "bozo", False) and not feed.entries:
                print(f"Feed warning: {source}: {feed.bozo_exception}")
            for entry in feed.entries[:35]:
                title, summary, link = clean(entry.get("title")), clean(entry.get("summary")), entry.get("link", "")
                if len(title) < 15 or not link.startswith("http"):
                    continue
                published = entry.get("published_parsed") or entry.get("updated_parsed")
                age = 9999
                if published:
                    try: age = max(0, (now - datetime(*published[:6], tzinfo=timezone.utc)).total_seconds()/3600)
                    except Exception: pass
                if MIN_AGE_HOURS <= age <= MAX_AGE_HOURS:
                    stories.append({"feed": source, "title": title, "summary": summary[:900], "url": link, "age_hours": round(age, 1)})
        except Exception as exc:
            print(f"Feed unavailable: {source}: {exc}")
    return stories


def choose_story(stories):
    if not stories:
        raise RuntimeError("No RSS stories from the last 36 hours. Retry the workflow later.")
    # Cluster similar headlines across feeds. This is a cross-feed signal, NOT fact-checking.
    clusters = []
    for s in sorted(stories, key=lambda x: x["age_hours"]):
        match = next((c for c in clusters if max(similarity(s["title"], m["title"]) for m in c) >= 0.24), None)
        if match is None: clusters.append([s])
        else: match.append(s)
    ranked = []
    for cluster in clusters:
        unique_feeds = len({x["feed"] for x in cluster})
        freshest = min(x["age_hours"] for x in cluster)
        best = max(cluster, key=lambda x: (len(tokens(x["title"])), -x["age_hours"]))
        ranked.append((unique_feeds, freshest, best, cluster))
    ranked.sort(key=lambda z: (z[0] >= 2, z[0], -z[1], len(tokens(z[2]["title"]))), reverse=True)
    _, _, chosen, cluster = ranked[0]
    chosen["corroboration"] = [{"feed": x["feed"], "title": x["title"], "url": x["url"]} for x in cluster]
    chosen["cross_feed_count"] = len({x["feed"] for x in cluster})
    chosen["verification_note"] = ("Similar headlines found in multiple feeds; still verify claims against original reporting and official statements." if chosen["cross_feed_count"] > 1 else "Only one matching feed found; independent corroboration is not established.")
    return chosen


def make_script(story):
    # Editorial template intentionally avoids inventing facts beyond the feed summary.
    title = story["title"].strip().rstrip("।.!? ")
    summary = re.sub(r"\s+", " ", story["summary"].strip())
    # RSS summaries can be article-length; cap them so narration stays near 30–40 seconds.
    summary_words = summary.split()[:38]
    summary = " ".join(summary_words)
    if not summary or len(tokens(summary)) < 8:
        summary = "उपलब्ध रिपोर्ट में इस खबर से जुड़ी शुरुआती जानकारी दी गई है। पूरी तस्वीर समझने के लिए मूल रिपोर्ट और संबंधित आधिकारिक बयान देखना ज़रूरी है।"
    # Keep a concise but transparent presenter script; source and uncertainty are explicit.
    script = (f"नमस्कार, इस वक्त की अहम खबर है: {title}। "
              f"रिपोर्ट के मुताबिक, {summary.rstrip('।.!?')}। "
              f"यह शुरुआती रिपोर्ट का संक्षेप है; हर दावे की स्वतंत्र पुष्टि नहीं हुई है। "
              f"पूरी जानकारी के लिए मूल रिपोर्ट और संबंधित आधिकारिक अपडेट से मिलान करें।")
    return script


def font_path():
    candidates = ["/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf",
      "/usr/share/fonts/truetype/noto/NotoSansDevanagariUI-Regular.ttf",
      "/usr/share/fonts/opentype/noto/NotoSansDevanagari-Regular.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
      "C:/Windows/Fonts/Nirmala.ttf"]
    for p in candidates:
        if Path(p).exists(): return p
    raise RuntimeError("Hindi font not found. GitHub workflow installs fonts-noto-core.")


def fetch_commons_image(query: str, dest: Path):
    """Fetch a Wikimedia Commons image only when license + attribution metadata exist."""
    terms = " ".join(list(tokens(query))[:6]) or "India news"
    params = urllib.parse.urlencode({"action":"query", "format":"json", "generator":"search", "gsrsearch":f'filetype:bitmap {terms}', "gsrnamespace":6, "gsrlimit":8, "prop":"imageinfo", "iiprop":"url|extmetadata", "iiurlwidth":1400})
    try:
        data = get_json("https://commons.wikimedia.org/w/api.php?" + params)
        pages = list(data.get("query", {}).get("pages", {}).values())
        for page in pages:
            info = (page.get("imageinfo") or [{}])[0]
            meta = info.get("extmetadata", {})
            license_name = clean(meta.get("LicenseShortName", {}).get("value", ""))
            artist = clean(meta.get("Artist", {}).get("value", ""))
            credit = clean(meta.get("Credit", {}).get("value", ""))
            url = info.get("thumburl") or info.get("url")
            if not url or not license_name: continue
            req = urllib.request.Request(url, headers={"User-Agent":"HindiShortsResearch/1.0"})
            with urllib.request.urlopen(req, timeout=18) as response:
                blob = response.read()
            dest.write_bytes(blob)
            return {"path": str(dest), "title": clean(page.get("title", "")), "url": info.get("descriptionurl", ""), "license": license_name, "artist": artist, "credit": credit}
    except Exception as exc:
        print("Commons image search unavailable; using original generated graphics:", exc)
    return None


def gradient_bg(seed=0):
    im = Image.new("RGB", (W,H)); pix = im.load()
    for y in range(H):
        t = y / H
        for x in range(W):
            glow = max(0, 1 - math.sqrt(((x/W)-0.78)**2 + ((y/H)-0.15)**2)*1.5)
            pix[x,y] = (int(7+16*t+24*glow), int(15+14*t+8*glow), int(39+24*t+35*glow))
    return im


def draw_wrap(draw, text, font, max_width):
    words = text.split(); lines=[]; line=""
    for word in words:
        test=(line+" "+word).strip()
        if draw.textbbox((0,0),test,font=font)[2] <= max_width or not line: line=test
        else: lines.append(line); line=word
    if line: lines.append(line)
    return lines


def rounded(draw, xy, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def make_ai_style_illustration(path: Path, story, index):
    """Original procedural illustration; clearly labeled, not a depiction of verified event imagery."""
    im=gradient_bg(index); d=ImageDraw.Draw(im, "RGBA")
    # abstract newsroom beams, rings, data panels, no fake people or event-specific details
    for i in range(8):
        x=80+i*145
        d.polygon([(x,0),(x+75,0),(x-360,H),(x-435,H)], fill=(25,95,160,22))
    d.ellipse((540,280,1240,980), outline=(70,180,255,95), width=8)
    d.ellipse((640,380,1140,880), outline=(255,65,82,150), width=10)
    d.ellipse((760,500,1020,760), fill=(255,65,82,170))
    d.line((80,1060,1000,1060), fill=(255,55,75,210), width=6)
    font=ImageFont.truetype(font_path(), 37)
    d.text((80,1130), "NEWS EXPLAINER", font=font, fill=(130,220,255,255))
    for i in range(5):
        y=1220+i*78; width=660-(i%3)*85
        rounded(d,(80,y,80+width,y+22),11,(150,190,220,70))
    # visible AI-style label is baked into image
    rounded(d,(70,1770,620,1850),20,(180,40,55,235))
    d.text((95,1787),"AI-STYLE ILLUSTRATION",font=ImageFont.truetype(font_path(),27),fill="white")
    im.save(path, quality=94)


def make_scene(story, script, index, total, photo, out_path):
    im=gradient_bg(index); d=ImageDraw.Draw(im, "RGBA")
    # premium Indian TV news visual identity
    d.rectangle((0,0,W,18), fill=(238,38,55,255))
    d.rectangle((0,70,W,180), fill=(10,20,43,235))
    fbrand=ImageFont.truetype(font_path(),34); fsmall=ImageFont.truetype(font_path(),27)
    d.text((58,100),"भारत | NEWS DESK",font=fbrand,fill=(255,255,255,255))
    rounded(d,(790,95,1018,155),20,(190,28,48,255)); d.text((820,109),"LIVE UPDATE",font=fsmall,fill="white")
    # headline panel
    d.rectangle((0,1330,W,1920),fill=(5,12,30,238))
    d.rectangle((0,1330,18,1920),fill=(245,45,60,255))
    d.text((60,1380),"आज की बड़ी खबर",font=ImageFont.truetype(font_path(),32),fill=(115,210,255,255))
    headline=story["title"]
    hf=ImageFont.truetype(font_path(),49 if index==0 else 42)
    y=1450
    for line in draw_wrap(d,headline,hf,940)[:4]:
        d.text((60,y),line,font=hf,fill=(255,255,255,255),stroke_width=1,stroke_fill=(0,0,0,120)); y+=64
    d.rectangle((0,1870,W,1920),fill=(180,25,45,255))
    d.text((60,1880),"स्रोत और सत्यापन नोट वीडियो के साथ TXT में",font=fsmall,fill="white")
    if photo and index==1:
        try:
            p=Image.open(photo["path"]).convert("RGB")
            # crop to scene window, dim slightly to protect text legibility
            target=(80,250,1000,1230); tw,th=target[2]-target[0],target[3]-target[1]
            ratio=max(tw/p.width,th/p.height); p=p.resize((int(p.width*ratio),int(p.height*ratio)))
            left=(p.width-tw)//2; top=(p.height-th)//2; p=p.crop((left,top,left+tw,top+th))
            p=ImageEnhance.Brightness(p).enhance(.78).filter(ImageFilter.GaussianBlur(0.2))
            im.paste(p,(target[0],target[1])); d=ImageDraw.Draw(im,"RGBA")
            d.rectangle(target,outline=(255,255,255,170),width=3)
            rounded(d,(90,1160,550,1220),15,(0,0,0,195))
            d.text((110,1173),f"PHOTO • {photo['license'][:22]}",font=fsmall,fill="white")
        except Exception as exc: print("Photo composition failed:",exc)
    else:
        # distinct AI-style illustration panels, label included
        d=ImageDraw.Draw(im,"RGBA")
        cx=540; cy=760
        d.ellipse((cx-235,cy-235,cx+235,cy+235),outline=(80,190,255,120),width=7)
        d.ellipse((cx-170,cy-170,cx+170,cy+170),outline=(245,45,60,190),width=12)
        d.polygon([(cx,cy-110),(cx+100,cy+70),(cx-100,cy+70)],fill=(80,190,255,95))
        d.text((85,1120),"AI-STYLE GRAPHIC • NOT EVENT FOOTAGE",font=fsmall,fill=(190,225,255,255))
    im.save(out_path,quality=94)


def timecode(seconds):
    ms=int(max(0,seconds)*1000); h,ms=divmod(ms,3600000); m,ms=divmod(ms,60000); s,ms=divmod(ms,1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def make_srt(script, duration, path):
    words=script.split(); chunks=[]
    # short readable phrases; subtitle text remains Hindi, max ~7 words per cue
    chunk=[]
    for word in words:
        chunk.append(word)
        if len(chunk)>=7: chunks.append(" ".join(chunk)); chunk=[]
    if chunk: chunks.append(" ".join(chunk))
    total=max(1,len(words)); elapsed=0; entries=[]
    for i,c in enumerate(chunks,1):
        start=elapsed; elapsed += duration*len(c.split())/total
        entries.append(f"{i}\n{timecode(start)} --> {timecode(min(duration,elapsed))}\n{c}\n")
    path.write_text("\n".join(entries),encoding="utf-8")


def render_video(story, script, audio, photo, stamp):
    ffmpeg=shutil.which("ffmpeg"); ffprobe=shutil.which("ffprobe")
    if not ffmpeg or not ffprobe: raise RuntimeError("FFmpeg/ffprobe missing.")
    duration=float(subprocess.run([ffprobe,"-v","error","-show_entries","format=duration","-of","default=noprint_wrappers=1:nokey=1",str(audio)],capture_output=True,text=True,check=True).stdout.strip())
    # A 30–40s target; if TTS is outside range, use FFmpeg tempo correction conservatively.
    final_audio=OUT/f"voice-final-{stamp}.mp3"
    if duration < 30 or duration > 40:
        rate=duration/35
        # atempo > 1 speeds up; < 1 slows down
        tempo=max(.85,min(1.20,duration/35))
        subprocess.run([ffmpeg,"-y","-i",str(audio),"-filter:a",f"atempo={tempo:.3f}","-b:a","128k",str(final_audio)],check=True,capture_output=True)
        audio=final_audio
        duration=float(subprocess.run([ffprobe,"-v","error","-show_entries","format=duration","-of","default=noprint_wrappers=1:nokey=1",str(audio)],capture_output=True,text=True,check=True).stdout.strip())
    duration=max(1,duration)
    srt=OUT/f"captions-{stamp}.srt"; make_srt(script,duration,srt)
    scene_texts=["INTRO • THE HEADLINE", "REPORT • WHAT IS KNOWN", "CONTEXT • WHAT TO CHECK", "TAKEAWAY • VERIFY FIRST"]
    # Four scenes with durations proportional to narration, then concatenate.
    words=script.split(); cuts=[0, .17, .52, .78, 1.0]
    durations=[duration*(cuts[i+1]-cuts[i]) for i in range(4)]
    scene_files=[]
    for i in range(4):
        scene=OUT/f"scene-{stamp}-{i+1}.png"
        make_scene(story,script,i,4,photo,scene); scene_files.append(scene)
    clips=[]
    for i,(scene,sec) in enumerate(zip(scene_files,durations)):
        clip=OUT/f"clip-{stamp}-{i+1}.mp4"; frames=max(1,round(sec*25))
        vf=f"scale=1180:2098:force_original_aspect_ratio=increase,crop=1080:1920,zoompan=z='min(zoom+0.00035,1.06)':d={frames}:s=1080x1920:fps=25,format=yuv420p"
        subprocess.run([ffmpeg,"-y","-loop","1","-i",str(scene),"-vf",vf,"-frames:v",str(frames),"-an","-c:v","libx264","-preset","veryfast","-crf","24",str(clip)],check=True,capture_output=True)
        clips.append(clip)
    concat=OUT/f"concat-{stamp}.txt"
    concat.write_text("\n".join(f"file '{p.resolve().as_posix()}'" for p in clips),encoding="utf-8")
    silent=OUT/f"silent-{stamp}.mp4"
    subprocess.run([ffmpeg,"-y","-f","concat","-safe","0","-i",str(concat),"-c","copy",str(silent)],check=True,capture_output=True)
    video=OUT/f"review-short-{stamp}.mp4"
    subpath=str(srt.resolve()).replace("\\","/").replace(":",r"\:").replace("'",r"\'")
    style="FontName=Noto Sans Devanagari,FontSize=17,PrimaryColour=&H00FFFFFF,OutlineColour=&H00101010,BackColour=&H99000000,BorderStyle=3,Outline=2,Shadow=1,Alignment=2,MarginV=290,MarginL=70,MarginR=70"
    vf=f"subtitles='{subpath}':force_style='{style}',format=yuv420p"
    subprocess.run([ffmpeg,"-y","-i",str(silent),"-i",str(audio),"-vf",vf,"-map","0:v:0","-map","1:a:0","-t",f"{duration:.3f}","-c:v","libx264","-preset","veryfast","-crf","22","-c:a","aac","-b:a","160k","-movflags","+faststart",str(video)],check=True,capture_output=True)
    # keep reviewable MP4, script/sources and thumbnail; remove bulky intermediates
    for p in clips+[concat,silent,srt]+scene_files:
        p.unlink(missing_ok=True)
    if final_audio.exists() and final_audio != audio: final_audio.unlink(missing_ok=True)
    return video,duration


def main():
    stamp=datetime.now().strftime("%Y%m%d-%H%M%S")
    stories=collect_stories(); story=choose_story(stories); script=make_script(story)
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"): raise RuntimeError("Install FFmpeg and ffprobe.")
    photo=fetch_commons_image(story["title"],OUT/f"commons-photo-{stamp}.jpg")
    if not photo: print("No suitable licensed Commons photo found; all scenes will use original graphics.")
    audio=OUT/f"voice-{stamp}.mp3"
    asyncio.run(edge_tts.Communicate(script,VOICE,rate=VOICE_RATE).save(str(audio)))
    video,duration=render_video(story,script,audio,photo,stamp)
    details={
      "status":"TEST ONLY — NOT PUBLISHED", "generated_at_utc":datetime.now(timezone.utc).isoformat(),
      "headline":story["title"],"summary_from_feed":story["summary"],"primary_feed":story["feed"],"primary_source_url":story["url"],
      "published_age_hours":story["age_hours"],"cross_feed_match_count":story["cross_feed_count"],
      "cross_feed_matches":story["corroboration"],"verification_note":story["verification_note"],
      "script_hindi":script,"voice":VOICE,"voice_rate":VOICE_RATE,"video_duration_seconds":round(duration,2),
      "visual_policy":"Procedural AI-style graphics are labeled as illustrations. Any real photo is sourced from Wikimedia Commons and its license/attribution recorded below.",
      "commons_photo":photo,"review_checklist":["Open every source link and confirm the article says what the script claims.","Check names, dates, numbers and any allegations against a primary/official source.","Confirm photo license and attribution before reusing the video.","Listen to Hindi pronunciation and inspect captions on a phone screen.","Do not publish until a human editor approves it."],
      "publishing":"No YouTube API, credentials, upload, or publishing step exists in this repository."
    }
    txt=OUT/f"review-notes-{stamp}.txt"; js=OUT/f"review-notes-{stamp}.json"
    txt.write_text("HINDI NEWS SHORT — HUMAN REVIEW REQUIRED\n\n"+f"HEADLINE: {story['title']}\nPRIMARY FEED: {story['feed']}\nPRIMARY URL: {story['url']}\nAGE: {story['age_hours']} hours\nMATCHING FEEDS: {story['cross_feed_count']}\nVERIFICATION: {story['verification_note']}\n\nSCRIPT:\n{script}\n\nOTHER MATCHES:\n"+"\n".join(f"- {m['feed']}: {m['title']}\n  {m['url']}" for m in story['corroboration'])+"\n\nPHOTO LICENSE / ATTRIBUTION:\n"+json.dumps(photo,ensure_ascii=False,indent=2)+"\n\nHUMAN REVIEW REQUIRED. This pipeline does not independently verify facts.\n",encoding="utf-8")
    js.write_text(json.dumps(details,ensure_ascii=False,indent=2),encoding="utf-8")
    # copy a thumbnail from the final first-frame design if available; a separate cover card
    cover=gradient_bg(0); d=ImageDraw.Draw(cover,"RGBA")
    d.rectangle((0,0,W,24),fill=(238,38,55,255)); d.text((70,160),"भारत | NEWS DESK",font=ImageFont.truetype(font_path(),40),fill="white")
    d.text((70,290),"आज की बड़ी खबर",font=ImageFont.truetype(font_path(),36),fill=(115,210,255,255))
    y=400
    for line in draw_wrap(d,story["title"],ImageFont.truetype(font_path(),64),930)[:7]: d.text((70,y),line,font=ImageFont.truetype(font_path(),64),fill="white"); y+=90
    rounded(d,(65,1580,760,1680),25,(190,28,48,255)); d.text((100,1603),"TEST CUT • REVIEW BEFORE USE",font=ImageFont.truetype(font_path(),30),fill="white")
    cover.save(OUT/f"thumbnail-{stamp}.png")
    print("TEST VIDEO READY:",video)
    print("REVIEW NOTES:",txt)
    print("STRUCTURED SOURCES:",js)
    print("Duration:",round(duration,2),"seconds; voice:",VOICE)

if __name__ == "__main__":
    main()
