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
#
#    You should have received a copy of the GNU General Public License
#    along

""" This module handles Google authentication """

from httplib2 import Http
import os
import sys

import googleapiclient.discovery

from oauth2client.file import Storage
from oauth2client.client import OAuth2WebServerFlow


def acquire_credentials(CLIENT_ID=None, CLIENT_SECRET=None, use_stored=True,
                        store=True,
                        storage_path=os.path.expanduser("~/.google_api_cred")):
    """Acquire credentials for brainmaps API. """
    # CLIENT_ID and CLIENT_SECRET come from
    # https://console.developers.google.com/apis/credentials

    CLIENT_ID = CLIENT_ID if CLIENT_ID else os.environ.get('CLIENT_ID', None)
    CLIENT_SECRET = CLIENT_SECRET if CLIENT_SECRET else os.environ.get('CLIENT_SECRET', None)

    if not CLIENT_ID:
        raise ValueError('Must provide client ID or set as "CLIENT_ID"'
                        'environment variable.')

    if not CLIENT_SECRET:
        raise ValueError('Must provide client ID or set as "CLIENT_SECRET"'
                         'environment variable.')

    if use_stored and os.path.isfile(storage_path):
        storage = Storage(storage_path)
        credentials = storage.get()
    else:
        flow = OAuth2WebServerFlow(client_id=CLIENT_ID,
                                   client_secret=CLIENT_SECRET,
                                   scope="https://www.googleapis.com/auth/brainmaps",
                                   redirect_uri="urn:ietf:wg:oauth:2.0:oob",
                                   access_type="offline")
        auth_uri = flow.step1_get_authorize_url()
        auth_code = input("Enter the authentication code: ")
        credentials = flow.step2_exchange(auth_code)
    if store is not None:
        storage = Storage(storage_path)
        storage.put(credentials)
    return credentials

def create_service(credentials, make_global=True):
    """Create brainmaps API service. """
    if credentials.access_token_expired:
        http_auth = credentials.refresh(Http())
    else:
        http_auth = credentials.authorize(Http())

    service = googleapiclient.discovery.build('brainmaps', 'v1',
                                              http=http_auth,
                                              cache_discovery=False)

    if make_global:
        sys.modules['service'] = service

    return service

def refresh_credentials(credentials, store=True,
                        storage_path=os.path.expanduser("~/.google_api_cred")):
    credentials.refresh(Http())
    if store:
        storage = Storage(storage_path)
        storage.put(credentials)

def _eval_service(service, raise_error=True):
    """ Evaluates brainmaps service and checks for globally defined service as
    fall back.
    """

    if service is None:
        if 'service' in sys.modules:
            return sys.modules['service']
        elif 'service' in globals():
            return globals()['service']
        else:
            if raise_error:
                raise Exception('Please either pass a brainmaps service or '
                                'define globally as "service" ')
    elif not isinstance(service, googleapiclient.discovery.Resource):
        error = 'Expected None or Resource, got {}'.format(type(service))
        if raise_error:
            raise TypeError(error)

    return service

def _eval_volumeId(volumeId, raise_error=True):
    """ Evaluates volume Id and checks for globally defined service as
    fall back.
    """

    if volumeId is None:
        if 'volumeId' in sys.modules:
            return sys.modules['volumeId']
        elif 'volumeId' in globals():
            return globals()['volumeId']
        else:
            if raise_error:
                raise Exception('Please either pass a volumeId as string or '
                                'define globally as "volumeId" ')
    elif not isinstance(volumeId, str):
        error = 'Expected None or string, got {}'.format(type(volumeId))
        if raise_error:
            raise TypeError(error)

    return volumeId

def set_global_volume(vol):
    """ Set global volume """
    sys.modules['volumeId'] = vol


