"""Test Bilibili guest session + download."""
import sys
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "core"))

from bilibili_auth import acquire_guest_session, has_login_session, GUEST_COOKIE_FILE
from downloader import download_video

TEST_URL = 'https://www.bilibili.com/video/BV1ji596EEwi/'

print('=== Buoc 1: Lay guest session (WebView an) ===')
print('Cua so co the hien thoang roi tat — binh thuong.')
path = acquire_guest_session(video_url=TEST_URL)
if path:
    print(f'OK: cookie luu tai {path}')
else:
    print('LOI: khong lay duoc guest cookie')
    sys.exit(1)

print('\n=== Buoc 2: Tai video 720p (guest) ===')
result = download_video(
    url=TEST_URL,
    output_path=str(PROJECT_ROOT / "downloads"),
    bilibili_quality='guest',
    progress_callback=lambda m: print(f'  >> {m}', end='\r'),
)
if result['success']:
    print(f"\nOK  title length: {len(result['title'])} chars")
    print(f"    {result['filepath']}")
    print(f"    duration: {result['duration']}s")
else:
    print(f"\nLOI: {result['error']}")

if has_login_session():
    print('\n(Co session dang nhap — co the test bilibili_quality="hd")')
