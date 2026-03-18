#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from athena_paths import (  # noqa: E402
    get_orchestrator_manifest_path,
    get_orchestrator_model_dir,
    get_orchestrator_scenario_cards_path,
    get_orchestrator_seed_path,
    get_orchestrator_v1_dir,
    get_solver_a_seed_path,
    get_solver_b_seed_path,
)


ROLE_PROMPTS = {
    "orchestrator": (
        "You are the Orchestrator. You route math and logic problems with rigor and budget discipline.\n"
        "Return exactly one action per turn. Allowed assistant outputs are only:\n"
        '<query target="solver_a">...</query>\n'
        '<query target="solver_b">...</query>\n'
        '<query target="both">solver_a: ...\\nsolver_b: ...</query>\n'
        "<clarify>...</clarify>\n"
        "<answer>...</answer>\n"
        "Answer directly only when the request is reliable from first principles. Ask one focused clarification when the request is underspecified. Query selectively. Do not reveal hidden reasoning or role-blend."
    ),
    "solver_a": (
        "You are Solver-A. You are a direct formal solver for math and logic.\n"
        "Work from first principles, stay concise, and return only this envelope:\n"
        "<answer>...</answer>\n"
        "<confidence>high|medium|low</confidence>\n"
        "Never emit query tags."
    ),
    "solver_b": (
        "You are Solver-B. You independently check math and logic problems for alternate paths and edge cases.\n"
        "Stay compact and return only this envelope:\n"
        "<answer>...</answer>\n"
        "<confidence>high|medium|low</confidence>\n"
        "Never emit query tags."
    ),
}

RECOMMENDED_ROUTINGS = {
    "direct_answer",
    "query_solver_a",
    "query_solver_b",
    "query_both",
    "clarify",
    "disagreement_synthesis",
}
DOMAINS = {"math", "logic"}
DIFFICULTIES = {"easy", "medium", "hard"}
EXPECTED_ROUTE_COUNTS = {
    "direct_answer": 12,
    "query_solver_a": 12,
    "query_solver_b": 12,
    "query_both": 15,
    "clarify": 6,
    "disagreement_synthesis": 3,
}
EXPECTED_DOMAIN_COUNTS = {"math": 42, "logic": 18}
EXPECTED_DATASET_COUNTS = {"orchestrator": 120, "solver_a": 60, "solver_b": 60}


class BlockStyleDumper(yaml.SafeDumper):
    pass


def _represent_str(dumper: yaml.SafeDumper, data: str) -> yaml.nodes.ScalarNode:
    style = "|" if "\n" in data else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style=style)


BlockStyleDumper.add_representer(str, _represent_str)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bootstrap, compile, and validate the Orchestrator Dataset V1 package.")
    parser.add_argument("--bootstrap", action="store_true", help="Write the initial canonical scenario_cards.yaml package.")
    parser.add_argument("--overwrite-bootstrap", action="store_true", help="Allow bootstrap to overwrite an existing scenario_cards.yaml.")
    parser.add_argument("--write", action="store_true", help="Write the compiled JSONL datasets and manifest.")
    parser.add_argument("--validate", action="store_true", help="Run schema and role-purity validation.")
    parser.add_argument("--token-stats", action="store_true", help="Run token-length stats with the tokenizer chat template.")
    parser.add_argument("--max-seq-length", type=int, default=2048)
    parser.add_argument("--model-name-or-path", default=str(get_orchestrator_model_dir()))
    return parser.parse_args()


def render_solver_answer(answer: str, confidence: str) -> str:
    return f"<answer>{answer}</answer>\n<confidence>{confidence}</confidence>"


def make_card(
    card_id: str,
    domain: str,
    difficulty: str,
    route: str,
    problem: str,
    gold_answer: str,
    *,
    ambiguity_flag: bool = False,
    clarification_prompt: str = "",
    solver_a_draft: str = "",
    solver_b_draft: str = "",
    disagreement_notes: str = "",
    final_orchestration_action: str = "",
) -> dict[str, Any]:
    if not final_orchestration_action:
        final_orchestration_action = (
            f"<clarify>{clarification_prompt}</clarify>" if ambiguity_flag else f"<answer>{gold_answer}</answer>"
        )
    confidence = "high" if difficulty == "easy" else "medium"
    if not solver_a_draft:
        solver_a_draft = render_solver_answer(
            gold_answer if not ambiguity_flag else f"Insufficient information: {clarification_prompt}",
            confidence,
        )
    if not solver_b_draft:
        solver_b_draft = render_solver_answer(
            gold_answer if not ambiguity_flag else f"Insufficient information: {clarification_prompt}",
            confidence,
        )
    return {
        "id": card_id,
        "domain": domain,
        "difficulty": difficulty,
        "problem": problem,
        "gold_answer": gold_answer,
        "ambiguity_flag": ambiguity_flag,
        "recommended_routing": route,
        "solver_a_draft": solver_a_draft,
        "solver_b_draft": solver_b_draft,
        "disagreement_notes": disagreement_notes,
        "clarification_prompt": clarification_prompt,
        "final_orchestration_action": final_orchestration_action,
    }


def bootstrap_package() -> dict[str, Any]:
    cards: list[dict[str, Any]] = []

    def add_many(prefix: str, domain: str, difficulty: str, route: str, rows: list[tuple[str, str]], *, ambiguity: bool = False, clarifications: list[str] | None = None) -> None:
        for index, (problem, gold_answer) in enumerate(rows, start=1):
            clarification_prompt = clarifications[index - 1] if clarifications else ""
            cards.append(
                make_card(
                    f"{prefix}_{index:02d}",
                    domain,
                    difficulty,
                    route,
                    problem,
                    gold_answer,
                    ambiguity_flag=ambiguity,
                    clarification_prompt=clarification_prompt,
                )
            )

    add_many(
        "math_direct",
        "math",
        "easy",
        "direct_answer",
        [
            ("Compute 17 * 19 exactly.", "323"),
            ("Simplify 2^5 * 2^3.", "256"),
            ("Solve 3x + 5 = 20.", "x = 5"),
            ("A rectangle has length 12 and width 7. What is its area?", "84"),
            ("Convert 0.375 to a reduced fraction.", "3/8"),
            ("Find gcd(84, 126).", "42"),
            ("Evaluate (6^2 - 4^2) / (6 - 4).", "10"),
            ("Factor x^2 - 9 over the integers.", "(x - 3)(x + 3)"),
        ],
    )
    add_many(
        "logic_direct",
        "logic",
        "easy",
        "direct_answer",
        [
            ("If every square is a rectangle, does it follow that every rectangle is a square?", "No."),
            ("Exactly one of P or Q is true. If P is true, is Q true?", "No."),
            ("If every rose is a flower and every flower is a plant, is every rose a plant?", "Yes."),
            ('Statement A is "P or Q". If P is true, must A be true?', "Yes."),
        ],
    )
    add_many(
        "math_solver_a",
        "math",
        "medium",
        "query_solver_a",
        [
            ("Find the sum of the first 20 positive integers.", "210"),
            ("Solve 2x^2 - 7x + 3 = 0.", "x = 3 or x = 1/2"),
            ("The arithmetic sequence is 5, 9, 13, ... . Find the 25th term.", "101"),
            ("Find the determinant of [[3, 5], [1, 4]].", "7"),
            ("How many positive divisors does 72 have?", "12"),
            ("What is the probability of getting exactly 2 heads in 3 fair coin flips?", "3/8"),
            ("Solve the system x + y = 11 and x - y = 3.", "x = 7, y = 4"),
            ("Simplify (3/4) / (9/10).", "5/6"),
            ("Find the mean of 4, 7, 9, 10, 20.", "10"),
        ],
    )
    add_many(
        "logic_solver_a",
        "logic",
        "medium",
        "query_solver_a",
        [
            ("Exactly one of A, B, and C is true. A is false, and B implies C. Which variable is true?", "C is true."),
            ("If P implies Q, Q implies R, and P is true, is R true?", "Yes."),
            ('Ada says "Ben is a knave." Ben says "Ada and I are opposite types." Who is the knight?', "Ben is the knight and Ada is the knave."),
        ],
    )
    add_many(
        "math_solver_b",
        "math",
        "medium",
        "query_solver_b",
        [
            ("Is 111111 divisible by 3?", "Yes."),
            ("How many diagonals does a 12-gon have?", "54"),
            ("Find 15^2 - 14^2.", "29"),
            ("Which is larger: 7/12 or 5/8?", "5/8 is larger."),
            ("Find the remainder when 2^10 is divided by 7.", "2"),
            ("Find the perimeter of a 6-8-10 triangle.", "24"),
            ("How many permutations are there of the letters A, B, C, and D?", "24"),
            ("Solve 2x - 3 > 7.", "x > 5"),
            ("Find the median of 2, 8, 3, 10, 9.", "8"),
        ],
    )
    add_many(
        "logic_solver_b",
        "logic",
        "medium",
        "query_solver_b",
        [
            ("Some A are B. No B are C. Can some A be C?", "Yes. Some A outside B could still be C."),
            ("If no poets are dull and some teachers are dull, can some teachers be poets?", "No."),
            ('If the statement "At least one of P or Q is false" is false, what follows?', "P and Q are both true."),
        ],
    )
    add_many(
        "math_both",
        "math",
        "medium",
        "query_both",
        [
            ("Compute 13^2 + 14^2.", "365"),
            ("Solve x^2 - 5x + 6 = 0.", "x = 2 or x = 3"),
            ("Evaluate 1/2 + 1/3 + 1/6.", "1"),
            ("Find the area of a circle with radius 5.", "25pi"),
            ("Find the sum of the interior angles of a hexagon.", "720 degrees"),
            ("Simplify (x^3 y^2) / (x y^5).", "x^2 / y^3"),
            ("What is the probability of drawing an ace from a standard 52-card deck?", "1/13"),
            ("Find lcm(18, 24).", "72"),
            ("If f(x) = 2x + 1, find f(7).", "15"),
            ("A bag has 3 red and 2 blue marbles. What is the probability of drawing a red marble and then a blue marble without replacement?", "3/10"),
        ],
    )
    add_many(
        "logic_both",
        "logic",
        "medium",
        "query_both",
        [
            ("If the server is down, the portal is unavailable. The portal is available. Can the server be down?", "No."),
            ("All marbles in box X are blue. Some blue objects are glass. Can you conclude that some marbles in box X are glass?", "No."),
            ("Nora is older than Omar, and Omar is older than Priya. Who is youngest?", "Priya."),
            ("If a card is a king, then it is a face card. This card is not a face card. Can it be a king?", "No."),
            ('A statement says "Both P and Q." If the statement is true and P is true, what must be true about Q?', "Q is true."),
        ],
    )
    add_many(
        "math_clarify",
        "math",
        "easy",
        "clarify",
        [
            ("Solve a x = 12 for x.", "Need the value of nonzero a."),
            ("Find the area of a triangle with base 10.", "Need the height of the triangle."),
            ("Find the average of the list.", "Need the list values or an equivalent summary."),
        ],
        ambiguity=True,
        clarifications=[
            "What is the value of a? It must be nonzero to solve for x.",
            "What is the triangle's height?",
            "What numbers are in the list?",
        ],
    )
    add_many(
        "logic_clarify",
        "logic",
        "easy",
        "clarify",
        [
            ("Three suspects made statements and exactly one lied. Who took the key?", "Need the suspects' statements."),
            ("Mia finished before Noah. Who won the race?", "Need more ordering information than one comparison."),
            ("Decide whether the argument is valid.", "Need the premises and the conclusion."),
        ],
        ambiguity=True,
        clarifications=[
            "What did each suspect say?",
            "What other race results or comparisons are known?",
            "What are the premises and what is the conclusion?",
        ],
    )
    cards.extend(
        [
            make_card(
                "math_disagreement_01",
                "math",
                "hard",
                "disagreement_synthesis",
                "Solve |x - 3| = 5.",
                "x = 8 or x = -2",
                solver_a_draft=render_solver_answer("x = 8 or x = -2", "high"),
                solver_b_draft=render_solver_answer("x = 8", "medium"),
                disagreement_notes="Solver B dropped the negative branch of the absolute value equation.",
                final_orchestration_action="<answer>The solutions are x = 8 and x = -2.</answer>",
            ),
            make_card(
                "math_disagreement_02",
                "math",
                "hard",
                "disagreement_synthesis",
                "How many real solutions does x^2 = 9 have?",
                "2 real solutions: x = 3 and x = -3",
                solver_a_draft=render_solver_answer("2 real solutions: x = 3 and x = -3", "high"),
                solver_b_draft=render_solver_answer("1 real solution: x = 3", "medium"),
                disagreement_notes="Solver B kept only the positive square root.",
                final_orchestration_action="<answer>There are 2 real solutions: x = 3 and x = -3.</answer>",
            ),
            make_card(
                "math_disagreement_03",
                "math",
                "hard",
                "disagreement_synthesis",
                "Evaluate 2^3^2 using standard exponent precedence.",
                "512",
                solver_a_draft=render_solver_answer("512", "high"),
                solver_b_draft=render_solver_answer("64", "medium"),
                disagreement_notes="Exponentiation is evaluated from the top exponent first: 2^(3^2), not (2^3)^2.",
                final_orchestration_action="<answer>512</answer>",
            ),
        ]
    )

    return {
        "version": 1,
        "name": "orchestrator_dataset_v1",
        "description": "Minimal role-pure math and logic orchestration seed set for selective two-solver querying.",
        "role_prompts": ROLE_PROMPTS,
        "target_counts": {
            "cards": 60,
            "orchestrator_rows": 120,
            "solver_a_rows": 60,
            "solver_b_rows": 60,
        },
        "cards": cards,
    }


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    ensure_parent(path)
    path.write_text(yaml.dump(payload, Dumper=BlockStyleDumper, sort_keys=False, allow_unicode=False, width=1000), encoding="utf-8")


def load_yaml(path: Path) -> dict[str, Any]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Expected mapping at top level: {path}")
    return raw


def detect_orchestrator_tag(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith('<query target="solver_a">') and stripped.endswith("</query>"):
        return "query_solver_a"
    if stripped.startswith('<query target="solver_b">') and stripped.endswith("</query>"):
        return "query_solver_b"
    if stripped.startswith('<query target="both">') and stripped.endswith("</query>"):
        return "query_both"
    if stripped.startswith("<clarify>") and stripped.endswith("</clarify>"):
        return "clarify"
    if stripped.startswith("<answer>") and stripped.endswith("</answer>"):
        return "answer"
    return ""


def validate_card(card: dict[str, Any]) -> None:
    required = {
        "id",
        "domain",
        "difficulty",
        "problem",
        "gold_answer",
        "ambiguity_flag",
        "recommended_routing",
        "solver_a_draft",
        "solver_b_draft",
        "disagreement_notes",
        "clarification_prompt",
        "final_orchestration_action",
    }
    missing = sorted(required.difference(card))
    if missing:
        raise ValueError(f"Card {card.get('id', '<unknown>')} is missing fields: {missing}")
    if card["domain"] not in DOMAINS:
        raise ValueError(f"Card {card['id']} has invalid domain: {card['domain']}")
    if card["difficulty"] not in DIFFICULTIES:
        raise ValueError(f"Card {card['id']} has invalid difficulty: {card['difficulty']}")
    if card["recommended_routing"] not in RECOMMENDED_ROUTINGS:
        raise ValueError(f"Card {card['id']} has invalid route: {card['recommended_routing']}")
    if not str(card["problem"]).strip():
        raise ValueError(f"Card {card['id']} has empty problem")
    if not str(card["gold_answer"]).strip():
        raise ValueError(f"Card {card['id']} has empty gold_answer")
    if card["recommended_routing"] == "clarify":
        if not bool(card["ambiguity_flag"]):
            raise ValueError(f"Card {card['id']} must set ambiguity_flag for clarify route")
        if not str(card["clarification_prompt"]).strip():
            raise ValueError(f"Card {card['id']} needs clarification_prompt")
    if not detect_orchestrator_tag(str(card["final_orchestration_action"])):
        raise ValueError(f"Card {card['id']} has invalid final_orchestration_action tag")


def solver_user_message(card: dict[str, Any], role_name: str) -> str:
    role_line = "Solve from first principles." if role_name == "solver_a" else "Independently check for alternate paths or edge cases."
    return (
        f"{role_line}\n"
        "Return only <answer> and <confidence>.\n"
        f"Domain: {card['domain']}\n"
        f"Problem: {card['problem']}"
    )


def solver_target(card: dict[str, Any], role_name: str) -> str:
    if card["recommended_routing"] == "clarify":
        answer = f"Insufficient information: {card['clarification_prompt']}"
        confidence = "high"
    else:
        answer = str(card["gold_answer"]).strip()
        confidence = "high" if card["difficulty"] == "easy" else "medium"
        if role_name == "solver_b" and card["recommended_routing"] in {"query_both", "disagreement_synthesis"}:
            confidence = "medium"
    return render_solver_answer(answer, confidence)


def orchestrator_initial_action(card: dict[str, Any]) -> str:
    route = card["recommended_routing"]
    problem = str(card["problem"]).strip()
    domain = str(card["domain"]).strip()
    if route == "direct_answer":
        return f"<answer>{card['gold_answer']}</answer>"
    if route == "clarify":
        return f"<clarify>{card['clarification_prompt']}</clarify>"
    if route == "query_solver_a":
        return (
            '<query target="solver_a">'
            f"Solve this {domain} problem from first principles and return only <answer> and <confidence>. "
            f"Problem: {problem}"
            "</query>"
        )
    if route == "query_solver_b":
        return (
            '<query target="solver_b">'
            f"Independently check this {domain} problem for alternate paths or edge cases and return only <answer> and <confidence>. "
            f"Problem: {problem}"
            "</query>"
        )
    if route in {"query_both", "disagreement_synthesis"}:
        return (
            '<query target="both">'
            f"solver_a: Solve this {domain} problem from first principles and return only <answer> and <confidence>.\n"
            f"solver_b: Independently check this {domain} problem for alternate paths or edge cases and return only <answer> and <confidence>.\n"
            f"Problem: {problem}"
            "</query>"
        )
    raise ValueError(f"Unknown route: {route}")


def orchestrator_follow_up_user(card: dict[str, Any]) -> str:
    route = card["recommended_routing"]
    if route == "direct_answer":
        return (
            "External solver budget is zero for this turn. If the problem is reliable from first principles, respond directly.\n"
            f"Problem: {card['problem']}"
        )
    if route == "clarify":
        return (
            "If essential information is missing, ask exactly one focused clarification and do not guess.\n"
            f"Problem: {card['problem']}"
        )
    evidence_lines = [
        "External solver evidence is now available.",
        "solver_a:",
        str(card["solver_a_draft"]).strip(),
        "",
        "solver_b:",
        str(card["solver_b_draft"]).strip(),
    ]
    if str(card["disagreement_notes"]).strip():
        evidence_lines.extend(["", f"Disagreement notes: {card['disagreement_notes']}"])
    evidence_lines.append("")
    evidence_lines.append("Choose the final user-facing answer now.")
    return "\n".join(evidence_lines)


def compile_datasets(package: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    cards = package["cards"]
    role_prompts = package["role_prompts"]
    orchestrator_rows: list[dict[str, Any]] = []
    solver_a_rows: list[dict[str, Any]] = []
    solver_b_rows: list[dict[str, Any]] = []
    route_counts = Counter()
    domain_counts = Counter()

    for card in cards:
        validate_card(card)
        route_counts[card["recommended_routing"]] += 1
        domain_counts[card["domain"]] += 1

        first_action = orchestrator_initial_action(card)
        orchestrator_rows.append(
            {
                "sample_id": f"{card['id']}_step_1",
                "card_id": card["id"],
                "dataset_role": "orchestrator",
                "domain": card["domain"],
                "route": card["recommended_routing"],
                "messages": [
                    {"role": "system", "content": role_prompts["orchestrator"]},
                    {"role": "user", "content": str(card["problem"]).strip()},
                    {"role": "assistant", "content": first_action},
                ],
            }
        )
        orchestrator_rows.append(
            {
                "sample_id": f"{card['id']}_step_2",
                "card_id": card["id"],
                "dataset_role": "orchestrator",
                "domain": card["domain"],
                "route": card["recommended_routing"],
                "messages": [
                    {"role": "system", "content": role_prompts["orchestrator"]},
                    {"role": "user", "content": str(card["problem"]).strip()},
                    {"role": "assistant", "content": first_action},
                    {"role": "user", "content": orchestrator_follow_up_user(card)},
                    {"role": "assistant", "content": str(card["final_orchestration_action"]).strip()},
                ],
            }
        )
        solver_a_rows.append(
            {
                "sample_id": f"{card['id']}_solver_a",
                "card_id": card["id"],
                "dataset_role": "solver_a",
                "domain": card["domain"],
                "route": card["recommended_routing"],
                "messages": [
                    {"role": "system", "content": role_prompts["solver_a"]},
                    {"role": "user", "content": solver_user_message(card, "solver_a")},
                    {"role": "assistant", "content": solver_target(card, "solver_a")},
                ],
            }
        )
        solver_b_rows.append(
            {
                "sample_id": f"{card['id']}_solver_b",
                "card_id": card["id"],
                "dataset_role": "solver_b",
                "domain": card["domain"],
                "route": card["recommended_routing"],
                "messages": [
                    {"role": "system", "content": role_prompts["solver_b"]},
                    {"role": "user", "content": solver_user_message(card, "solver_b")},
                    {"role": "assistant", "content": solver_target(card, "solver_b")},
                ],
            }
        )

    manifest = {
        "version": 1,
        "name": package["name"],
        "description": package["description"],
        "source_file": get_orchestrator_scenario_cards_path().name,
        "counts": {
            "cards": len(cards),
            "orchestrator_rows": len(orchestrator_rows),
            "solver_a_rows": len(solver_a_rows),
            "solver_b_rows": len(solver_b_rows),
        },
        "route_counts": dict(sorted(route_counts.items())),
        "domain_counts": dict(sorted(domain_counts.items())),
        "role_prompts": role_prompts,
        "files": {
            "orchestrator_seed": get_orchestrator_seed_path().name,
            "solver_a_seed": get_solver_a_seed_path().name,
            "solver_b_seed": get_solver_b_seed_path().name,
        },
        "token_stats": {},
    }
    return orchestrator_rows, solver_a_rows, solver_b_rows, manifest


def validate_messages(rows: list[dict[str, Any]], dataset_role: str) -> None:
    for row in rows:
        messages = row.get("messages")
        if not isinstance(messages, list) or not messages:
            raise ValueError(f"{dataset_role}: row {row.get('sample_id')} has invalid messages")
        roles = [message.get("role") for message in messages]
        if roles[0] != "system":
            raise ValueError(f"{dataset_role}: row {row.get('sample_id')} must start with system")
        if roles[-1] != "assistant":
            raise ValueError(f"{dataset_role}: row {row.get('sample_id')} must end with assistant")
        for message in messages:
            if message.get("role") not in {"system", "user", "assistant"}:
                raise ValueError(f"{dataset_role}: row {row.get('sample_id')} has invalid role {message.get('role')}")
            if not str(message.get("content") or "").strip():
                raise ValueError(f"{dataset_role}: row {row.get('sample_id')} has empty content")
        assistant = str(messages[-1]["content"]).strip()
        if dataset_role == "orchestrator":
            if not detect_orchestrator_tag(assistant):
                raise ValueError(f"orchestrator: row {row['sample_id']} has invalid assistant tag")
        else:
            if "<query target=" in assistant:
                raise ValueError(f"{dataset_role}: row {row['sample_id']} must not emit query tags")
            if not re.fullmatch(r"<answer>.*</answer>\s*<confidence>(high|medium|low)</confidence>", assistant, flags=re.S):
                raise ValueError(f"{dataset_role}: row {row['sample_id']} has invalid answer envelope")


def validate_package(package: dict[str, Any], orchestrator_rows: list[dict[str, Any]], solver_a_rows: list[dict[str, Any]], solver_b_rows: list[dict[str, Any]], manifest: dict[str, Any]) -> None:
    cards = package.get("cards")
    if not isinstance(cards, list) or not cards:
        raise ValueError("scenario_cards.yaml must contain a non-empty cards list")
    if package.get("role_prompts") != ROLE_PROMPTS:
        raise ValueError("role_prompts diverged from the canonical prompts in the build script")
    if len({ROLE_PROMPTS["orchestrator"], ROLE_PROMPTS["solver_a"], ROLE_PROMPTS["solver_b"]}) != 3:
        raise ValueError("role prompts must be distinct")
    route_counts = Counter(card["recommended_routing"] for card in cards)
    domain_counts = Counter(card["domain"] for card in cards)
    if dict(route_counts) != EXPECTED_ROUTE_COUNTS:
        raise ValueError(f"Route counts mismatch: expected {EXPECTED_ROUTE_COUNTS}, got {dict(route_counts)}")
    if dict(domain_counts) != EXPECTED_DOMAIN_COUNTS:
        raise ValueError(f"Domain counts mismatch: expected {EXPECTED_DOMAIN_COUNTS}, got {dict(domain_counts)}")
    if len(orchestrator_rows) != EXPECTED_DATASET_COUNTS["orchestrator"]:
        raise ValueError("Orchestrator row count mismatch")
    if len(solver_a_rows) != EXPECTED_DATASET_COUNTS["solver_a"]:
        raise ValueError("Solver-A row count mismatch")
    if len(solver_b_rows) != EXPECTED_DATASET_COUNTS["solver_b"]:
        raise ValueError("Solver-B row count mismatch")
    validate_messages(orchestrator_rows, "orchestrator")
    validate_messages(solver_a_rows, "solver_a")
    validate_messages(solver_b_rows, "solver_b")
    manifest_counts = manifest.get("counts", {})
    for key, expected in {
        "cards": len(cards),
        "orchestrator_rows": len(orchestrator_rows),
        "solver_a_rows": len(solver_a_rows),
        "solver_b_rows": len(solver_b_rows),
    }.items():
        if manifest_counts.get(key) != expected:
            raise ValueError(f"Manifest count mismatch for {key}: {manifest_counts.get(key)} != {expected}")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    ensure_parent(path)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    ensure_parent(path)
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def compute_token_stats(model_name_or_path: str, max_seq_length: int, manifest: dict[str, Any]) -> None:
    from transformers import AutoTokenizer
    from train import ChatDataset, print_length_stats, token_lengths

    tokenizer = AutoTokenizer.from_pretrained(model_name_or_path, use_fast=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token if tokenizer.eos_token is not None else "<|pad|>"
    stats: dict[str, Any] = {}
    for label, path in {
        "orchestrator": get_orchestrator_seed_path(),
        "solver_a": get_solver_a_seed_path(),
        "solver_b": get_solver_b_seed_path(),
    }.items():
        dataset = ChatDataset(str(path))
        lengths = token_lengths(tokenizer, dataset.samples)
        over_limit = print_length_stats(lengths, max_seq_length)
        p95_index = int(0.95 * (len(lengths) - 1))
        stats[label] = {
            "samples": len(lengths),
            "min": lengths[0],
            "p95": lengths[p95_index],
            "max": lengths[-1],
            "over_limit": over_limit,
            "max_seq_length": max_seq_length,
            "model_name_or_path": model_name_or_path,
        }
    manifest["token_stats"] = stats


def main() -> None:
    args = parse_args()
    scenario_path = get_orchestrator_scenario_cards_path()
    package_dir = get_orchestrator_v1_dir()
    package_dir.mkdir(parents=True, exist_ok=True)
    if args.bootstrap:
        if scenario_path.exists() and not args.overwrite_bootstrap:
            raise FileExistsError(f"{scenario_path} already exists. Use --overwrite-bootstrap to replace it.")
        write_yaml(scenario_path, bootstrap_package())
    if not scenario_path.exists():
        raise FileNotFoundError(f"Missing canonical scenario source: {scenario_path}")
    package = load_yaml(scenario_path)
    orchestrator_rows, solver_a_rows, solver_b_rows, manifest = compile_datasets(package)
    if args.write:
        write_jsonl(get_orchestrator_seed_path(), orchestrator_rows)
        write_jsonl(get_solver_a_seed_path(), solver_a_rows)
        write_jsonl(get_solver_b_seed_path(), solver_b_rows)
    if args.validate:
        validate_package(package, orchestrator_rows, solver_a_rows, solver_b_rows, manifest)
    if args.token_stats:
        if not args.write:
            write_jsonl(get_orchestrator_seed_path(), orchestrator_rows)
            write_jsonl(get_solver_a_seed_path(), solver_a_rows)
            write_jsonl(get_solver_b_seed_path(), solver_b_rows)
        compute_token_stats(args.model_name_or_path, args.max_seq_length, manifest)
    if args.write:
        write_manifest(get_orchestrator_manifest_path(), manifest)
    print(
        f"Built orchestrator package at {package_dir} | "
        f"cards={manifest['counts']['cards']} orchestrator={manifest['counts']['orchestrator_rows']} "
        f"solver_a={manifest['counts']['solver_a_rows']} solver_b={manifest['counts']['solver_b_rows']}"
    )


if __name__ == "__main__":
    main()
