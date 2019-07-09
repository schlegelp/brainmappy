#    This script is part of brainmappy (http://www.github.com/schlegelp/brainmappy).
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


""" This module contains functions to convert data.
"""

import argparse
import io
import json
import os
import re
import requests
import shlex
import struct

from collections import OrderedDict
from requests_futures.sessions import FuturesSession
from six.moves import http_cookies as Cookie
from tqdm import tqdm

import numpy as np
import pandas as pd

parser = argparse.ArgumentParser()
parser.add_argument('command')
parser.add_argument('url')
parser.add_argument('-d', '--data')
parser.add_argument('-b', '--data-binary', default=None)
parser.add_argument('-X', default='')
parser.add_argument('-H', '--header', action='append', default=[])
parser.add_argument('--compressed', action='store_true')
parser.add_argument('--insecure', action='store_true')


def get_ng_meshes(x=None):
    """Load neuroglancer meshes from cURLs.

    Parameters
    ----------
    x :         filepath | file-like | None
                File with cURLs to read. If ``None``, will read from clipboard.

    Returns
    -------
    dict
                ``{object_id : {'verts': [[x1, y1, z1], [...]],
                                'faces': [[v1, v2, v3], [...]]}}``

    """
    if isinstance(x, type(None)):
        # Read without any delimiting
        x = pd.read_clipboard(delimiter='\t', header=None)[0].values

    # Parse the curls
    re = parse_curls(x)

    # Discard Requests that don't point to meshes
    req = [r for r in re if r.method == 'POST']
    req = [r for r in re if 'batches' in r.data]

    if len(req) == 0:
        raise ValueError('No valid mesh cURLs found.')

    # Now retrieve data
    future_session = FuturesSession(max_workers=10)

    # For some reason .send() does not work concurrently, only .get()
    # and .post() do
    futures = [future_session.post(r.url,
                                   data=r.data,
                                   headers=r.headers) for r in req]
    responses = [f.result() for f in tqdm(futures,
                                          desc='Fetching meshes',
                                          leave=False)]

    # Raise errors, if any
    for r in responses:
        r.raise_for_status()

    # Parse data
    data = {}
    for r in tqdm(responses, desc='Extracting data', leave=False):
        object_id, filename, verts, faces = parse_raw_ng(r.content)

        if object_id not in data:
            data[object_id] = dict(fragments=[], verts=[], faces=[])

        data[object_id]['fragments'].append(filename)
        data[object_id]['verts'].append(verts)
        data[object_id]['faces'].append(faces)

    # If we have multiple fragments per object, we need to add an offset
    # to the faces before merging
    for ob in data:
        for i, faces in enumerate(data[ob]['faces'][1:]):
            # Get number of previous verts
            n_prev = sum([v.shape[0] for v in data[ob]['verts'][:i + 1]])
            faces += n_prev

    # Stack vertices and faces
    for ob in data:
        data[ob]['verts'] = np.vstack(data[ob]['verts'])
        data[ob]['faces'] = np.vstack(data[ob]['faces'])

    return data


def parse_curls(x):
    """Extract headers and data for requests from neuroglancer mesh cURLs.

    Parameters
    ----------
    x :     file | list of cURLs
            For file, it is assumed that each line is a single cURL.

    Returns
    -------
    headers :   list of dicts
    data :      list of dicts
    urls :      list of str

    """
    if isinstance(x, str) and os.path.isfile(x):
        with open(x, 'r') as f:
            return [uncurl(line) for line in f]
    else:
        return [uncurl(c) for c in x]


def uncurl(curl):
    """ This code is based on `uncurl <https://github.com/spulec/uncurl>`_ and
    was modified to return an actual requests object instead of a formatted
    string.

    Parameters
    ----------
    curl :      str

    Returns
    -------
    request.Request

    Examples
    --------
    >>> import requests
    >>> r = uncurl(curl)
    >>> s = requests.Session()
    >>> resp = s.send(r.prepare())

    """

    # Remove trailing semi-colons and whitespaces
    curl = curl.strip(';')
    curl = curl.strip()

    tokens = shlex.split(curl)
    parsed_args = parser.parse_args(tokens)

    if parsed_args.X.upper() == 'POST':
        method = 'POST'
    else:
        method = 'GET'

    post_data = parsed_args.data or parsed_args.data_binary

    if post_data:
        # Make sure method is POST if there is postdata
        method = 'POST'
        try:
            post_data_json = json.loads(post_data)
        except ValueError:
            post_data_json = None

    cookie_dict = OrderedDict()
    quoted_headers = OrderedDict()

    for curl_header in parsed_args.header:
        if curl_header.startswith(':'):
            occurrence = [m.start() for m in re.finditer(':', curl_header)]
            header_key, header_value = (curl_header[:occurrence[1]],
                                        curl_header[occurrence[1] + 1:])
        else:
            header_key, header_value = curl_header.split(":", 1)

        if header_key.lower() == 'cookie':
            cookie = Cookie.SimpleCookie(header_value)
            for key in cookie:
                cookie_dict[key] = cookie[key].value
        else:
            quoted_headers[header_key] = header_value.strip()

    return requests.Request(method, parsed_args.url,
                            data=post_data_json,
                            headers=quoted_headers,
                            cookies=cookie_dict)


def parse_raw_ng(x):
    """Parse neuroglancer's custom binary mesh format.

    Parameters
    ----------
    x :         bytes
                Binary data to parse.

    Returns
    -------
    object ID :     str
    fragment IDs :  list of str
    vertices :      numpy array
    faces :         numpy array

    Note
    ----
    The format of each fragment in the file is as follows:

    - object ID - long-long int (8 bytes)
    - filename length - int (4 bytes)
    - 4 empty pad bytes (4 bytes)
    - filename - char ({filename length} bytes)
    - n_verts - long-long int (8 bytes)
    - n_faces - long-long int (8 bytes)
    - vert coordinates - float ({n_verts} * 3 * 4 bytes)
    - face indices - int ({n_faces} * 3 * 4 bytes)

    """
    if not isinstance(x, (bytes, io.BufferedIOBase)):
        raise TypeError('Unable to parse data of type {}'.format(type(x)))

    # Turn bytes into a file-like object if necessary
    f = io.BytesIO(x) if isinstance(x, bytes) else x

    size = os.path.getsize(f.name) if isinstance(x, io.BufferedIOBase) else len(x)

    verts = []
    faces = []
    filenames = []
    while f.tell() < size:
        object_id, filenamelen = struct.unpack('qi4x', f.read(16))
        fn, n_verts, n_faces = struct.unpack('{}s2q'.format(filenamelen),
                                             f.read(filenamelen + 8 + 8))

        this_verts = struct.unpack('{}f'.format(n_verts * 3),
                                   f.read(n_verts * 3 * 4))
        this_verts = np.array(this_verts).reshape((n_verts, 3))

        this_faces = struct.unpack('{}i'.format(n_faces * 3),
                                   f.read(n_faces * 3 * 4))
        this_faces = np.array(this_faces).reshape((n_faces, 3))

        # Make sure to add an offset to the faces
        faces.append(this_faces + sum([v.shape[0] for v in verts]))
        verts.append(this_verts)
        filenames.append(fn)

    return str(object_id), filenames, np.vstack(verts).astype(int), np.vstack(faces)
