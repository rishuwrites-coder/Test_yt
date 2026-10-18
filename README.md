# Premium Hindi News Shorts — test-only generator

Creates one reviewable vertical 9:16 MP4 (target 30–40 seconds), Hindi narration, burned-in Devanagari captions, thumbnail, source links, and a human-review checklist. **It never uploads or publishes to YouTube.**

## What changed
- Premium Indian TV-news visual style with four distinct scenes, subtle zoom motion, a red breaking-news strip, and mobile-first Hindi captions.
- Deep male Hindi narration using Edge TTS `hi-IN-MadhurNeural` (free/unofficial service; availability and voice quality may change).
- Recent RSS stories from BBC Hindi and Google News Hindi/India; similar headlines are grouped as a cross-feed signal.
- Optional relevant Wikimedia Commons photo when a usable file with license metadata is found. The review notes record the file page, license and attribution. If no suitable photo is found, the video uses original procedural graphics.
- Procedural graphics are marked “AI-STYLE ILLUSTRATION”; they are not actual generative-AI images and must not be mistaken for event footage.
- `review-notes.txt` and `.json` include source links, cross-feed matches, verification caveat, script, image licensing and a review checklist.
- GitHub Actions artifact is retained for 14 days. No YouTube secrets, OAuth, upload code or publishing step.

## Run on GitHub (free tier subject to GitHub limits)
1. Put these files in your repository, preserving `.github/workflows/test-video.yml`.
2. Open **Actions → Generate Premium Hindi News Test Short → Run workflow**.
3. Download the `premium-hindi-short-review` artifact from the completed run.
4. Play `review-short-*.mp4` and inspect the notes, script, source links, thumbnail and captions.

## Local run
Install Python 3.11+, FFmpeg/ffprobe, and a Devanagari font. On Ubuntu:
```bash
sudo apt-get update && sudo apt-get install -y ffmpeg fonts-noto-core
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

## Important limitations
- **Cross-feed matching is not fact-checking.** RSS entries can repeat the same wire story, have stale summaries, or be wrong. Open the source URLs and verify material claims against original reporting and primary/official sources before any use.
- The script is an original template around RSS title/summary, not a reasoning model. Review Hindi grammar, pronunciation, names, dates and claims.
- Wikimedia Commons search is best-effort and may return no suitable image. Check the individual license and attribution terms before reuse. Do not imply a generic illustration depicts the actual event.
- Edge TTS is an unofficial client to an online service, not a guaranteed SLA. No API keys are required, but internet access is needed.
- Output is a draft for human review, not publication-ready journalism. No automated upload/publishing is included.
