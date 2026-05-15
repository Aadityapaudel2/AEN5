from __future__ import annotations

import json
import shutil
from pathlib import Path


NOTEBOOKS = [
    Path(r"N:\Research\AENAIMO260_0_2_3_BENCHMARKGRADE_V1.ipynb"),
    Path(r"N:\Research\AEN_Valid_Canons\AENAIMO260_0_2_3_BENCHMARKGRADE.ipynb"),
]

OLD_REVISION = "2026-04-27-cb08-runtimeatboot-controller-section-wrapper-v1.4.4-disagreement-adjudication"
NEW_REVISION = "2026-04-27-cb08-runtimeatboot-controller-section-wrapper-v1.4.5-certification-print"

HELPER = '''

def _emit_runtime_at_boot_certification(summary: dict[str, Any], runtime: dict[str, Any] | None = None) -> dict[str, Any]:
    def _cert_int(value: Any) -> int:
        try:
            return int(value)
        except Exception:
            return 0

    def _cert_float(value: Any) -> float:
        try:
            return round(float(value), 4)
        except Exception:
            return 0.0

    payload = dict(summary or {})
    roles = dict(payload.get("roles") or {})
    role_rows: list[dict[str, Any]] = []
    for fallback_label, raw_report in roles.items():
        report = dict(raw_report or {})
        role_rows.append(
            {
                "runtime_label": str(report.get("runtime_label") or fallback_label),
                "role_name": str(report.get("role_name") or fallback_label),
                "status": str(report.get("status", "")),
                "passed": bool(report.get("passed", False)),
                "line_count": _cert_int(report.get("line_count", 0)),
                "certified_count": _cert_int(report.get("certified_count", 0)),
                "blocked_reason": str(report.get("blocked_reason", "") or ""),
                "elapsed_seconds": _cert_float(report.get("elapsed_seconds", 0)),
            }
        )
    certificate = {
        "event": "runtime_at_boot_certification",
        "revision": str(payload.get("revision", CB07_5_RUNTIME_CONTEXT_REVISION)),
        "run_id": str(payload.get("run_id", "")),
        "passed": bool(payload.get("passed", False)),
        "status": str(payload.get("status", "")),
        "blocked_reason": str(payload.get("blocked_reason", "") or ""),
        "required_runtime_labels": list(payload.get("required_runtime_labels") or []),
        "roles": role_rows,
        "total_certified_count": sum(_cert_int(row.get("certified_count", 0)) for row in role_rows),
        "total_line_count": sum(_cert_int(row.get("line_count", 0)) for row in role_rows),
        "boot_log_csv_path": str(payload.get("boot_log_csv_path", "") or ""),
        "elapsed_seconds": _cert_float(payload.get("elapsed_seconds", 0)),
    }
    if isinstance(runtime, dict):
        runtime["runtime_at_boot_certification"] = dict(certificate)
    globals()["RUNTIME_AT_BOOT_CERTIFICATION"] = dict(certificate)
    print(json.dumps(certificate, ensure_ascii=False, separators=(",", ":")), flush=True)
    return certificate
'''

RUN_GATE_NEEDLE = "def run_runtime_at_boot_gate(runtime: dict[str, Any]) -> dict[str, Any]:"
SUMMARY_PRINT_BLOCK = '''    globals()["RUNTIME_AT_BOOT_SUMMARY"] = dict(summary)
    globals()["RUNTIME_AT_BOOT_REPORTS"] = dict(role_reports)
    print(json.dumps(summary, ensure_ascii=False, separators=(",", ":")), flush=True)'''
SUMMARY_PRINT_REPLACEMENT = '''    globals()["RUNTIME_AT_BOOT_SUMMARY"] = dict(summary)
    globals()["RUNTIME_AT_BOOT_REPORTS"] = dict(role_reports)
    _emit_runtime_at_boot_certification(summary, runtime)
    print(json.dumps(summary, ensure_ascii=False, separators=(",", ":")), flush=True)'''


def patch_notebook(path: Path) -> None:
    notebook = json.loads(path.read_text(encoding="utf-8"))
    patched = False
    for cell in notebook.get("cells", []):
        source = "".join(cell.get("source", []))
        if "CB08_RUNTIME_REVISION" not in source or "run_runtime_at_boot_gate" not in source:
            continue
        source = source.replace(OLD_REVISION, NEW_REVISION)
        if "_emit_runtime_at_boot_certification" not in source:
            source = source.replace(RUN_GATE_NEEDLE, HELPER + "\n" + RUN_GATE_NEEDLE)
        if SUMMARY_PRINT_BLOCK not in source:
            raise RuntimeError(f"Expected summary print block not found in {path}")
        source = source.replace(SUMMARY_PRINT_BLOCK, SUMMARY_PRINT_REPLACEMENT)
        compile(source, f"{path}::CB08", "exec")
        cell["source"] = source.splitlines(keepends=True)
        patched = True
        break
    if not patched:
        raise RuntimeError(f"CB08 cell not found in {path}")
    backup = path.with_suffix(path.suffix + ".pre_cert_print_bak")
    if not backup.exists():
        shutil.copy2(path, backup)
    path.write_text(json.dumps(notebook, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"patched {path}")


def main() -> int:
    for notebook_path in NOTEBOOKS:
        patch_notebook(notebook_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
