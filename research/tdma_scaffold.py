from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


FINAL_TAG_RE = re.compile(r"<final>\s*([^<]+)\s*</final>", re.IGNORECASE)
INT_RE = re.compile(r"-?\d+")


@dataclass(frozen=True)
class TDMAConfig:
    max_rounds: int = 8
    memory_tail_records: int = 64
    require_arbiter_approval: bool = True
    max_completion_tokens: int = 4096


@dataclass(frozen=True)
class AgentMessage:
    role: str
    text: str


@dataclass(frozen=True)
class RoundResult:
    round_index: int
    athena_text: str
    artemis_text: str
    agent01_text: str
    athena_final: int | None
    artemis_final: int | None
    athena_latency_s: float
    artemis_latency_s: float
    agent01_latency_s: float
    total_latency_s: float
    arbiter_decision: str
    accepted: bool


class TextAgent(Protocol):
    def generate(self, prompt: str, *, max_completion_tokens: int) -> str:
        """Generate one text response from a prompt."""


class MemoryNDJSON:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.touch()

    def tail(self, n: int) -> list[dict]:
        if n <= 0:
            return []
        lines = self.path.read_text(encoding="utf-8", errors="ignore").splitlines()
        out: list[dict] = []
        for line in lines[-n:]:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return out

    def append(self, row: dict) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False))
            f.write("\n")


def extract_final_integer(text: str) -> int | None:
    tagged = FINAL_TAG_RE.findall(text)
    if tagged:
        m = INT_RE.search(tagged[-1])
        if m:
            return int(m.group(0))
    ints = INT_RE.findall(text)
    if not ints:
        return None
    return int(ints[-1])


def arbiter_approved(text: str) -> bool:
    lower = text.lower()
    if "<final>" in lower:
        return True
    if "approve" in lower and "reject" not in lower:
        return True
    return False


def parse_arbiter_decision(text: str) -> str:
    lower = text.lower()
    if "reject" in lower:
        return "reject"
    if "approve" in lower or "<final>" in lower:
        return "approve"
    return "unknown"


class CallableTextAgent:
    """Adapter for function-style clients.

    Expected callable signature:
        fn(prompt: str, max_completion_tokens: int) -> str
    """

    def __init__(self, fn):
        self._fn = fn

    def generate(self, prompt: str, *, max_completion_tokens: int) -> str:
        return str(self._fn(prompt, max_completion_tokens))


class TriadicDebateOrchestrator:
    def __init__(
        self,
        *,
        athena: TextAgent,
        artemis: TextAgent,
        agent01: TextAgent,
        memory_store: MemoryNDJSON,
        config: TDMAConfig | None = None,
    ) -> None:
        self.athena = athena
        self.artemis = artemis
        self.agent01 = agent01
        self.memory = memory_store
        self.config = config or TDMAConfig()

    def run(self, problem_text: str) -> tuple[int | None, list[RoundResult]]:
        transcript: list[AgentMessage] = []
        rounds: list[RoundResult] = []
        memory_rows = self.memory.tail(self.config.memory_tail_records)
        memory_context = "\n".join(
            f"- [{r.get('role', 'unknown')}] {r.get('kind', 'note')}: {r.get('text', '')}"
            for r in memory_rows
        ).strip()

        for idx in range(1, self.config.max_rounds + 1):
            round_started = time.perf_counter()
            athena_prompt = self._build_athena_prompt(problem_text, transcript, memory_context)
            t0 = time.perf_counter()
            athena_text = self.athena.generate(
                athena_prompt,
                max_completion_tokens=self.config.max_completion_tokens,
            )
            athena_latency_s = time.perf_counter() - t0

            artemis_prompt = self._build_artemis_prompt(problem_text, transcript, athena_text, memory_context)
            t0 = time.perf_counter()
            artemis_text = self.artemis.generate(
                artemis_prompt,
                max_completion_tokens=self.config.max_completion_tokens,
            )
            artemis_latency_s = time.perf_counter() - t0

            agent01_prompt = self._build_agent01_prompt(problem_text, transcript, athena_text, artemis_text, memory_context)
            t0 = time.perf_counter()
            agent01_text = self.agent01.generate(
                agent01_prompt,
                max_completion_tokens=self.config.max_completion_tokens,
            )
            agent01_latency_s = time.perf_counter() - t0
            total_latency_s = time.perf_counter() - round_started

            athena_final = extract_final_integer(athena_text)
            artemis_final = extract_final_integer(artemis_text)
            arbiter_decision = parse_arbiter_decision(agent01_text)

            approved = (
                athena_final is not None
                and artemis_final is not None
                and athena_final == artemis_final
                and (
                    not self.config.require_arbiter_approval
                    or arbiter_approved(agent01_text)
                )
            )

            rr = RoundResult(
                round_index=idx,
                athena_text=athena_text,
                artemis_text=artemis_text,
                agent01_text=agent01_text,
                athena_final=athena_final,
                artemis_final=artemis_final,
                athena_latency_s=athena_latency_s,
                artemis_latency_s=artemis_latency_s,
                agent01_latency_s=agent01_latency_s,
                total_latency_s=total_latency_s,
                arbiter_decision=arbiter_decision,
                accepted=approved,
            )
            rounds.append(rr)

            transcript.extend(
                [
                    AgentMessage(role="athena", text=athena_text),
                    AgentMessage(role="artemis", text=artemis_text),
                    AgentMessage(role="agent01", text=agent01_text),
                ]
            )
            self._persist_round(problem_text=problem_text, result=rr)

            if approved:
                return athena_final, rounds

        return None, rounds

    def _persist_round(self, *, problem_text: str, result: RoundResult) -> None:
        ts = time.time()
        self.memory.append(
            {
                "ts": ts,
                "role": "agent01",
                "kind": "round_summary",
                "text": f"round={result.round_index} accepted={result.accepted} "
                f"athena_final={result.athena_final} artemis_final={result.artemis_final} "
                f"decision={result.arbiter_decision}",
                "latency": {
                    "athena_s": result.athena_latency_s,
                    "artemis_s": result.artemis_latency_s,
                    "agent01_s": result.agent01_latency_s,
                    "total_s": result.total_latency_s,
                },
                "problem_preview": problem_text[:160],
            }
        )

    def _build_athena_prompt(
        self,
        problem_text: str,
        transcript: list[AgentMessage],
        memory_context: str,
    ) -> str:
        return (
            "You are Athena (solver). Solve carefully, show concise reasoning, and if ready output <final>INTEGER</final>.\n\n"
            f"Problem:\n{problem_text}\n\n"
            f"Memory:\n{memory_context or '(none)'}\n\n"
            f"Transcript:\n{self._render_transcript(transcript)}\n"
        )

    def _build_artemis_prompt(
        self,
        problem_text: str,
        transcript: list[AgentMessage],
        athena_text: str,
        memory_context: str,
    ) -> str:
        return (
            "You are Artemis (critic). Find errors or confirm Athena. If final is valid, emit <final>INTEGER</final>.\n\n"
            f"Problem:\n{problem_text}\n\n"
            f"Athena draft:\n{athena_text}\n\n"
            f"Memory:\n{memory_context or '(none)'}\n\n"
            f"Transcript:\n{self._render_transcript(transcript)}\n"
        )

    def _build_agent01_prompt(
        self,
        problem_text: str,
        transcript: list[AgentMessage],
        athena_text: str,
        artemis_text: str,
        memory_context: str,
    ) -> str:
        return (
            "You are Agent01 (arbiter). Approve only if Athena and Artemis are consistent and final integer is reliable. "
            "Reply with APPROVE or REJECT, optionally including <final>INTEGER</final>.\n\n"
            f"Problem:\n{problem_text}\n\n"
            f"Athena:\n{athena_text}\n\n"
            f"Artemis:\n{artemis_text}\n\n"
            f"Memory:\n{memory_context or '(none)'}\n\n"
            f"Transcript:\n{self._render_transcript(transcript)}\n"
        )

    @staticmethod
    def _render_transcript(transcript: list[AgentMessage]) -> str:
        if not transcript:
            return "(empty)"
        rendered: list[str] = []
        for item in transcript[-24:]:
            rendered.append(f"[{item.role}] {item.text}")
        return "\n".join(rendered)
