#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.evals.checks import EvalFailure, evaluate_cases, load_cases, load_manifest_source_ids


DEFAULT_CASES = ROOT / "backend" / "app" / "evals" / "golden_cases.json"
DEFAULT_MANIFEST = ROOT / "dataroom" / "manifest.json"


def post_question(base_url: str, question: str, timeout: float) -> dict:
    payload = json.dumps({"question": question}).encode("utf-8")
    request = urllib.request.Request(
        base_url.rstrip("/") + "/ask",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise EvalFailure(f"HTTP {exc.code} from /ask: {body}") from exc
    except urllib.error.URLError as exc:
        raise EvalFailure(f"Could not reach {base_url.rstrip('/')}/ask: {exc.reason}") from exc
    return json.loads(body)


def get_json(base_url: str, path: str, timeout: float) -> dict:
    url = base_url.rstrip("/") + path
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise EvalFailure(f"HTTP {exc.code} from {path}: {body}") from exc
    except urllib.error.URLError as exc:
        raise EvalFailure(f"Could not reach {url}: {exc.reason}") from exc
    return json.loads(body)


def run_smoke_checks(base_url: str, timeout: float) -> list[dict]:
    checks = []

    health = get_json(base_url, "/health", timeout)
    health_failures = []
    if health.get("ok") is not True:
        health_failures.append("/health must return ok=true")
    checks.append({"id": "health", "passed": not health_failures, "failures": health_failures})

    sources = get_json(base_url, "/sources", timeout)
    sources_failures = []
    source_items = sources.get("sources")
    if not isinstance(source_items, list):
        sources_failures.append("/sources must return a sources list")
    elif len(source_items) == 0:
        sources_failures.append("/sources must return at least one source")
    checks.append({"id": "sources", "passed": not sources_failures, "failures": sources_failures})

    return checks


def load_response_fixture(path: Path) -> dict[str, dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        return data
    if isinstance(data, list):
        return {item["id"]: item["response"] for item in data}
    raise EvalFailure("Response fixture must be a dict keyed by case id or a list of {id, response} objects.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run golden answer-quality evals for the dataroom assistant.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="FastAPI base URL for /ask.")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES, help="Golden eval case JSON file.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST, help="Dataroom manifest used to validate cited source ids.")
    parser.add_argument("--responses", type=Path, help="Optional offline response fixture instead of calling /ask.")
    parser.add_argument("--timeout", type=float, default=20.0, help="HTTP timeout per question in seconds.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON results.")
    args = parser.parse_args()

    cases = load_cases(args.cases)
    manifest_source_ids = load_manifest_source_ids(args.manifest)

    smoke_checks: list[dict] = []
    if args.responses:
        response_fixture = load_response_fixture(args.responses)

        def answer_for(case: dict) -> dict:
            try:
                return response_fixture[case["id"]]
            except KeyError as exc:
                raise EvalFailure(f"Missing offline response for case {case['id']!r}.") from exc

    else:
        try:
            smoke_checks = run_smoke_checks(args.base_url, args.timeout)
        except Exception as exc:  # noqa: BLE001 - eval runners should report all case failures.
            smoke_checks = [{"id": "api_smoke", "passed": False, "failures": [str(exc)]}]

        def answer_for(case: dict) -> dict:
            return post_question(args.base_url, case["question"], args.timeout)

    results = evaluate_cases(cases, answer_for, manifest_source_ids)
    passed = sum(1 for result in results if result["passed"])
    failed = len(results) - passed
    smoke_failed = sum(1 for check in smoke_checks if not check["passed"])

    if args.json:
        print(
            json.dumps(
                {
                    "total": len(results),
                    "passed": passed,
                    "failed": failed,
                    "smoke_checks": smoke_checks,
                    "results": results,
                },
                indent=2,
            )
        )
    else:
        for check in smoke_checks:
            status = "PASS" if check["passed"] else "FAIL"
            print(f"{status} smoke/{check['id']}")
            for failure in check["failures"]:
                print(f"  - {failure}")
        print(f"Golden evals: {passed}/{len(results)} passed")
        for result in results:
            status = "PASS" if result["passed"] else "FAIL"
            print(f"{status} {result['id']}: {result['question']}")
            for failure in result["failures"]:
                print(f"  - {failure}")

    return 0 if failed == 0 and smoke_failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
