import sys
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "core"))
 
from downloader import download_video
 
TEST_URLS = [
    # YouTube - video ngan test (khoang 10 giay)
    'https://youtube.com/shorts/shd4avQjheM?si=SGUzdQSRR6wyeHmF',
    'https://youtube.com/shorts/vtTqZiLDV1M?si=CgTIalksF1Tfd6tc'
]
 
def show_progress(info):
    print(f'  >> {info}', end='\r')
 
for url in TEST_URLS:
    print(f'\nThu tai: {url}')
    result = download_video(
        url=url,
        output_path=str(PROJECT_ROOT / "downloads"),
        progress_callback=show_progress
    )
    if result['success']:
        print(f'\nOK  Title   : {result["title"]}')
        print(f'    File    : {result["filepath"]}')
        print(f'    Duration: {result["duration"]}s')
    else:
        print(f'\nLOI: {result["error"]}')
