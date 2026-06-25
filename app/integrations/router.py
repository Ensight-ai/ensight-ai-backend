"""Google connection routes: connect, OAuth callback, status, disconnect."""

from fastapi import APIRouter, Depends, status
from fastapi.responses import RedirectResponse

from app.core.config import settings
from app.dependencies import get_current_user
from app.integrations.dependencies import get_google_integration_service
from app.integrations.schemas import AuthorizeUrl, GoogleConnectionStatus
from app.integrations.service import GoogleIntegrationService, IntegrationError

router = APIRouter(prefix="/integrations/google", tags=["integrations"])


@router.get("/connect", response_model=AuthorizeUrl)
def connect_google(
    current_user=Depends(get_current_user),
    service: GoogleIntegrationService = Depends(get_google_integration_service),
):
    """Owner-only: get the Google consent URL to start connecting a calendar."""
    return AuthorizeUrl(authorize_url=service.get_authorize_url(current_user.id))


@router.get("/callback")
def google_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    service: GoogleIntegrationService = Depends(get_google_integration_service),
):
    """Public: where Google redirects the owner's browser after consent.

    Completes the handshake, then bounces back to the dashboard with a status.
    """
    base = f"{settings.frontend_url}/dashboard/settings"
    if error or not code or not state:
        return RedirectResponse(f"{base}?google=error")
    try:
        service.handle_callback(code, state)
    except IntegrationError:
        return RedirectResponse(f"{base}?google=error")
    return RedirectResponse(f"{base}?google=connected")


@router.get("/status", response_model=GoogleConnectionStatus)
def google_status(
    current_user=Depends(get_current_user),
    service: GoogleIntegrationService = Depends(get_google_integration_service),
):
    return service.get_status(current_user.id)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def disconnect_google(
    current_user=Depends(get_current_user),
    service: GoogleIntegrationService = Depends(get_google_integration_service),
):
    service.disconnect(current_user.id)
