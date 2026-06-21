# VietDub Backend

UI chi can khoi tao facade:

```python
from core.backend import VietDubBackend

backend = VietDubBackend()
backend.initialize()
```

## Luong chinh

```python
shop_id = backend.create_shop(
    "Shop thoi trang",
    source_language="zh-CN",
    translation_mode="google",
    export_preset="shorts",
)

project_id = backend.create_project("Batch hom nay", shop_id)
backend.add_inputs(project_id, [url_text, file_path, folder_path])
backend.start_project(project_id, event_callback=on_queue_event)
```

`event_callback` nhan dictionary:

```python
{
    "event": "started | progress | completed_step | failed | canceled | interrupted | idle",
    "job_id": 1,
    "step": "acquire | transcribe | translate | export",
    "detail": None,
}
```

## API cho UI

- `create_shop(...)`
- `create_project(...)`
- `add_inputs(...)`
- `start_project(...)`, `stop_project()`
- `cancel_job(...)`, `retry_job(...)`
- `project_dashboard(...)`, `job_detail(...)`
- `update_subtitle_text(...)`
- `resolve_issue(...)`, `approve_job(...)`
- `set_gemini_api_key(...)`, `has_gemini_api_key()`

Callback worker chay o background thread. CustomTkinter UI phai dua update ve main
thread bang `after(...)`, khong update widget truc tiep tu callback.

## Job states

```text
pending -> running -> review -> pending(export) -> completed
                  \-> failed -> pending(retry)
                  \-> canceled
```

Backend tu recover job `running` thanh `pending` khi app khoi dong lai.
