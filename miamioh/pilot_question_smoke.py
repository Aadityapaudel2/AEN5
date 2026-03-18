from __future__ import annotations

import sys
from pathlib import Path

sys.dont_write_bytecode = True

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from browser.canvas_support import (  # noqa: E402
    InstitutionRegistry,
    build_pilot_bundle_query,
    build_pilot_override_summary_lines,
    is_schedule_query,
    retrieve_bundle_chunks,
    retrieve_pilot_override_chunks,
)


DEFAULT_QUERIES = [
    "What is this course about?",
    "When is Exam 2?",
    "When is the final?",
    "What should I know about discussions?",
    "Help me study for Quiz 6",
]

EXPECTED_MARKERS = {
    "What is this course about?": ["Students work through:", "Linear Equations"],
    "When is Exam 2?": ["Requested assessment: Exam #2", "Mar 19, 2026"],
    "When is the final?": ["Final exam window:", "May 11--15, 2026"],
    "What should I know about discussions?": ["Discussion policy:"],
    "Help me study for Quiz 6": ["Requested assessment: Quiz #6", "factoring trinomials"],
}


def _print_section(title: str) -> None:
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def main() -> int:
    registry = InstitutionRegistry.load(REPO_ROOT / "browser" / "config" / "institutions.json", project_root=REPO_ROOT)
    institution = registry.get("miamioh")
    if institution is None:
        print("MiamiOH institution record not found.")
        return 1

    failures: list[str] = []
    course_ids = ["250433"]

    for query in DEFAULT_QUERIES:
        _print_section(query)
        summary_lines = build_pilot_override_summary_lines(institution, course_ids=course_ids, query=query)
        override_limit = 4 if is_schedule_query(query) else 2
        override_chunks = retrieve_pilot_override_chunks(institution, query, course_ids=course_ids, limit=override_limit)
        bundle_query = build_pilot_bundle_query(institution, query, course_ids=course_ids)
        bundle_chunks = retrieve_bundle_chunks(institution, bundle_query, course_ids=course_ids, limit=4)

        print("Summary lines:")
        for line in summary_lines:
            print(f"- {line}")

        print("\nPilot override chunks:")
        for chunk in override_chunks:
            print(f"- [{chunk['source_type']}] {chunk['title']}")
            print(f"  {chunk['text']}")

        print("\nBundle chunks:")
        for chunk in bundle_chunks:
            print(f"- [{chunk['source_type']}] {chunk['title']}")
            print(f"  {chunk['text']}")

        haystack = "\n".join(
            summary_lines
            + [chunk.get("title", "") for chunk in override_chunks]
            + [chunk.get("text", "") for chunk in override_chunks]
            + [chunk.get("title", "") for chunk in bundle_chunks]
            + [chunk.get("text", "") for chunk in bundle_chunks]
        ).lower()
        for marker in EXPECTED_MARKERS.get(query, []):
            if marker.lower() not in haystack:
                failures.append(f"{query}: missing marker `{marker}`")

    if failures:
        _print_section("Smoke Failed")
        for failure in failures:
            print("- " + failure)
        return 1

    _print_section("Smoke Passed")
    print("All pilot question checks produced the expected MiamiOH course context.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
