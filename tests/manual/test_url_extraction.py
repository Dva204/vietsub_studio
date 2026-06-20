import re

def extract_url_douyin(str):
    match = re.search(r'https?://[^\s]+', str)
    return match.group(0) if match else None

share_text = """
5.64 kPX:/ 09/14 k@C.us :6pm 感谢一路陪伴，加油，娟你也是最棒的！你对良哥好 良哥忘不了…… # 良子大胃袋 # 良子味真足 # 味真足 # 记录生活 # 良子娟儿  https://v.douyin.com/kVe0fTxvSsg/ 复制此链接，打开Dou音搜索，直接观看视频！
"""

url = extract_url_douyin(share_text)

print(url)