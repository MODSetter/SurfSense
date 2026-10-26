"""The user's own OAuth app, for a provider taking only apps registered with it in advance.

Its id and scopes go on the plugin's entry; its secret only into the encrypted credential.
"""

from fastapi import HTTPException, status
from pydantic import BaseModel

from api.config import get_settings
from modules.plugins.remote.sign_in.oauth.sign_in_client import sign_in_client


class OwnApp(BaseModel):
    client_id: str
    client_secret: str | None = None
    scopes: list[str] | None = None


def own_app_auth(app: OwnApp) -> dict:
    # `own_app` tells it from a registry entry's own client ID, which the publisher set.
    auth: dict = {"type": "oauth", "client_id": app.client_id.strip(), "own_app": True}
    if app.scopes:
        auth["scopes"] = app.scopes
    return auth


def needs_own_app() -> HTTPException:
    """The provider takes only apps registered in advance, with the callback to register one."""
    return HTTPException(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        {
            "code": "plugin_oauth_needs_client",
            "message": (
                "This server accepts only apps registered with it in advance. "
                "Register your own and sign in with its client ID."
            ),
            "redirect_uri": sign_in_client(get_settings().port).redirect_uri,
        },
    )


def registration_refused() -> HTTPException:
    """The provider registers apps, but refused SurfSense: it may take only apps it approved."""
    return HTTPException(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        {
            "code": "plugin_oauth_refused",
            "message": (
                "This server's sign-in refused to register SurfSense. It may accept "
                "only apps it approved."
            ),
            "redirect_uri": sign_in_client(get_settings().port).redirect_uri,
        },
    )
