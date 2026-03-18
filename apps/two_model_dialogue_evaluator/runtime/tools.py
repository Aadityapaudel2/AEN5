from __future__ import annotations

import ast
import json
import re
import textwrap
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from paths import get_tool_behavior_primer_path

TOOL_NAME_CALCULATOR = "calculator"

TOOL_CALL_RE = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.IGNORECASE | re.DOTALL)
ARITHMETIC_RE = re.compile(r"^[\d\s+\-*/%().,^]+$")
ARITHMETIC_CHUNK_RE = re.compile(r"[\d\s+\-*/%().,^]{6,}")
LONG_INTEGER_RE = re.compile(r"\d{8,}")
COMPUTE_HINT_RE = re.compile(r"\b(exact|exactly|compute|calculate|evaluate|verify|calculator)\b", re.IGNORECASE)

TOOL_APPENDIX = textwrap.dedent(
    """
    Tool mode is enabled for this turn.

    You have calculator access.

    If exact arithmetic would help, output only this block:
    <tool_call>
    {"tool":"calculator","expression":"(2 + 2) * 5"}
    </tool_call>

    Do not include prose in the same message as a tool call.
    After a tool result is returned, answer normally.
    """
).strip()

DEFAULT_BEHAVIOR_PRIMER = textwrap.dedent(
    """
    Tool behavior primer:

    Example 1
    User: Compute 987654321987654321 + 123456789123456789 exactly.
    Assistant: I will verify the exact sum with the calculator.
    Assistant: <tool_call>{"tool":"calculator","expression":"987654321987654321 + 123456789123456789"}</tool_call>
    Tool result: result = 1111111111111111110
    Assistant: The exact value is \(1111111111111111110\).

    Example 2
    User: Evaluate 28989898989/224/2989898*(2+333).
    Assistant: I will verify the arithmetic with the calculator.
    Assistant: <tool_call>{"tool":"calculator","expression":"28989898989/224/2989898*(2+333)"}</tool_call>
    Tool result: result = 14500.638246383262
    Assistant: The value is \(14500.638246383262\).

    Example 3
    User: Verify that (12345678901234567890 mod 97) * 13 is correct.
    Assistant: I will check it with the calculator.
    Assistant: <tool_call>{"tool":"calculator","expression":"(12345678901234567890 % 97) * 13"}</tool_call>
    Tool result: result = 247
    Assistant: The verified value is \(247\).

    Example 4
    User: Compute 8^12 - 29^5 + 17 exactly.
    Assistant: I will use the calculator for the exact value.
    Assistant: <tool_call>{"tool":"calculator","expression":"8**12 - 29**5 + 17"}</tool_call>
    Tool result: result = 68698965604
    Assistant: The exact value is \(68698965604\).

    Example 5
    User: If arithmetic is long or exactness matters, what should you do?
    Assistant: Briefly say that you will verify it with the calculator, emit the calculator tool call, and then answer from the tool result.
    """
).strip()


@dataclass(frozen=True)
class ToolCall:
    tool: str
    expression: str
    raw: str


@dataclass(frozen=True)
class ToolResult:
    tool: str
    ok: bool
    expression: str
    stdout: str
    stderr: str
    result_text: str
    duration_ms: int


def append_tool_protocol(system_prompt: str) -> str:
    base = (system_prompt or "").strip()
    appendix = TOOL_APPENDIX
    primer = load_tool_behavior_primer()
    if primer:
        appendix = f"{appendix}\n\n{primer}"
    if not base:
        return appendix
    if TOOL_APPENDIX in base or '"tool":"calculator"' in base or '"tool":"python"' in base:
        return base
    return f"{base}\n\n{appendix}"


def is_tool_candidate(text: str) -> bool:
    expression = _normalize_expression(text)
    if expression and ARITHMETIC_RE.fullmatch(expression) and _has_operator(expression):
        return _is_safe_expression(expression)
    raw = (text or "").strip()
    return bool(COMPUTE_HINT_RE.search(raw) and LONG_INTEGER_RE.search(raw))


def infer_direct_calculator_call(text: str) -> Optional[ToolCall]:
    expression = _normalize_expression(text)
    if not expression or not ARITHMETIC_RE.fullmatch(expression) or not _has_operator(expression):
        return None
    if not _is_safe_expression(expression):
        return None
    return ToolCall(tool=TOOL_NAME_CALCULATOR, expression=expression, raw=_tool_block(expression))


def infer_embedded_calculator_call(text: str) -> Optional[ToolCall]:
    raw = (text or "").strip()
    if not raw:
        return None
    chunks = [chunk.strip() for chunk in ARITHMETIC_CHUNK_RE.findall(raw) if _has_operator(chunk)]
    for chunk in sorted(chunks, key=len, reverse=True):
        expression = _normalize_expression(chunk)
        if expression and ARITHMETIC_RE.fullmatch(expression) and _is_safe_expression(expression):
            return ToolCall(tool=TOOL_NAME_CALCULATOR, expression=expression, raw=_tool_block(expression))
    return None


def extract_tool_call(text: str) -> Optional[ToolCall]:
    if not text:
        return None
    match = TOOL_CALL_RE.search(text)
    if not match:
        return None
    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None

    tool = str(payload.get("tool") or "").strip().lower()
    if tool not in {"", TOOL_NAME_CALCULATOR, "python"}:
        return None

    expression = _payload_expression(payload)
    if not expression or not _is_safe_expression(expression):
        return None
    return ToolCall(tool=TOOL_NAME_CALCULATOR, expression=expression, raw=_tool_block(expression))


def execute_tool(call: ToolCall, *, cwd: Optional[Path] = None, timeout_seconds: int = 8) -> ToolResult:
    _ = cwd, timeout_seconds
    if call.tool != TOOL_NAME_CALCULATOR:
        return ToolResult(call.tool, False, call.expression, "", f"Unsupported tool: {call.tool}", "", 0)
    return execute_calculator_tool(call.expression)


def format_tool_request(call: ToolCall, *, provenance: str = "runtime") -> str:
    source = provenance.strip().lower() or "runtime"
    payload = {"tool": call.tool, "expression": call.expression}
    body = json.dumps(payload, ensure_ascii=False, indent=2)
    return f"Tool request ({source})\n```json\n{body}\n```"


def format_tool_result(result: ToolResult) -> str:
    lines = [
        "Tool result",
        f"- tool: {result.tool}",
        f"- status: {'ok' if result.ok else 'error'}",
        f"- duration_ms: {result.duration_ms}",
        f"- expression: {result.expression}",
    ]
    if result.result_text:
        lines.extend(["", "result", f"```text\n{result.result_text}\n```"])
    if result.stderr:
        lines.extend(["", "stderr", f"```text\n{result.stderr}\n```"])
    return "\n".join(lines)


def build_tool_followup_message(result: ToolResult) -> str:
    parts = [
        f"TOOL RESULT: {result.tool}",
        f"status: {'ok' if result.ok else 'error'}",
        f"duration_ms: {result.duration_ms}",
        f"expression: {result.expression}",
    ]
    if result.result_text:
        parts.extend(["result:", result.result_text])
    if result.stderr:
        parts.extend(["stderr:", result.stderr])
    parts.append("Use this calculator result. If another arithmetic check is still needed, you may emit another calculator tool call. Otherwise answer the original user request directly.")
    return "\n".join(parts)


def load_tool_behavior_primer() -> str:
    try:
        text = get_tool_behavior_primer_path().read_text(encoding="utf-8-sig").strip()
    except FileNotFoundError:
        return DEFAULT_BEHAVIOR_PRIMER
    return text or DEFAULT_BEHAVIOR_PRIMER


def execute_calculator_tool(expression: str) -> ToolResult:
    start = time.perf_counter()
    if not _is_safe_expression(expression):
        return ToolResult(TOOL_NAME_CALCULATOR, False, expression, "", "Unsupported calculator expression.", "", _elapsed_ms(start))
    try:
        tree = ast.parse(expression, mode="eval")
        value = eval(compile(tree, "<evaluator_calculator>", "eval"), {"__builtins__": {}}, {})
    except ZeroDivisionError:
        return ToolResult(TOOL_NAME_CALCULATOR, False, expression, "", "Division by zero.", "", _elapsed_ms(start))
    except Exception as exc:
        return ToolResult(TOOL_NAME_CALCULATOR, False, expression, "", str(exc), "", _elapsed_ms(start))
    return ToolResult(TOOL_NAME_CALCULATOR, True, expression, "", "", _stringify_result(value), _elapsed_ms(start))


def _payload_expression(payload: dict[str, object]) -> str:
    expression = str(payload.get("expression") or "").strip()
    if expression:
        return _normalize_expression(expression)

    code = str(payload.get("code") or "").strip()
    if not code:
        return ""
    lines = [line.strip() for line in code.splitlines() if line.strip()]
    if len(lines) != 1 or "=" not in lines[0]:
        return ""
    lhs, rhs = lines[0].split("=", 1)
    if lhs.strip() != "result":
        return ""
    return _normalize_expression(rhs)


def _normalize_expression(text: str) -> str:
    candidate = (text or "").strip()
    lowered = candidate.lower()
    for prefix in ("compute ", "calculate ", "evaluate ", "verify that ", "verify ", "check ", "what is "):
        if lowered.startswith(prefix):
            candidate = candidate[len(prefix) :].strip()
            lowered = candidate.lower()
            break
    candidate = re.sub(r"\b(exactly|please|is correct|correct)\b", "", candidate, flags=re.IGNORECASE)
    candidate = re.sub(r"\bmod\b", "%", candidate, flags=re.IGNORECASE)
    candidate = candidate.replace("^", "**")
    candidate = candidate.replace(",", "")
    candidate = re.sub(r"\s*=\s*\?$", "", candidate)
    candidate = re.sub(r"\s*=\s*$", "", candidate)
    candidate = re.sub(r"\?\s*$", "", candidate)
    candidate = re.sub(r"(?<=[\d)])\s*\.(?!\d)\s*$", "", candidate)
    candidate = re.sub(r"(?<=\d)\s*(?=\()", "*", candidate)
    candidate = re.sub(r"(?<=\))\s*(?=\d)", "*", candidate)
    candidate = re.sub(r"(?<=\))\s*(?=\()", "*", candidate)
    candidate = re.sub(r"\s+", "", candidate)
    return candidate.strip()


def _is_safe_expression(expression: str) -> bool:
    try:
        tree = ast.parse(expression, mode="eval")
    except Exception:
        return False
    allowed = (
        ast.Expression,
        ast.BinOp,
        ast.UnaryOp,
        ast.Constant,
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.FloorDiv,
        ast.Mod,
        ast.Pow,
        ast.USub,
        ast.UAdd,
        ast.Load,
    )
    has_binop = False
    for node in ast.walk(tree):
        if not isinstance(node, allowed):
            return False
        has_binop = has_binop or isinstance(node, ast.BinOp)
    return has_binop


def _has_operator(text: str) -> bool:
    return any(op in text for op in ("+", "-", "*", "/", "%", "^"))


def _tool_block(expression: str) -> str:
    return "<tool_call>\n" + json.dumps({"tool": TOOL_NAME_CALCULATOR, "expression": expression}, ensure_ascii=False) + "\n</tool_call>"


def _stringify_result(value: object) -> str:
    if isinstance(value, float):
        if value == 0:
            return "0"
        if value.is_integer():
            return str(int(value))
        return repr(value)
    return repr(value)


def _elapsed_ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)
