"""What each subscription plan unlocks.

Capabilities (agent types):
    starter -> chat only
    beta    -> chat or voice
    pro     -> chat, voice, or both

Agent limits (how many agents you can create):
    starter -> 1
    beta    -> 3
    pro     -> 10

Features (gated extras beyond the base support agent):
    starter -> none (chat agent, lead spotting, history, basic analytics)
    beta    -> + booking, content, exports
    pro     -> + financing
"""

from enum import Enum

from app.agents.schemas import Capability
from app.auth.schemas import Plan

PLAN_CAPABILITIES: dict[Plan, set[Capability]] = {
    Plan.inactive: set(),
    Plan.starter: {Capability.chat},
    Plan.beta: {Capability.chat, Capability.voice},
    Plan.pro: {Capability.chat, Capability.voice, Capability.both},
}

# The plans that grant access. Anything else (e.g. ``inactive``) means the user
# hasn't subscribed and must pay before using the product.
PAID_PLANS: set[Plan] = {Plan.starter, Plan.beta, Plan.pro}


def is_active_plan(plan: Plan) -> bool:
    return plan in PAID_PLANS


def is_capability_allowed(plan: Plan, capability: Capability) -> bool:
    return capability in PLAN_CAPABILITIES.get(plan, set())


# --- agent count limits ----------------------------------------------------

PLAN_AGENT_LIMITS: dict[Plan, int] = {
    Plan.inactive: 0,
    Plan.starter: 1,
    Plan.beta: 3,
    Plan.pro: 10,
}


def agent_limit(plan: Plan) -> int:
    return PLAN_AGENT_LIMITS.get(plan, 0)


# --- gated features --------------------------------------------------------


class Feature(str, Enum):
    """Premium features beyond the base chat agent, gated by plan."""

    booking = "booking"
    content = "content"
    exports = "exports"
    financing = "financing"


PLAN_FEATURES: dict[Plan, set[Feature]] = {
    Plan.inactive: set(),
    Plan.starter: set(),
    Plan.beta: {Feature.booking, Feature.content, Feature.exports},
    Plan.pro: {
        Feature.booking,
        Feature.content,
        Feature.exports,
        Feature.financing,
    },
}


def is_feature_allowed(plan: Plan, feature: Feature) -> bool:
    return feature in PLAN_FEATURES.get(plan, set())
