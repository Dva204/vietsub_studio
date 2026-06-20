# Tests

## Unit tests

Chay offline, khong goi API va khong tai video:

```powershell
python -m unittest discover -s tests/unit -v
```

## Manual tests

Nhung script nay co the can Internet, API key, GUI, model hoac file media.
Chay tung file tu thu muc goc cua du an, vi du:

```powershell
python tests/manual/test_env.py
python tests/manual/test_translate_files.py
python tests/manual/test_subtitle_workspace.py
python tests/manual/test_gemini_connection.py
python tests/manual/test_transcriber.py
python tests/manual/test_tts.py
python tests/manual/test_exporter.py
python tests/manual/test_downloader.py
python tests/manual/test_bilibili_auth.py
```
