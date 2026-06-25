"""Which capabilities each plan unlocks.

starter -> chat only
beta    -> chat or voice
pro     -> chat, voice, or both
"""

from app.agents.schemas import Capability
from app.auth.schemas import Plan

PLAN_CAPABILITIES: dict[Plan, set[Capability]] = {
    Plan.starter: {Capability.chat},
    Plan.beta: {Capability.chat, Capability.voice},
    Plan.pro: {Capability.chat, Capability.voice, Capability.both},
}


def is_capability_allowed(plan: Plan, capability: Capability) -> bool:
    return capability in PLAN_CAPABILITIES.get(plan, set())
