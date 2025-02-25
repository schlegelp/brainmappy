#    Code shamelessly "acquired" from Eric Perlman who in turn got it from
#    Matthew Nichols. Now part of brainmappy (http://www.github.com/schlegelp/brainmappy).
#    Copyright (C) 2018 Philipp Schlegel
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.

"""This module handles Google authentication"""

import os
import sys
import pickle
import json

from google_auth_oauthlib import get_user_credentials
from google.auth.transport.requests import AuthorizedSession
from google.auth.transport.requests import Request

__all__ = ["acquire_credentials", "set_global_volume"]

_BRAINMAPS_SCOPES = ["https://www.googleapis.com/auth/brainmaps"]


def acquire_credentials(
    client_secret_file=None,
    client_id=None,
    client_secret=None,
    use_stored=True,
    store=True,
    make_global=True,
    gui_auth=False,
    storage_path=os.path.expanduser("~/brainmappy_creds.pickle"),
):
    """Acquire credentials for brainmaps API and return a AuthorizedSession.

    client_secret_file or both client_id and client_secret are required on
    first run. After that, the values are read from storage_path.
    """
    # Construct authentication from a client secrets file,
    # available from https://console.developers.google.com/

    if client_secret_file or (client_id and client_secret):
        if client_secret_file:
            with open(client_secret_file, "r") as f:
                secret = json.load(f)
            client_id = secret["installed"]["client_id"]
            client_secret = secret["installed"]["client_secret"]
        elif not client_id or not client_secret:
            raise Exception(
                "Must either provide a `client_secret_file` or `client_id` and `client_secret`."
            )

        creds = get_user_credentials(
            scopes=_BRAINMAPS_SCOPES,
            client_id=client_id,
            client_secret=client_secret,
        )
        session = AuthorizedSession(creds)
    elif use_stored and os.path.isfile(storage_path):
        with open(storage_path, "rb") as token:
            creds = pickle.load(token)
        session = AuthorizedSession(creds)
    else:
        raise Exception("Valid credentials required.")

    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            raise Exception("Credentials invalid but unable to refresh.")

    if store:
        # Save the credentials for the next run
        with open(storage_path, "wb") as token:
            pickle.dump(creds, token)

    if make_global:
        sys.modules["brainmap_credentials"] = creds
        sys.modules["brainmap_session"] = session

    return session


def _eval_session(session=None, raise_error=True):
    """Evaluate brainmaps session and checks for globally defined session."""
    if session is None:
        if "brainmap_session" in sys.modules:
            return sys.modules["brainmap_session"]
        elif "brainmap_session" in globals():
            return globals()["brainmap_session"]
        else:
            if raise_error:
                raise Exception(
                    "Please either pass a brainmaps session or "
                    'define globally as "service" '
                )
    elif not isinstance(session, AuthorizedSession):
        error = "Expected None or Resource, got {}".format(type(session))
        if raise_error:
            raise TypeError(error)

    # Refresh stale credentials
    if session.credentials.expired:
        session.credentials.refresh(Request())

    return session


def _eval_volumeId(volumeId, raise_error=True):
    """Evaluate volume Id and checks for globally defined service."""
    if volumeId is None:
        if "volumeId" in sys.modules:
            return sys.modules["volumeId"]
        elif "volumeId" in globals():
            return globals()["volumeId"]
        else:
            if raise_error:
                raise Exception(
                    "Please either pass a volumeId as string or "
                    'define globally as "volumeId"'
                )
    elif not isinstance(volumeId, str):
        error = "Expected None or string, got {}".format(type(volumeId))
        if raise_error:
            raise TypeError(error)

    return volumeId


def set_global_volume(vol):
    """Set global volume."""
    sys.modules["volumeId"] = vol
