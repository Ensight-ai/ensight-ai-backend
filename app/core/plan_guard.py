"""A FastAPI dependency that gates a route behind a plan feature.

Usage in a router::

    from app.core.plan_guard import require_feature
    from app.core.plans import Feature

    @router.post("/generate")
    def generate(current_user=Depends(require_feature(Feature.content)), ...):
        ...

It authenticates the user (like ``get_current_user``) AND checks their plan,
returning the auth user on success or raising 403 if the plan doesn't include
the feature.
"""

from fastapi import Depends, HTTPException, status

from app.auth.dependencies import get_auth_service
from app.auth.service import AuthService
from app.core.plans import Feature, is_feature_allowed
from app.dependencies import get_current_user


def require_feature(feature: Feature):
    def dependency(
        current_user=Depends(get_current_user),
        auth_service: AuthService = Depends(get_auth_service),
    ):
        plan = auth_service.get_plan(current_user.id)
        if not is_feature_allowed(plan, feature):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Your '{plan.value}' plan does not include "
                    f"'{feature.value}'. Upgrade to unlock it."
                ),
            )
        return current_user

    return dependency
