from __future__ import annotations

import argparse
import json
import mimetypes
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import quote

import uvicorn
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response, StreamingResponse

from .config_store import ConfigStore
from .models import JobRequest
from .runtime_manager import RuntimeManager
from app.media_index import build_analysis_index, is_video_file, match_analysis_files
from app.runtime_paths import configure_runtime_environment, get_bundle_root, get_runtime_root, resource_path, runtime_path


configure_runtime_environment()


class BackendService:
    """Process-wide state used by the local FastAPI application."""

    def __init__(self) -> None:
        self.config_store = ConfigStore()
        self.config_store.load()
        self.runtime_manager = RuntimeManager(self.config_store)


SERVICE = BackendService()
BUNDLE_ROOT = get_bundle_root()
RUNTIME_ROOT = get_runtime_root()
FRONTEND_DIR = resource_path("app", "frontend")
UPLOADS_DIR = runtime_path("user_temp")
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Crayotter Backend", version="0.1", docs_url="/docs", redoc_url=None)


def _within_root(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _allowed_file(path: Path) -> bool:
    return _within_root(path, RUNTIME_ROOT) or _within_root(path, BUNDLE_ROOT)


def _error(status: int, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail=message)


def _sanitize_upload_name(filename: str) -> str:
    raw_name = Path(filename or "").name.strip()
    stem, suffix = Path(raw_name).stem or "uploaded_video", Path(raw_name).suffix.lower()
    safe_stem = re.sub(r"[^0-9A-Za-z_\\-\\u4e00-\\u9fff]+", "_", stem).strip("_") or "uploaded_video"
    safe_suffix = suffix if re.fullmatch(r"\\.[0-9A-Za-z]{1,10}", suffix or "") else ""
    return f"{safe_stem}{safe_suffix}"


def _allocate_upload_path(filename: str) -> Path:
    candidate = UPLOADS_DIR / filename
    if not candidate.exists():
        return candidate
    for index in range(2, 100000):
        deduped = UPLOADS_DIR / f"{candidate.stem}_{index}{candidate.suffix}"
        if not deduped.exists():
            return deduped
    raise RuntimeError("Could not allocate an upload path.")


def _display_upload_path(path: Path) -> str:
    return (Path("user_temp") / path.relative_to(UPLOADS_DIR)).as_posix()


def _serialize_upload_item(path: Path, *, analysis_index: dict[str, list[Path]] | None = None) -> dict[str, Any]:
    stat = path.stat()
    matches = match_analysis_files(path, analysis_index=analysis_index or {}) if is_video_file(path) else []
    latest = matches[0] if matches else None
    return {
        "name": path.name,
        "path": str(path.resolve()),
        "display_path": _display_upload_path(path),
        "size_bytes": stat.st_size,
        "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        "kind": "video" if is_video_file(path) else "file",
        "has_analysis": bool(matches),
        "analysis_count": len(matches),
        "analysis_path": str(latest.resolve()) if latest else "",
        "analysis_display_path": _display_upload_path(latest) if latest else "",
        "analysis_modified_at": datetime.fromtimestamp(latest.stat().st_mtime, tz=timezone.utc).isoformat() if latest else "",
    }


def _list_upload_items() -> list[dict[str, Any]]:
    index = build_analysis_index([UPLOADS_DIR])
    return [
        _serialize_upload_item(path, analysis_index=index)
        for path in sorted(UPLOADS_DIR.rglob("*"), key=lambda item: item.stat().st_mtime, reverse=True)
        if path.is_file() and is_video_file(path)
    ]


def _resolve_upload_path(raw_path: str) -> Path | None:
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = (RUNTIME_ROOT / candidate).resolve(strict=False)
    try:
        resolved = candidate.resolve(strict=False)
        resolved.relative_to(UPLOADS_DIR.resolve())
        return resolved
    except (OSError, ValueError):
        return None


def _delete_upload(raw_path: str) -> dict[str, Any]:
    resolved = _resolve_upload_path(raw_path)
    if resolved is None:
        raise _error(400, "Upload path is outside user_temp.")
    if not resolved.exists() or not resolved.is_file():
        raise _error(404, f"Upload not found: {raw_path}")
    deleted_analysis: list[dict[str, str]] = []
    if is_video_file(resolved):
        for analysis_path in match_analysis_files(resolved, analysis_index=build_analysis_index([UPLOADS_DIR])):
            try:
                analysis_path.unlink()
                deleted_analysis.append({"path": str(analysis_path.resolve()), "display_path": _display_upload_path(analysis_path)})
            except FileNotFoundError:
                pass
    resolved.unlink()
    return {"deleted": True, "path": str(resolved), "display_path": _display_upload_path(resolved), "deleted_analysis_count": len(deleted_analysis), "deleted_analysis": deleted_analysis}


def _file_response(path: Path, request: Request, *, allow_range: bool = False, download: bool = False) -> Response:
    try:
        resolved = path.resolve(strict=True)
    except FileNotFoundError:
        raise _error(404, f"File not found: {path.name}") from None
    if not _allowed_file(resolved):
        raise _error(403, "Requested file is outside the project workspace.")
    # Starlette's FileResponse provides conditional and HTTP Range responses.
    return FileResponse(resolved, filename=resolved.name if download else None, headers={"Cache-Control": "no-store", "Accept-Ranges": "bytes" if allow_range else "none"})


@app.get("/")
def root() -> dict[str, Any]:
    return {"service": "crayotter-backend", "version": "0.1", "ui": "/ui/", "docs": "/docs"}


@app.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@app.get("/ui")
def ui_redirect() -> RedirectResponse:
    return RedirectResponse("/ui/", status_code=302)


@app.get("/ui/")
def ui_index(request: Request) -> Response:
    return _file_response(FRONTEND_DIR / "index.html", request)


@app.get("/ui/{asset_path:path}")
def ui_assets(asset_path: str, request: Request) -> Response:
    candidate = (FRONTEND_DIR / asset_path).resolve(strict=False)
    if not _within_root(candidate, FRONTEND_DIR):
        raise _error(403, "Forbidden static path.")
    return _file_response(candidate, request)


@app.get("/config")
def get_config() -> dict[str, Any]:
    return SERVICE.config_store.load().model_dump()


@app.put("/config")
async def update_config(request: Request) -> dict[str, Any]:
    try:
        return SERVICE.config_store.update(await request.json()).model_dump()
    except HTTPException:
        raise
    except Exception as exc:
        raise _error(400, str(exc)) from exc


@app.get("/jobs")
def list_jobs() -> dict[str, Any]:
    return {"items": SERVICE.runtime_manager.list_jobs()}


@app.post("/jobs", status_code=201)
async def create_job(request: Request) -> dict[str, Any]:
    try:
        return SERVICE.runtime_manager.create_job(JobRequest.model_validate(await request.json()))
    except Exception as exc:
        raise _error(400, str(exc)) from exc


@app.get("/jobs/{job_id}/events/stream")
def stream_events(job_id: str, after: int = 0) -> StreamingResponse:
    def events() -> Iterator[bytes]:
        cursor = after
        while True:
            items = SERVICE.runtime_manager.wait_for_events(job_id, after_sequence=cursor, timeout=1.0)
            if items:
                for event in items:
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\\n\\n".encode("utf-8")
                    cursor = max(cursor, int(event["sequence"]))
            else:
                yield b": ping\\n\\n"
            job = SERVICE.runtime_manager.get_job(job_id)
            if job is None or (job.record.status in {"completed", "failed", "cancelled", "interrupted"} and not items):
                yield b"event: end\\ndata: {}\\n\\n"
                return
    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "Connection": "keep-alive"})


@app.get("/jobs/{job_id}/artifacts")
def artifacts(job_id: str) -> dict[str, Any]:
    return {"items": SERVICE.runtime_manager.list_job_artifacts(job_id)}


@app.get("/jobs/{job_id}/events")
def events(job_id: str, after: int = 0) -> dict[str, Any]:
    return {"items": SERVICE.runtime_manager.list_events(job_id, after_sequence=after)}


@app.get("/jobs/{job_id}/events.log")
def events_log(job_id: str) -> Response:
    filename = quote(f"{job_id}-events.log")
    return Response(SERVICE.runtime_manager.events_log_text(job_id), media_type="text/plain", headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}", "Cache-Control": "no-store"})


@app.get("/jobs/{job_id}/messages")
def messages(job_id: str) -> dict[str, Any]:
    return {"items": SERVICE.runtime_manager.list_messages(job_id)}


@app.get("/jobs/{job_id}/plans/current")
def current_plan(job_id: str) -> dict[str, Any]:
    return SERVICE.runtime_manager.get_current_plan(job_id)


@app.get("/jobs/{job_id}/plans/diff")
def plan_diff(job_id: str, from_: str = Query("", alias="from"), to: str = "") -> dict[str, Any]:
    return SERVICE.runtime_manager.get_plan_diff(job_id, from_, to)


@app.get("/jobs/{job_id}/plans/{version}")
def plan(job_id: str, version: str) -> dict[str, Any]:
    return SERVICE.runtime_manager.get_plan(job_id, version)


@app.get("/jobs/{job_id}")
def job_detail(job_id: str) -> dict[str, Any]:
    try:
        return SERVICE.runtime_manager.get_job_detail(job_id)
    except KeyError as exc:
        raise _error(404, f"Not found: {exc.args[0]}") from exc


@app.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str) -> dict[str, Any]:
    return _job_action(lambda: SERVICE.runtime_manager.cancel_job(job_id))


@app.post("/jobs/{job_id}/resume")
def resume_job(job_id: str) -> dict[str, Any]:
    return _job_action(lambda: SERVICE.runtime_manager.resume_job(job_id))


@app.post("/jobs/{job_id}/pause")
async def pause_job(job_id: str, request: Request) -> dict[str, Any]:
    payload = await request.json()
    return _job_action(lambda: SERVICE.runtime_manager.pause_job(job_id, str(payload.get("mode") or "next_safe_point")))


@app.post("/jobs/{job_id}/approve")
async def approve_job(job_id: str, request: Request) -> dict[str, Any]:
    payload = await request.json()
    return _job_action(lambda: SERVICE.runtime_manager.approve_job(job_id, str(payload.get("pause_token") or "")))


@app.post("/jobs/{job_id}/messages", status_code=201)
async def add_message(job_id: str, request: Request) -> dict[str, Any]:
    payload = await request.json()
    return _job_action(lambda: SERVICE.runtime_manager.add_message(job_id, str(payload.get("content") or "")))


@app.post("/jobs/{job_id}/plans/{version}/{action}")
async def plan_action(job_id: str, version: str, action: str, request: Request) -> dict[str, Any]:
    payload = await request.json()
    if action == "feedback":
        return _job_action(lambda: SERVICE.runtime_manager.apply_plan_feedback(job_id, version, str(payload.get("feedback") or payload.get("content") or "")), created=True)
    if action == "approve":
        return _job_action(lambda: SERVICE.runtime_manager.approve_plan(job_id, version))
    if action == "reject":
        return _job_action(lambda: SERVICE.runtime_manager.reject_plan(job_id, version))
    raise _error(404, f"Unknown plan action: {action}")


def _job_action(action: Any, *, created: bool = False) -> dict[str, Any]:
    try:
        return action()
    except RuntimeError as exc:
        raise _error(409, str(exc)) from exc
    except KeyError as exc:
        raise _error(404, f"Not found: {exc.args[0]}") from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise _error(400, str(exc)) from exc


@app.get("/files")
def get_file(path: str, request: Request, download: bool = False) -> Response:
    if not path:
        raise _error(400, "Missing path query parameter.")
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = RUNTIME_ROOT / candidate
    return _file_response(candidate, request, allow_range=True, download=download)


@app.get("/uploads")
def uploads() -> dict[str, Any]:
    return {"items": _list_upload_items()}


@app.post("/uploads", status_code=201)
async def upload(request: Request) -> dict[str, Any]:
    try:
        form = await request.form()
        fields = form.getlist("files") or form.getlist("file")
        uploaded: list[dict[str, Any]] = []
        for field in fields:
            filename, file_obj = getattr(field, "filename", ""), getattr(field, "file", None)
            if not filename or file_obj is None:
                continue
            target = _allocate_upload_path(_sanitize_upload_name(filename))
            with target.open("wb") as handle:
                shutil.copyfileobj(file_obj, handle)
            uploaded.append(_serialize_upload_item(target))
        if not uploaded:
            raise ValueError("No valid files were uploaded.")
        return {"items": uploaded}
    except HTTPException:
        raise
    except Exception as exc:
        raise _error(400, str(exc)) from exc




@app.delete("/uploads")
def delete_upload(path: str) -> dict[str, Any]:
    if not path:
        raise _error(400, "Missing path query parameter.")
    return _delete_upload(path)


@app.delete("/jobs/{job_id}")
def delete_job(job_id: str) -> dict[str, Any]:
    return _job_action(lambda: SERVICE.runtime_manager.delete_job(job_id))


def build_uvicorn_server(host: str = "127.0.0.1", port: int = 8765) -> uvicorn.Server:
    """Build a Uvicorn server for the desktop launcher."""
    return uvicorn.Server(uvicorn.Config(app, host=host, port=port, log_level="info"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Crayotter FastAPI backend service.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
