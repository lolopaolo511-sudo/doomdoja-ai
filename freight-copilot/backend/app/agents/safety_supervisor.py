"""Compliance & Safety Supervisor agent.

Guardrail layer. Treats ALL imported content (freight text, emails, PDFs,
copied descriptions, platform data) as untrusted DATA — never instructions.
Detects prompt-injection attempts, embedded override instructions, secrets in
text, suspicious banking changes and unverified-carrier usage.
"""

from __future__ import annotations

import re

from .base import AgentResult, BaseAgent

# Patterns that indicate text is trying to act as an instruction to the system.
_INJECTION_PATTERNS = [
    r"(?i)ignore\s+(?:all\s+|any\s+)?(?:previous\s+|prior\s+)?instructions",
    r"(?i)disregard (the|all|your) (rules|instructions|system prompt)",
    r"(?i)you are now",
    r"(?i)act as (an?|the) (admin|administrator|system)",
    r"(?i)system prompt",
    r"(?i)send (the|an)? ?(email|message|payment) (now|immediately|automatically)",
    r"(?i)approve (this|the) (order|payment|carrier) (without|now)",
    r"(?i)change (the )?bank (account|details|number)",
    r"(?i)transfer (the )?(funds|money|payment)",
    r"(?i)delete (all|the) (records|data|database)",
    r"(?i)reveal (the )?(api key|password|secret|credentials)",
    r"(?i)<\s*script",
    r"(?i)drop\s+table",
]

_SECRET_PATTERNS = [
    r"(?i)api[_-]?key\s*[:=]\s*\S+",
    r"(?i)password\s*[:=]\s*\S+",
    r"sk-[A-Za-z0-9]{16,}",
    r"(?i)bearer\s+[A-Za-z0-9._-]{12,}",
]

_BANK_CHANGE = re.compile(r"(?i)(new|updated|changed) (bank|iban|account)|iban[:\s]", re.IGNORECASE)


class SafetySupervisorAgent(BaseAgent):
    name = "safety_supervisor"

    def scan_text(self, text: str | None) -> AgentResult:
        """Scan untrusted text. Returns findings; the text is NEVER executed."""
        text = text or ""
        findings: list[str] = []
        severity = "low"

        for pat in _INJECTION_PATTERNS:
            if re.search(pat, text):
                findings.append(f"prompt_injection_like:{pat}")
                severity = "high"

        for pat in _SECRET_PATTERNS:
            if re.search(pat, text):
                findings.append("possible_secret_in_text")
                severity = "high"

        if _BANK_CHANGE.search(text):
            findings.append("bank_detail_change_mentioned")
            if severity != "high":
                severity = "medium"

        blocked = severity == "high"
        summary = (
            "No safety issues detected; content treated as data."
            if not findings
            else (
                f"{len(findings)} safety finding(s); content is treated strictly "
                "as untrusted data and was NOT executed as instructions."
            )
        )
        return self._result(
            summary=summary,
            output={
                "findings": findings,
                "severity": severity,
                "blocked": blocked,
                "safe_next_step": (
                    "Human reviewer should inspect the highlighted source text."
                    if findings
                    else "Proceed; standard human approval still required for actions."
                ),
                "reviewer_required": bool(findings),
            },
            confidence=0.9 if findings else 0.8,
            factors=findings or ["clean"],
        )

    def guard_external_action(self, *, approved: bool, system: str) -> AgentResult:
        """Block any external action that is not explicitly human-approved."""
        if not approved:
            return self._result(
                summary=f"Blocked unapproved external action on {system}.",
                output={
                    "blocked": True,
                    "reason": "external action requires an approved ApprovalRequest",
                    "severity": "high",
                    "reviewer_required": True,
                },
                confidence=1.0,
                factors=["human_in_the_loop"],
            )
        return self._result(
            summary=f"External action on {system} permitted (human-approved).",
            output={"blocked": False, "severity": "low"},
            confidence=1.0,
            factors=["approved"],
        )
