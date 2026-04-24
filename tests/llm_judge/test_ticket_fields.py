"""
Ticket field classification — priority and components.

Cases are defined in cases/classification.yaml.
"""

import pytest

from tests.conftest import load_yaml
from tests.utils import agent_runner

CASES = load_yaml("classification.yaml")


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_ticket_priority(case: dict):
    fields = agent_runner.get_ticket_fields(case["input"])

    assert fields["priority"] == case["expected_priority"], (
        f"Expected priority '{case['expected_priority']}', "
        f"got '{fields['priority']}'"
    )


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_ticket_components(case: dict):
    fields = agent_runner.get_ticket_fields(case["input"])

    assert set(fields["components"]) == set(case["expected_components"]), (
        f"Expected components {case['expected_components']}, "
        f"got {fields['components']}"
    )
