import sys
sys.path.append('..')   # De import tu thu muc cha
 
from downloader import download_video
 
TEST_URLS = [
    # YouTube - video ngan test (khoang 10 giay)
    'https://youtu.be/G8Zz2XfJxag?si=zavmkNRoFPVk695C',
    # Them URL TikTok that cua ban vao day de test
    '3.33 :2pm 04/25 Mws:/ L@W.MJ 我醒了 今天还是才艺请假条～  https://v.douyin.com/-85_-5SxslU/ 复制此链接，打开Dou音搜索，直接观看视频！',
    'https://www.tiktok.com/@benngoaibanco/video/7624761240597957908?is_from_webapp=1&sender_device=pc',
    '【真正的齐响诗班，英哭花笑银狼闹】 https://www.bilibili.com/video/BV1ji596EEwi/?share_source=copy_web',
    'https://www.facebook.com/share/r/1K8R38i4Rb/',
    'https://youtube.com/shorts/HXOseXsk050?si=pfzEsR_Dsm6x2GWm'
]
 
def show_progress(info):
    print(f'  >> {info}', end='\r')
 
for url in TEST_URLS:
    print(f'\nThu tai: {url}')
    result = download_video(
        url=url,
        output_path='../downloads',
        progress_callback=show_progress
    )
    if result['success']:
        print(f'\nOK  Title   : {result["title"]}')
        print(f'    File    : {result["filepath"]}')
        print(f'    Duration: {result["duration"]}s')
    else:
        print(f'\nLOI: {result["error"]}')
