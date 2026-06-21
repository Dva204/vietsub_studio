import yt_dlp
import os
import logging
import re
from urllib.parse import urlsplit, urlunsplit

try:
    from core.bilibili_auth import (
        ensure_bilibili_cookies,
        get_cookie_file_for_quality,
        has_login_session,
        refresh_session_on_412,
    )
except ModuleNotFoundError:
    from bilibili_auth import (
    ensure_bilibili_cookies,
    get_cookie_file_for_quality,
    has_login_session,
    refresh_session_on_412,
    )

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

FORMAT_CANDIDATES = (
    {
        'format': 'bv*+ba/b',
        'merge_output_format': 'mp4',
        'format_sort': ['res:1080', 'ext:mp4:m4a', 'codec:h264', 'size'],
    },
    {
        'format': 'best',
        'merge_output_format': 'mp4',
    },
    {
        'format': 'bestvideo+bestaudio/best/worst',
        'merge_output_format': 'mp4',
    },
)

BILIBILI_FORMAT_GUEST = (
    {
        'format': 'bestvideo[height<=720]+bestaudio/best[height<=720]/best',
        'merge_output_format': 'mp4',
        'format_sort': ['res:720', 'ext:mp4:m4a', 'codec:h264'],
    },
    {
        'format': 'best',
        'merge_output_format': 'mp4',
    },
)

BILIBILI_FORMAT_HD = (
    {
        'format': 'bv*+ba/b',
        'merge_output_format': 'mp4',
        'format_sort': ['res:1080', 'ext:mp4:m4a', 'codec:h264', 'size'],
    },
    {
        'format': 'best',
        'merge_output_format': 'mp4',
    },
)


def extract_url(text: str) -> str | None:
    match = re.search(r'https?://[^\s\u4e00-\u9fff]+', text)
    if not match:
        return None
    url = match.group(0).rstrip('.,;:!?)】」\'"')
    return url or None


def clean_url(url: str) -> str:
    parsed = urlsplit(url)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, '', ''))


def is_bilibili_url(url: str) -> bool:
    host = urlsplit(url).netloc.lower()
    return 'bilibili.com' in host or host == 'b23.tv'


def is_tiktok_url(url: str) -> bool:
    host = urlsplit(url).netloc.lower()
    return 'tiktok.com' in host


def _has_curl_cffi() -> bool:
    try:
        import curl_cffi  # noqa: F401
        return True
    except ImportError:
        return False


def _format_candidates_for_url(url: str, bilibili_quality: str) -> tuple:
    if is_bilibili_url(url):
        if bilibili_quality == 'hd':
            return BILIBILI_FORMAT_HD
        return BILIBILI_FORMAT_GUEST
    return FORMAT_CANDIDATES


def _build_auth_strategies(
    url: str,
    cookies_file: str | None,
    bilibili_quality: str,
) -> list[dict]:
    strategies: list[dict] = [{}]

    if is_bilibili_url(url):
        cookie_path = cookies_file or get_cookie_file_for_quality(bilibili_quality)
        if cookie_path and os.path.isfile(cookie_path):
            strategies = [{'cookiefile': str(cookie_path)}]
        return strategies

    if cookies_file and os.path.isfile(cookies_file):
        strategies.append({'cookiefile': os.path.abspath(cookies_file)})

    return strategies


def _build_ydl_opts(
    output_path: str,
    format_opts: dict,
    progress_hook,
    url: str,
    auth_opts: dict | None = None,
) -> dict:
    headers = {
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/138.0.0.0 Safari/537.36'
        ),
    }
    if is_bilibili_url(url):
        headers['Referer'] = 'https://www.bilibili.com/'
        headers['Origin'] = 'https://www.bilibili.com'

    opts = {
        'outtmpl': os.path.join(output_path, '%(title)s.%(ext)s'),
        'quiet': True,
        'no_warnings': True,
        'retries': 5,
        'fragment_retries': 5,
        'socket_timeout': 30,
        'progress_hooks': [progress_hook],
        'http_headers': headers,
        **(auth_opts or {}),
        **format_opts,
    }
    if is_tiktok_url(url) and _has_curl_cffi():
        from yt_dlp.networking.impersonate import ImpersonateTarget
        opts['impersonate'] = ImpersonateTarget.from_str('chrome')
    return opts


def _is_format_error(error: Exception) -> bool:
    msg = str(error).lower()
    return 'requested format is not available' in msg or 'no video formats' in msg


def _is_bilibili_auth_error(error: Exception) -> bool:
    msg = str(error).lower()
    return '412' in msg or 'precondition failed' in msg


def _is_tiktok_impersonation_error(error: Exception) -> bool:
    msg = str(error).lower()
    return (
        'impersonate target is available' in msg
        or 'unable to extract universal data for rehydration' in msg
    )


def _needs_bilibili_login(error: Exception) -> bool:
    msg = str(error).lower()
    return 'premium member' in msg or 'requires premium' in msg


def download_video(
    url: str,
    output_path: str,
    progress_callback=None,
    cancel_flag=None,
    cookies_file: str | None = None,
    bilibili_quality: str = 'guest',
    bilibili_login_callback=None,
) -> dict:
    """
    Download video from YouTube/Tiktok/Douyin/Bilibili.

    bilibili_quality:
      - 'guest': tu dong lay session (~720p), khong can user lam gi
      - 'hd': can dang nhap Bilibili trong app (1080p)

    bilibili_login_callback: ham goi khi can mo cua so dang nhap (tu UI)
    """
    extracted_url = extract_url(url)
    if extracted_url:
        url = clean_url(extracted_url)
    elif not url.startswith('http'):
        return {
            'success': False,
            'filepath': None,
            'error': 'Khong tim thay URL hop le trong chuoi da nhap',
        }

    if is_bilibili_url(url):
        if bilibili_quality == 'hd' and not cookies_file:
            cookie_path = ensure_bilibili_cookies(
                quality='hd',
                login_callback=bilibili_login_callback,
            )
            if not cookie_path:
                return {
                    'success': False,
                    'filepath': None,
                    'error': (
                        'Can dang nhap Bilibili de tai 1080p. '
                        'Nhan "Ket noi Bilibili" trong app.'
                    ),
                    'needs_bilibili_login': True,
                }
            cookies_file = str(cookie_path)
        elif not cookies_file:
            cookie_path = ensure_bilibili_cookies(
                quality='guest',
                video_url=url,
            )
            if cookie_path:
                cookies_file = str(cookie_path)

    os.makedirs(output_path, exist_ok=True)

    def _notify_progress(message: str):
        if not progress_callback:
            return
        try:
            progress_callback(message)
        except Exception:
            logging.debug('progress_callback failed', exc_info=True)

    def progress_hook(d):
        if cancel_flag and cancel_flag[0]:
            raise Exception('Download cancelled by user')

        if d['status'] == 'downloading':
            pct = d.get('percent_str', '0%').strip()
            speed = d.get('_speed_str', '').strip()
            eta = d.get('_eta_str', '').strip()
            _notify_progress(f'{pct} | {speed} | {eta}')
        elif d['status'] == 'finished':
            _notify_progress('Merging Audio + Video...')

    format_candidates = _format_candidates_for_url(url, bilibili_quality)
    cookie_path = cookies_file
    last_error = None

    for attempt in range(2):
        auth_strategies = _build_auth_strategies(
            url, cookie_path, bilibili_quality,
        )
        for auth_opts in auth_strategies:
            for index, format_opts in enumerate(format_candidates):
                ydl_opts = _build_ydl_opts(
                    output_path, format_opts, progress_hook, url, auth_opts,
                )
                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(url, download=True)

                        filepath = ydl.prepare_filename(info)
                        base = os.path.splitext(filepath)[0]
                        if not filepath.endswith('.mp4'):
                            filepath = base + '.mp4'

                        return {
                            'success': True,
                            'filepath': filepath,
                            'title': info.get('title', 'Unknown Title'),
                            'duration': info.get('duration', 0),
                            'platform': info.get('extractor', 'unknown'),
                            'format_strategy': index + 1,
                            'bilibili_quality': bilibili_quality,
                            'error': None,
                        }
                except yt_dlp.utils.DownloadError as e:
                    last_error = e
                    if _is_format_error(e) and index < len(format_candidates) - 1:
                        continue
                    if _needs_bilibili_login(e) and bilibili_quality == 'guest':
                        return {
                            'success': False,
                            'filepath': None,
                            'error': (
                                'Video nay can tai chat luong cao hon. '
                                'Hay chon 1080p va dang nhap Bilibili.'
                            ),
                            'needs_bilibili_login': True,
                        }
                    break
                except Exception as e:
                    last_error = e
                    break
            else:
                continue
            break

        if (
            attempt == 0
            and is_bilibili_url(url)
            and _is_bilibili_auth_error(last_error)
        ):
            logging.warning('Bilibili 412, refreshing guest session...')
            refreshed = refresh_session_on_412(video_url=url)
            if refreshed:
                cookie_path = str(refreshed)
                last_error = None
                continue
        break

    logging.error('Download error: %s', last_error)
    return _build_error_result(last_error, url, bilibili_quality)


def _build_error_result(
    last_error: Exception | None,
    url: str,
    bilibili_quality: str,
) -> dict:
    msg = str(last_error) if last_error else 'Unknown download error'
    result = {'success': False, 'filepath': None, 'error': msg}

    if 'unsupported' in msg.lower():
        result['error'] = 'Unsupported format'
    elif 'private' in msg.lower():
        result['error'] = 'This video is private, cannot be downloaded'
    elif _is_format_error(last_error):
        result['error'] = 'Video khong co format phu hop. Hay cap nhat yt-dlp.'
    elif _is_tiktok_impersonation_error(last_error):
        if not _has_curl_cffi():
            result['error'] = (
                'TikTok can curl-cffi. Chay: pip install "yt-dlp[default,curl-cffi]"'
            )
        else:
            result['error'] = (
                'TikTok tu choi request. Thu cap nhat yt-dlp: pip install -U yt-dlp'
            )
    elif _is_bilibili_auth_error(last_error) and is_bilibili_url(url):
        result['error'] = (
            'Khong the ket noi Bilibili. Thu lai sau hoac chon 1080p + dang nhap.'
        )
        result['needs_bilibili_refresh'] = True
    elif bilibili_quality == 'hd' and not has_login_session():
        result['error'] = 'Can dang nhap Bilibili de tai 1080p.'
        result['needs_bilibili_login'] = True

    return result
