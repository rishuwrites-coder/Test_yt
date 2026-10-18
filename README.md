# Hindi Shorts Test — no publishing

This is a **test-only** project. It creates one Hindi news Short as an MP4 artifact for you to inspect. It has no YouTube upload code, no OAuth, and no publishing secrets.

## GitHub test
1. Create a private repository at https://github.com/new (example: `hindi-shorts-test`).
2. Upload the files in this folder, keeping `.github/workflows/test-video.yml`.
3. Open **Actions → Generate Test Short → Run workflow**.
4. When finished, download the `hindi-short-test` artifact from the workflow run.
5. Extract it and play the MP4. The TXT file lists the source URL and generated script.

## Local test
Install Python 3.11+ and FFmpeg. On Ubuntu/Debian:
```bash
sudo apt-get update
sudo apt-get install -y ffmpeg fonts-noto-core
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```
On Windows PowerShell, install FFmpeg and a Hindi font, then:
```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

## Limitations
RSS content is not independently verified; inspect the original source before using any video. The script uses a simple template, not an AI fact-checker. Visuals are original text graphics, not downloaded news footage. `edge-tts` is an unofficial client and may change or be rate-limited. This repo does not publish anything to YouTube.
