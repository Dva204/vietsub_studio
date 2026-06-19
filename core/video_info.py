from pyexpat import errors
import subprocess, json, os

SUPPORTED_EXT = {'.mp4', '.mkv', '.mov', '.avi', '.webm'}

def get_video_info(filepath: str) -> dict:
    """
    Đọc thông tin video bằng ffprobe.
    Trả về : {valid, duration, width, height, size_mb, error}
    """
    ext = os.path.splitext(filepath)[1].lower()
    
    if ext not in SUPPORTED_EXT:
        return {'valid': False, 'error': f'Định dạng {ext} không được hỗ trợ'}
    
    if not os.path.exists(filepath):
        return {'valid': False, 'error': 'File không tồn tại'}
    
    cmd = [
        'ffprobe', '-v', 'quiet',
        '-print_format', 'json',
        '-show_streams', '-show_format',
        filepath
    ]

    try:
        out = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore',
            timeout=15
        )

       
        data = json.loads(out.stdout)

        fmt = data.get('format', {})
        stream = next((s for s in data.get('streams', []) if s.get('codec_type') == 'video'), {})

        return {
            'valid' : True,
            'duration': float(fmt.get('duration', 0)),
            'width': stream.get('width', 0),
            'height': stream.get('height', 0),
            'size_mb': round(os.path.getsize(filepath) / 1024 / 1024, 1),
            'error': None
        }
    except Exception as e:
        return {'valid': False, 'error': f'Khong doc duoc file: {e}'}
