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

""" This module handles Google authentication """

import os
import sys
import json

from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import AuthorizedSession
from six.moves import http_client

_BRAINMAPS_SCOPES = ["https://www.googleapis.com/auth/brainmaps"]
_REFRESH_CODES = (http_client.UNAUTHORIZED, http_client.FORBIDDEN)


def acquire_credentials(client_secret_file=None,
                        client_id=None,
                        client_secret=None,
                        use_stored=True,
                        store=True,
                        make_global=True,
                        gui_auth=False,
                        storage_path=os.path.expanduser("~/.google_api_cred")):
    """Acquire credentials for brainmaps API and return authorized session.

    client_secret_file or both client_id and client_secret are required on
    first run. After that, the values are read from storage_path.
    """
    # Construct authentication from a client secrets file,
    # available from https://console.developers.google.com/

    if client_secret_file or (client_id and client_secret):
        if client_secret_file:
            flow = InstalledAppFlow.from_client_secrets_file(
                client_secret_file,
                scopes=_BRAINMAPS_SCOPES,
                redirect_uri="urn:ietf:wg:oauth:2.0:oob")
        elif client_id and client_secret:
            flow = InstalledAppFlow.from_client_config(
                {
                    "installed": {
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://www.googleapis.com/oauth2/v3/token"
                    }
                },
                scopes=_BRAINMAPS_SCOPES,
                redirect_uri="urn:ietf:wg:oauth:2.0:oob")
        else:
            raise Exception("Valid credentials required.")

        if gui_auth:
            flow.run_local_server()
        else:
            flow.run_console()

        credentials = flow.credentials
        if store:
            store_credentials(credentials, storage_path)
    elif use_stored and os.path.isfile(storage_path):
        flow = InstalledAppFlow.from_client_secrets_file(
                storage_path,
                scopes=_BRAINMAPS_SCOPES,
                redirect_uri="urn:ietf:wg:oauth:2.0:oob")
    else:
        raise Exception("Valid credentials required.")

    if make_global:
        sys.modules['brainmap_flow'] = flow
        sys.modules['brainmap_session'] = flow.authorized_session()

    return flow


def store_credentials(credentials, storage_path):
    """Store credentials in json file."""
    stored_credentials = {'installed': {
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri
    }}
    with open(storage_path, 'w') as outfile:
        json.dump(stored_credentials, outfile, indent=4)


def _eval_session(session=None, raise_error=True):
    """Evaluate brainmaps session and checks for globally defined session."""
    if session is None:
        if 'brainmap_session' in sys.modules:
            return sys.modules['brainmap_session']
        elif 'brainmap_session' in globals():
            return globals()['brainmap_session']
        else:
            if raise_error:
                raise Exception('Please either pass a brainmaps session or '
                                'define globally as "service" ')
    elif not isinstance(session, AuthorizedSession):
        error = 'Expected None or Resource, got {}'.format(type(session))
        if raise_error:
            raise TypeError(error)

    return session

def _eval_volumeId(volumeId, raise_error=True):
    """Evaluate volume Id and checks for globally defined service."""
    if volumeId is None:
        if 'volumeId' in sys.modules:
            return sys.modules['volumeId']
        elif 'volumeId' in globals():
            return globals()['volumeId']
        else:
            if raise_error:
                raise Exception('Please either pass a volumeId as string or '
                                'define globally as "volumeId"')
    elif not isinstance(volumeId, str):
        error = 'Expected None or string, got {}'.format(type(volumeId))
        if raise_error:
            raise TypeError(error)

    return volumeId

def set_global_volume(vol):
    """Set global volume."""
    sys.modules['volumeId'] = vol
