import os, logging
from faster_whisper import WhisperModel

#Thư mục lưu model(Tránh tải lại mỗi lần)
MODEL_DIR = os.path.join(os.path.dirname(__file__), '..', 'models')
os.makedirs(MODEL_DIR,exist_ok=True)

LANGUAGE_MAP = {
    'Tieng Trung': 'zh',
    'Tieng Anh'  : 'en',
    'Tieng Nhat' : 'ja',
    'Tieng Han'  : 'ko',
}

def _get_device_config(prefer_gpu: bool = True):
    """Chọn device cho Faster-Whisper.

    Tối ưu cho mục tiêu bán app: tránh yêu cầu user cài CUDA.
    Nếu CUDA runtime/DLL không sẵn sàng (vd cublas64_12.dll) thì bắt buộc fallback CPU.
    """

    # Nếu người dùng không cho phép GPU
    if not prefer_gpu:
        return 'cpu', 'int8', 'CPU'

    # 1) Ưu tiên kiểm tra DLL CUDA có sẵn không (cách chắc chắn nhất)
    #    cublas64_12.dll thường nằm trong CUDA runtime, hoặc folder của NVIDIA.
    try:
        import ctypes

        required = 'cublas64_12.dll'
        # Try load to validate availability
        ctypes.WinDLL(required)
    except Exception:
        return 'cpu', 'int8', 'CPU'

    # 2) Nếu DLL OK thì mới kiểm tra CUDA device count
    try:
        import ctranslate2
        if ctranslate2.get_cuda_device_count() > 0:
            return 'cuda', 'float16', 'GPU (NVIDIA CUDA)'
    except Exception:
        pass

    return 'cpu', 'int8', 'CPU'



def transcribe_video(
    video_path: str,
    language: str = 'Tieng Trung',
    model_size: str = 'base',
    progress_callback = None, #Hàm nhận chuỗi trạng thái
    cancel_flag = None 
) -> dict:
    """
    Nhận diện giọng nói và xuất file SRT
    Trả về: { success, srt_path, segment_count, device_used, error }
    """
    lang_code = LANGUAGE_MAP.get(language, 'zh')
    device, compute_type, device_name = _get_device_config()

    if progress_callback:
        progress_callback(f'Dang tai model "{model_size}"({device_name})...')
    
    # Nếu đang chọn GPU mà runtime CUDA thiếu DLL, ta fallback sang CPU
    try:
        model = WhisperModel(
            model_size,
            device=device,
            compute_type=compute_type,
            download_root=MODEL_DIR
        )

    except Exception as e:
        err_msg = str(e)
        if device != 'cpu' and ('cublas' in err_msg.lower() or 'cuda' in err_msg.lower() or 'dll' in err_msg.lower()):
            fallback_device, fallback_compute, fallback_name = 'cpu', 'int8', 'CPU'
            if progress_callback:
                progress_callback(f'GPU khong san sang ({err_msg}). Fallback qua {fallback_name}...')
            try:
                model = WhisperModel(
                    model_size,
                    device=fallback_device,
                    compute_type=fallback_compute,
                    download_root=MODEL_DIR
                )
                device = fallback_device
                compute_type = fallback_compute
                device_name = fallback_name
            except Exception as e2:
                logging.error(f'Do not load Whisper (fallback CPU): {e2}')
                return {'success': False, 'error': f'Do not load the model : {e2}'}
        else:
            logging.error(f'Do not load Whisper: {e}')
            return {'success': False, 'error': f'Do not load the model : {e}'}


    if progress_callback:
        progress_callback('Detecting speaker voices... (please wait)')

    try:
        segments, info = model.transcribe(
            video_path,
            language=lang_code,
            beam_size=5,
            vad_filter=True, #Bỏ qua đoạn im lặng
        )

        #Export SRT
        srt_path = os.path.splitext(video_path)[0] + '.srt'
        count = 0

        with open(srt_path, 'w', encoding='utf-8') as f:
            for seg in segments:
                if cancel_flag and cancel_flag[0]:
                    return {'success': False, 'error': 'Canceled'}
                
                count += 1
                start = _seconds_to_srt_time(seg.start)
                end = _seconds_to_srt_time(seg.end)

                f.write(f'{count}\n{start} --> {end}\n{seg.text.strip()}\n\n')

                if progress_callback:
                    progress_callback(f'Processing {count} segments...')
                
        return {
                    'success'       : True,
                    'srt_path'      : srt_path,
                    'segment_count' : count,
                    'device_used'   : device_name,
                    'error'         : None
                }
                
    except Exception as e:
        logging.error(f'Loi STT: {e}')
        return {'success': False, 'error': str(e)}

def _seconds_to_srt_time(seconds: float) -> str:
    """Chuyen 125.4 -> '00:02:05,400'"""

    ms = int((seconds % 1) * 1000)
    s = int(seconds) % 60
    m = int(seconds) // 60 % 60
    h = int(seconds) // 3600

    return f'{h:02d}:{m:02d}:{s:02d},{ms:03d}'