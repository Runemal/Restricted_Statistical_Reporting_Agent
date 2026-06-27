from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx

from .config import load_config
from .models import Checkpoint, PipelineRunResult
from .period import current_report_period, resolve_period_path
from .quota import fetch_quota_info
from .reporting import build_summary, telegram_message
from .ssh_tunnel import SshTunnel
from .storage import run_query_file, write_rows
from .telegram import send_telegram_message


def run_pipeline(
    config_path: str | Path,
    queries_path: str | Path,
    *,
    send_telegram: bool = True,
) -> PipelineRunResult:
    checkpoints: list[Checkpoint] = []

    def ok(name: str, detail: str = "") -> None:
        checkpoints.append(Checkpoint(name=name, status="ok", detail=detail))

    def failed(name: str, detail: str) -> PipelineRunResult:
        checkpoints.append(Checkpoint(name=name, status="failed", detail=detail))
        return PipelineRunResult(status="failed", checkpoints=checkpoints, error=detail)

    try:
        config = load_config(config_path)
        ok("config_loaded", str(config_path))
        report_period = current_report_period()
        quota = fetch_quota_info()
        ok("quota_checked", "ok" if quota and not quota.error else "unavailable")

        with SshTunnel(config.ssh) as tunnel:
            ok("ssh_tunnel_opened", tunnel.base_url)
            api_path = resolve_period_path(config.api.path, report_period)
            payload = _fetch_json(tunnel.base_url, api_path, config.api.headers, config.api.timeout_seconds)
            rows = _extract_rows(payload, config.api.data_path)
            ok("api_data_fetched", f"{len(rows)} row(s)")

        saved_files = write_rows(rows, config.storage.output_dir, config.storage.dataset_name)
        ok("local_data_prepared", f"{len(rows)} row(s)")

        query_results = run_query_file(saved_files.sqlite_path, Path(queries_path))
        ok("sqlite_queries_completed", f"{len(query_results)} query result(s)")

        summary = build_summary(len(rows), query_results, report_period, quota)
        result = PipelineRunResult(
            status="ok",
            checkpoints=checkpoints,
            saved_files=saved_files,
            extracted_rows=len(rows),
            query_results=query_results,
            summary=summary,
            report_period=report_period,
            quota=quota,
        )
        try:
            if send_telegram:
                result.telegram_sent = send_telegram_message(config.telegram, telegram_message(result))
                ok("telegram_sent", str(result.telegram_sent))
            else:
                ok("telegram_skipped", "send_telegram=false")
        finally:
            _cleanup_saved_files(saved_files)
            result.saved_files = None
        return result
    except Exception as exc:
        return failed("pipeline_failed", str(exc))


def _fetch_json(base_url: str, path: str, headers: dict[str, str], timeout_seconds: int) -> Any:
    url = f"{base_url.rstrip('/')}{path}"
    with httpx.Client(timeout=timeout_seconds, follow_redirects=False) as client:
        response = client.get(url, headers=headers)
        response.raise_for_status()
        return response.json()


def _extract_rows(payload: Any, data_path: str | None) -> list[dict[str, Any]]:
    selected = _select_path(payload, data_path) if data_path else payload
    if isinstance(selected, list):
        return [_normalize_row(item) for item in selected]
    if isinstance(selected, dict):
        return [_normalize_row(selected)]
    raise ValueError("API payload data_path must resolve to an object or list of objects")


def _select_path(payload: Any, data_path: str | None) -> Any:
    current = payload
    for part in (data_path or "").split("."):
        if not part:
            continue
        if not isinstance(current, dict) or part not in current:
            raise ValueError(f"data_path part not found: {part}")
        current = current[part]
    return current


def _normalize_row(item: Any) -> dict[str, Any]:
    if isinstance(item, dict):
        return {str(key): value for key, value in item.items()}
    return {"value": item}


def _cleanup_saved_files(saved_files: Any) -> None:
    for path in (saved_files.csv_path, saved_files.sqlite_path):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
