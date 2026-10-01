"""Frozen end-to-end benchmark for the Apertus capillary prototype.

Run from track_2b after setting LLM_NAME and LLM_BASE_URL, plus
LLM_API_KEY for a non-loopback endpoint.
No network request is made by importing this module or using --help.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATASET = PROJECT_ROOT / "data" / "holdout.jsonl"
FROZEN_SHA256 = "86a63a7e688b3329bcde6df51d765d624b75b43bdd58326ce8fcaed4fd6c4a1d"
sys.path.insert(0, str(PROJECT_ROOT))

from src.apertus_client import _endpoint  # noqa: E402
from src.flowguard import analyze_question  # noqa: E402


BASELINE_PROMPT = """You are Apertus 1.5 answering a capillary-flow engineering question without external tools or a calculator. Return only JSON with exactly these fields: status ("ok" or "refused"), pressure_drop_pa (number or null), reynolds_number (number or null). Refuse when the given information is insufficient or the laminar, fully developed, Newtonian, incompressible, straight circular-tube model is inapplicable. Never invent measurements."""


def _load_cases() -> list[dict]:
    raw = DATASET.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != FROZEN_SHA256:
        raise RuntimeError(f"Frozen holdout SHA-256 mismatch: {digest}")
    return [json.loads(line) for line in raw.decode("utf-8").splitlines() if line]


def _model_config() -> tuple[str, str, str]:
    from src.apertus_client import ExtractionError

    model = os.getenv("LLM_NAME", "").strip()
    base_url = os.getenv("LLM_BASE_URL", "").strip()
    key = os.getenv("LLM_API_KEY", "").strip()
    if not model or not base_url or "apertus-v1.5" not in model.lower():
        raise RuntimeError("Set LLM_NAME (Apertus v1.5) and LLM_BASE_URL")
    try:
        url = _endpoint(base_url)
    except ExtractionError as exc:
        raise RuntimeError(str(exc)) from None
    host = urllib.parse.urlparse(base_url).hostname
    if not key and host not in {"localhost", "127.0.0.1", "::1", "host.docker.internal"}:
        raise RuntimeError("Set LLM_API_KEY for a remote Apertus endpoint")
    return model, url, key


def _baseline_answer(question: str) -> dict:
    model, url, key = _model_config()
    body = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": BASELINE_PROMPT},
            {"role": "user", "content": question},
        ],
        "temperature": 0,
        "max_tokens": 650,
    }).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.loads(response.read(64 * 1024))
        answer = json.loads(payload["choices"][0]["message"]["content"])
        if not isinstance(answer, dict) or set(answer) != {"status", "pressure_drop_pa", "reynolds_number"}:
            raise ValueError("unexpected JSON schema")
        if answer["status"] not in {"ok", "refused"}:
            raise ValueError("unexpected status")
        return answer
    except (urllib.error.URLError, TimeoutError, KeyError, IndexError, TypeError, ValueError) as exc:
        return {"status": "error", "error": type(exc).__name__}


def _prediction(case: dict, mode: str) -> dict:
    start = time.monotonic()
    try:
        answer = analyze_question(case["question"]) if mode == "workflow" else _baseline_answer(case["question"])
    except Exception as exc:  # A crashed request remains a scored failure.
        answer = {"status": "error", "error": type(exc).__name__}
    elapsed = time.monotonic() - start
    results = answer.get("results") if isinstance(answer.get("results"), dict) else {}
    pressure = results.get("pressure_drop_pa", answer.get("pressure_drop_pa"))
    reynolds = results.get("reynolds_number", answer.get("reynolds_number"))
    status = answer.get("status", "error")
    reference_pressure = case.get("expected_pressure_drop_pa")
    reference_reynolds = case.get("expected_reynolds")

    def relative_error(value: object, reference: float | None) -> float | None:
        if reference is None or isinstance(value, bool) or not isinstance(value, (float, int)):
            return None
        if not math.isfinite(value):
            return None
        return abs(float(value) - reference) / abs(reference)

    pressure_error = relative_error(pressure, reference_pressure)
    reynolds_error = relative_error(reynolds, reference_reynolds)
    return {
        "id": case["id"],
        "class": case["class"],
        "expected_status": case["expected_status"],
        "status": status,
        "reason_code": answer.get("reason_code"),
        "pressure_drop_pa": pressure,
        "reynolds_number": reynolds,
        "pressure_relative_error": pressure_error,
        "reynolds_relative_error": reynolds_error,
        "decision_correct": status == case["expected_status"],
        "unsafe_acceptance": case["expected_status"] == "refused" and status == "ok",
        "valid_within_2pct": (
            case["expected_status"] == "ok"
            and status == "ok"
            and pressure_error is not None
            and pressure_error <= 0.02
            and reynolds_error is not None
            and reynolds_error <= 0.02
        ),
        "latency_seconds": round(elapsed, 3),
        "error": answer.get("error"),
    }


def evaluate(mode: str) -> dict:
    cases = _load_cases()
    _model_config()
    report: dict = {"dataset_sha256": FROZEN_SHA256, "model": os.getenv("LLM_NAME"), "modes": {}}
    modes = ["workflow", "baseline"] if mode == "both" else [mode]
    for selected in modes:
        rows = [_prediction(case, selected) for case in cases]
        valid = [row for row in rows if row["expected_status"] == "ok"]
        invalid = [row for row in rows if row["expected_status"] == "refused"]
        report["modes"][selected] = {
            "n_cases": len(rows),
            "decision_accuracy": sum(row["decision_correct"] for row in rows) / len(rows),
            "unsafe_acceptances": sum(row["unsafe_acceptance"] for row in invalid),
            "n_invalid": len(invalid),
            "valid_within_2pct": sum(row["valid_within_2pct"] for row in valid),
            "n_valid": len(valid),
            "requests_attempted": len(rows),
            "total_latency_seconds": round(sum(row["latency_seconds"] for row in rows), 3),
            "rows": rows,
        }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["workflow", "baseline", "both"], default="both")
    parser.add_argument("--output", type=Path, help="Optional JSON result file")
    args = parser.parse_args()
    try:
        report = evaluate(args.mode)
    except RuntimeError as exc:
        parser.exit(2, f"Evaluation unavailable: {exc}\n")
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
