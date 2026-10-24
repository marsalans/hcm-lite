"""Policy Q&A guards: the brief's Section 3 rules must stay complete, correct and cheap."""

import pytest

from hcm_ai.agent.policy import POLICY_TEXT
from hcm_ai.agent.prompts import CHAT_INSTRUCTIONS, chat_instructions
from hcm_ai.services import mock_impl

# Facts a judge can ask about; each must be stated in the policy (Section 2, 3 and 7 of the brief).
REQUIRED_FACTS = [
    "09:00",
    "grace 15 min",
    "09:15",
    "half-day under 5h",
    "Sat-Sun",
    "150 m",
    "new records only",
    "409",
    "no record and no approved leave",
    "missing_checkout",
    "working days only",
    "weekends and holidays skipped",
    "annual 14",
    "sick 8",
    "casual 10",
    "unpaid unlimited",
    "422",
    "dry run",
    "unique code/email",
    "salary > 0",
    "1.5 x basic",
    "HRA 40%",
    "medical 10%",
    "per-day rate = gross / working days",
    "one day's pay, not the whole gross",
    "(absent days + unpaid days + 0.5 x half days)",
    "prorated",
    "600k",
    "1.2M",
    "2.4M",
    "3.6M",
    "30k + 15%",
    "210k + 25%",
    "510k + 35%",
    "Admin only",
    "finalized runs locked",
    "temporary password",
    "audit log",
    "bcrypt",
    "attendance rate",
    "late %",
    "absenteeism",
    "leave utilization",
    "attrition",
]


@pytest.mark.parametrize("fact", REQUIRED_FACTS)
def test_policy_states_every_required_fact(fact: str) -> None:
    flat = " ".join(POLICY_TEXT.split())
    assert fact in flat, f"policy must state: {fact!r}"


def test_policy_agrees_with_the_code_constants() -> None:
    for kind, quota in mock_impl._QUOTAS.items():
        assert f"{kind} {quota}" in POLICY_TEXT
    assert f"{mock_impl._GROSS_FACTOR} x basic" in POLICY_TEXT


def test_policy_is_the_single_source_inside_the_prompt() -> None:
    assert POLICY_TEXT in CHAT_INSTRUCTIONS
    assert CHAT_INSTRUCTIONS.count("annual 14") == 1  # not restated elsewhere


def test_policy_and_prompt_are_static_for_prefix_caching() -> None:
    assert "{" not in POLICY_TEXT and "}" not in POLICY_TEXT  # no template placeholders
    assert CHAT_INSTRUCTIONS.index(POLICY_TEXT) < CHAT_INSTRUCTIONS.index("Rules:")


def test_per_request_facts_come_after_the_whole_static_prefix() -> None:
    class Ctx:
        class context:  # noqa: N801
            class user:  # noqa: N801
                class role:  # noqa: N801
                    value = "HR"

            class today:  # noqa: N801
                @staticmethod
                def isoformat() -> str:
                    return "2026-10-25"

    text = chat_instructions(Ctx, None)  # type: ignore[arg-type]
    assert text.startswith(CHAT_INSTRUCTIONS)
    assert text.endswith("User role: HR. Today: 2026-10-25.")


def test_policy_fits_the_token_budget() -> None:
    assert len(CHAT_INSTRUCTIONS) / 4 < 850  # measured 809 real tokens (o200k_base)


def test_prompt_still_forbids_inventing_rules() -> None:
    assert "never invent a rule" in CHAT_INSTRUCTIONS
    assert "say you don't know" in CHAT_INSTRUCTIONS
