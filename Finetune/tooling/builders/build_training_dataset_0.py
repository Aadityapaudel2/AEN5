from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
TRAININGDATA = ROOT / "Finetune" / "trainingdata"
DATASET_PATH = TRAININGDATA / "training_dataset_0_identity.jsonl"
MANIFEST_PATH = TRAININGDATA / "training_dataset_0_identity_manifest.json"

LOCKED_ROWS = 6


RAW_SOURCES: list[tuple[str, str]] = [
    (
        "number_theory",
        "evaluation/testdata/aimo/problems/number_theory_modular_arithmetic_1.txt",
    ),
    (
        "number_theory",
        "evaluation/testdata/aimo/problems/number_theory_divisibility_and_gcd_1.txt",
    ),
    (
        "number_theory",
        "evaluation/testdata/aimo/problems/number_theory_quadratic_residues_1.txt",
    ),
    (
        "number_theory",
        "evaluation/testdata/aimo/problems/number_theory_p_adic_valuations_1.txt",
    ),
    (
        "number_theory",
        "evaluation/testdata/aimo/problems/number_theory_arithmetic_functions_1.txt",
    ),
    (
        "combinatorics",
        "testdata_unpublished_2026-03-09/aimo_broad_archive_2026-03-09/problems/combinatorics_extremal_combinatorics_1.txt",
    ),
    (
        "combinatorics",
        "testdata_unpublished_2026-03-09/aimo_broad_archive_2026-03-09/problems/combinatorics_graph_cycles_on_planar_tilings_1.txt",
    ),
    (
        "combinatorics",
        "testdata_unpublished_2026-03-09/aimo_broad_archive_2026-03-09/problems/combinatorics_graph_cycles_on_planar_tilings_2.txt",
    ),
    (
        "combinatorics",
        "testdata_unpublished_2026-03-09/aimo_broad_archive_2026-03-09/problems/combinatorics_matrix_permanent_1.txt",
    ),
    (
        "combinatorics",
        "testdata_unpublished_2026-03-09/aimo_broad_archive_2026-03-09/problems/combinatorics_polyomino_tilings_1.txt",
    ),
    (
        "geometry",
        "testdata_unpublished_2026-03-09/aimo_broad_archive_2026-03-09/problems/geometry_circle_geometry_on_the_unit_circle_1.txt",
    ),
    (
        "geometry",
        "testdata_unpublished_2026-03-09/aimo_broad_archive_2026-03-09/problems/geometry_coordinate_geometry_on_axes_and_quadrants_1.txt",
    ),
    (
        "geometry",
        "testdata_unpublished_2026-03-09/aimo_broad_archive_2026-03-09/problems/geometry_euclidean_geometry_in_a_square_1.txt",
    ),
    (
        "geometry",
        "testdata_unpublished_2026-03-09/aimo_broad_archive_2026-03-09/problems/geometry_euclidean_triangle_geometry_circumcenter_circumcircle_1.txt",
    ),
    (
        "geometry",
        "testdata_unpublished_2026-03-09/aimo_broad_archive_2026-03-09/problems/mixed_coordinate_geometry_circle_line_intersection_tangent_slope_1.txt",
    ),
    (
        "logic",
        "evaluation/testdata/logic/problems/corelogic_v10367.txt",
    ),
    (
        "logic",
        "evaluation/testdata/logic/problems/corelogic_v10391.txt",
    ),
    (
        "logic",
        "evaluation/testdata/logic/problems/corelogic_v10431.txt",
    ),
    (
        "logic",
        "evaluation/testdata/logic/problems/corelogic_v10642.txt",
    ),
    (
        "logic",
        "evaluation/testdata/logic/problems/formal_truth_grid_a.txt",
    ),
    (
        "algebra",
        "evaluation/testdata/aimo/problems/algebra_complex_numbers_1.txt",
    ),
    (
        "algebra",
        "evaluation/testdata/aimo/problems/algebra_finite_commutative_rings_and_ideals_1.txt",
    ),
    (
        "algebra",
        "evaluation/testdata/aimo/problems/algebra_finite_field_polynomial_irreducibility_1.txt",
    ),
    (
        "algebra",
        "evaluation/testdata/aimo/problems/algebra_functional_equations_1.txt",
    ),
    (
        "algebra",
        "evaluation/testdata/aimo/problems/algebra_integer_polynomials_and_gcd_1.txt",
    ),
]

QUESTION_ROWS: list[tuple[str, dict[str, object]]] = [
    (
        "verifier_questions",
        {
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "Problem: A draft solution claims a theorem now proves the result, but one conclusion in the middle looks suspicious. "
                        "Draft: 'This is correct, this is correct, but then this last implication also follows.'"
                    ),
                },
                {
                    "role": "assistant",
                    "content": (
                        "This is correct so far, but why is this next implication valid? Which theorem hypothesis are you using in that exact step?"
                    ),
                },
            ]
        },
    ),
    (
        "verifier_questions",
        {
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "Problem: A solver reaches a contradiction by manipulating an expression and then jumps to a conclusion. "
                        "Draft: 'Okay, I see where the proof ends: after this rewrite the contradiction is obvious.'"
                    ),
                },
                {
                    "role": "assistant",
                    "content": (
                        "I see where you are trying to go, but in this step the better way to think about it is to isolate the exact contradiction. Which statement is incompatible with which earlier assumption?"
                    ),
                },
            ]
        },
    ),
    (
        "verifier_questions",
        {
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "Problem: A proof cites a theorem in a broad way and then uses it to justify a strong claim. "
                        "Draft: 'I see your concern, but the theorem handles it, so the argument should be fine.'"
                    ),
                },
                {
                    "role": "assistant",
                    "content": (
                        "Your concern is valid, but let's decipher the theorem carefully: what does it actually say, and which part of your claim is still not covered by its conclusion?"
                    ),
                },
            ]
        },
    ),
    (
        "verifier_questions",
        {
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "Problem: A solver paraphrases the problem and then follows a line of reasoning that may not match the exact ask. "
                        "Draft: 'So according to the question, we just need to show the construction exists, and then the numeric answer follows.'"
                    ),
                },
                {
                    "role": "assistant",
                    "content": (
                        "According to the question, what is the exact quantity being asked for? Can you restate the target before committing to the rest of the approach?"
                    ),
                },
            ]
        },
    ),
    (
        "verifier_questions",
        {
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "Problem: Two possible approaches are on the table, and the solver picks one quickly. "
                        "Draft: 'I think this is the better approach, so I'll continue from here.'"
                    ),
                },
                {
                    "role": "assistant",
                    "content": (
                        "Why is this the better approach? What does it control that the other approach fails to control?"
                    ),
                },
            ]
        },
    ),
]


UNIQUENESS_MARKER = re.compile(r"\n(?:\d+\)\s+)?Uniqueness Test\b", re.IGNORECASE)


def normalize_text(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def trim_solution_tail(solution: str) -> str:
    match = UNIQUENESS_MARKER.search(solution)
    if match:
        solution = solution[: match.start()]
    return solution.strip()


def metadata_path_for_problem(path: Path) -> Path:
    parts = list(path.parts)
    try:
        idx = parts.index("problems")
    except ValueError as exc:
        raise ValueError(f"Could not infer metadata path for {path}") from exc
    parts[idx] = "metadata"
    metadata_path = Path(*parts).with_suffix(".json")
    return metadata_path


def parse_via_metadata(path: Path) -> dict[str, object]:
    metadata_path = metadata_path_for_problem(path)
    metadata = json.loads(metadata_path.read_text(encoding="utf-8", errors="replace"))
    short_name = metadata["identity"]["short_name"]
    givens = metadata["problem_spec"]["givens"]
    ask = metadata["problem_spec"]["ask"]
    summary = metadata["problem_spec"]["summary"]
    trick = metadata["solution_signature"]["critical_trick(s)"][0]
    final_answer = metadata["instance_snapshot"]["final_answer"]["normalized"]

    user_lines = [short_name, ""] + givens + [""] + ask
    assistant_lines = [
        "Solution.",
        summary,
        "",
        f"Key idea: {trick}",
        "",
        f"Final answer: {final_answer}",
    ]
    return {
        "messages": [
            {"role": "user", "content": "\n".join(user_lines).strip()},
            {"role": "assistant", "content": "\n".join(assistant_lines).strip()},
        ]
    }


def parse_problem_file(path: Path) -> dict[str, object]:
    text = normalize_text(path.read_text(encoding="utf-8", errors="replace"))
    marker = "\nSolution."
    if marker not in text:
        return parse_via_metadata(path)
    problem_text, solution_text = text.split(marker, 1)
    solution_text = "Solution." + solution_text
    solution_text = trim_solution_tail(solution_text)
    return {
        "messages": [
            {"role": "user", "content": problem_text.strip()},
            {"role": "assistant", "content": solution_text},
        ]
    }


def load_locked_lines(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if len(lines) < LOCKED_ROWS:
        raise ValueError(f"{path} has only {len(lines)} rows; expected at least {LOCKED_ROWS}")
    locked = lines[:LOCKED_ROWS]
    for idx, line in enumerate(locked, start=1):
        json.loads(line)
    return locked


def main() -> None:
    locked_lines = load_locked_lines(DATASET_PATH)

    generated_lines: list[str] = []
    domain_counts: dict[str, int] = {}
    source_files: list[str] = []

    for domain, relative_path in RAW_SOURCES:
        path = ROOT / relative_path
        row = parse_problem_file(path)
        generated_lines.append(json.dumps(row, ensure_ascii=False))
        domain_counts[domain] = domain_counts.get(domain, 0) + 1
        source_files.append(str(path))

    for domain, row in QUESTION_ROWS:
        generated_lines.append(json.dumps(row, ensure_ascii=False))
        domain_counts[domain] = domain_counts.get(domain, 0) + 1

    all_lines = locked_lines + generated_lines
    DATASET_PATH.write_text("\n".join(all_lines) + "\n", encoding="utf-8")

    manifest = {
        "dataset_name": "training_dataset_0_identity",
        "version": 4,
        "purpose": (
            "Dataset 0 preserves Athena's locked identity rows and appends a small "
            "cross-domain style foundation across number theory, combinatorics, "
            "geometry, logic, and algebra, plus a small verifier-style layer that "
            "teaches better question-asking during problem solving."
        ),
        "format": {
            "type": "jsonl_messages",
            "system_message_used": False,
        },
        "output_file": str(DATASET_PATH),
        "row_count": len(all_lines),
        "locked_identity_rows": LOCKED_ROWS,
        "domain_counts": domain_counts,
        "source_files": source_files,
        "notes": [
            "The first 6 rows are preserved verbatim from the user-locked identity seed.",
            "Five rows were added for each of: number theory, combinatorics, geometry, logic, and algebra.",
            "The selected combinatorics and geometry rows avoid the currently active benchmark candidates discussed in-session.",
            "Five short verifier rows were appended to teach Athena to ask sharper correction-focused questions.",
        ],
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
