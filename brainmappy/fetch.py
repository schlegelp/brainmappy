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


""" This module contains functions to fetch data via Google's brainmaps API.
"""

import functools
import math
import urllib

from .auth import _eval_session, _eval_volumeId
from .io import parse_raw_ng

from tqdm import trange

import numpy as np
import pandas as pd
from scipy.cluster.vq import kmeans2


@functools.lru_cache(maxsize=32)
def get_schemas(session=None):
    """Return DataFrame with available schemata.

    Parameters
    ----------
    session :           AuthorizedSession
                        Get from ``brainmappy.acquire_credentials``.
                        If None, will search in globals.

    Returns
    -------
    pandas.DataFrame

    """
    session = _eval_session(session)

    url = _make_url('$discovery', 'rest')
    resp = session.get(url)

    resp.raise_for_status()

    return pd.DataFrame.from_records(resp.json())


@functools.lru_cache(maxsize=32)
def get_volumes(session=None):
    """Return list of available volumes.

    Parameters
    ----------
    session :           AuthorizedSession
                        Get from ``brainmappy.acquire_credentials``.
                        If None, will use search in globals.

    Returns
    -------
    list

    """
    session = _eval_session(session)

    url = _make_url('v1', 'volumes')
    resp = session.get(url)

    resp.raise_for_status()

    return resp.json()['volumeId']


@functools.lru_cache(maxsize=32)
def get_volume_info(volume_id, session=None):
    """Get info on volume.

    Parameters
    ----------
    volume_id :         str
                        Volume ID to look up info for.
    session :           AuthorizedSession
                        Get from ``brainmappy.acquire_credentials``.
                        If None, will search in globals.

    Returns
    -------
    list of dictionarys
                        Dictionaries containing for each scale of this volume::

                         {'volumeSize': {'x': int, 'y': int, 'z': int},
                          'channelCount': int,
                          'channelType': str (e.g. 'UINT64'),
                          'pixelSize': {'x': int, 'y': int, 'z': int},
                          'boundingBox': [{'corner': {},
                                           'size': {'x': int, 'y': int, 'z': int}}]}

    """
    session = _eval_session(session)

    url = _make_url('v1', 'volumes', volume_id)
    resp = session.get(url)

    resp.raise_for_status()

    return resp.json()['geometry']


@functools.lru_cache(maxsize=32)
def get_mesh_list(volume_id, session=None):
    """List meshes for this volume.

    Parameters
    ----------
    volume_id :         str
                        Volume ID to look up info for.
    session :           AuthorizedSession
                        Get from ``brainmappy.acquire_credentials``.
                        If None, will use search in globals.

    Returns
    -------
    list of dict
                        List of dictionaries::

                          [{'name': str, 'type': str}]

    None
                        If no meshes

    """
    session = _eval_session(session)

    url = _make_url('v1', 'objects', volume_id, 'meshes')
    resp = session.get(url)

    resp.raise_for_status()

    return resp.json().get('meshes', None)


@functools.lru_cache(maxsize=32)
def get_resource_list(object_id, volume_id, session=None):
    """List resources for a given object.

    Parameters
    ----------
    object_id :         int
                        ID of object.
    volume_id :         str
                        Volume ID to look up info for.
    session :           AuthorizedSession
                        Get from ``brainmappy.acquire_credentials``.
                        If None, will use search in globals.

    Returns
    -------
    dict

    """
    session = _eval_session(session)

    url = _make_url('v1', 'volumes', volume_id, 'objects', object_id, 'resources')
    resp = session.get(url)

    resp.raise_for_status()

    return resp.json()


@functools.lru_cache(maxsize=32)
def get_projects(session=None):
    """Return list of projects.

    Parameters
    ----------
    session :           AuthorizedSession
                        Get from ``brainmappy.acquire_credentials``.
                        If None, will search in globals.

    Returns
    -------
    pandas.DataFrame

    """
    session = _eval_session(session)

    url = _make_url('v1', 'projects')
    resp = session.get(url)

    resp.raise_for_status()

    return pd.DataFrame.from_records(resp.json()['project'])


@functools.lru_cache(maxsize=32)
def get_datasets(project_id, session=None):
    """Return list of datasets in given project.

    Parameters
    ----------
    project_id :        str | int
                        Project ID.
    session :           AuthorizedSession
                        Get from ``brainmappy.acquire_credentials``.
                        If None, will search in globals.

    Returns
    -------
    list of datasetIds

    """
    session = _eval_session(session)

    url = _make_url('v1', 'datasets', project_id=project_id)
    resp = session.get(url)

    resp.raise_for_status()

    return resp.json()['datasetIds']


@functools.lru_cache(maxsize=32)
def get_change_stacks(volume_id, session=None):
    """Return list of change stacks for given volume.

    Parameters
    ----------
    volume_id :         int
                        ID of volume. See ``brainmappy.get_volumes``.
    session :           AuthorizedSession
                        Get from ``brainmappy.acquire_credentials``.
                        If None, will search in globals.

    Returns
    -------
    list

    """
    session = _eval_session(session)

    url = _make_url('v1', 'changes', volume_id, 'change_stacks')
    resp = session.get(url)

    resp.raise_for_status()

    return resp.json()['changeStackId']


def get_fragments(object_id, volume_id=None, mesh_name='mcws_quad1e6',
                  session=None, change_stack_id=None):
    """Return fragments constituting a given object.

    Parameters
    ----------
    object_id :         int
                        ID of object.
    volume_id :         str | None, optional
                        ID of segmentation volume to use. If None, will search
                        in globals.
    mesh_name :         str
                        Name of meshes.
    session :           AuthorizedSession
                        Get from ``brainmappy.acquire_credentials``.
                        If None, will search in globals.
    change_stack_id :   str, optional
                        If provided, will use alternative agglomeration stack.

    Returns
    -------
    list
                        List of object ID -> fragment ID mapping.

    """
    session = _eval_session(session)
    volume_id = _eval_volumeId(volume_id)

    url = _make_url('v1', 'objects', volume_id, 'meshes',
                    mesh_name + ':listfragments',
                    objectId=object_id,
                    returnSupervoxelIds=True)

    if change_stack_id:
        url += urllib.parse.urlencode({'header.changeStackId': change_stack_id})

    resp = session.get(url)
    resp.raise_for_status()

    frags = resp.json()

    if not frags:
        raise ValueError('No fragments found for object {}'.format(object_id))

    return list(zip(frags['supervoxelId'], frags['fragmentKey']))


def get_meshes_batch(object_id, volume_id=None, session=None,
                     mesh_name='mcws_quad1e6', change_stack_id=None):
    """Return meshes for given object ID.

    Parameters
    ----------
    object_id :         int
                        ID of object.
    volume_id :         str | None, optional
                        ID of segmentation volume to use. If not provided, will
                        use global.
    session :           AuthorizedSession
                        Get from ``brainmappy.acquire_credentials``.
                        If None, will search in globals.
    mesh_name :         str
                        Name of meshes.
    change_stack_id :   str, optional
                        If provided, will use alternative agglomeration stack.

    Returns
    -------
    vertices, faces

    """
    session = _eval_session(session)
    volume_id = _eval_volumeId(volume_id)

    # Get the fragments
    frags = get_fragments(object_id=object_id,
                          volume_id=volume_id,
                          session=session,
                          change_stack_id=change_stack_id,
                          mesh_name=mesh_name)

    url = _make_url('v1', 'objects', 'meshes:batch')

    # There is a hard cap of 100 fragments per query
    verts = None
    faces = None
    for i in trange(0, len(frags), 100, desc='Fetching mesh batches'):
        chunk = frags[i: i + 100]

        post = dict(volumeId=volume_id,
                    meshName=mesh_name,
                    batches=[{'object_id': ob,
                              'fragment_keys': [fr]} for (ob, fr) in chunk])

        resp = session.post(url, json=post)

        # Parse binary data
        obj_id, frag_ids, v, f = parse_raw_ng(resp.content)

        # Combine chunks - make sure to offset faces
        faces = f if faces is None else np.append(faces,
                                                  f + verts.shape[0],
                                                  axis=0)
        verts = v if verts is None else np.append(verts,
                                                  v, axis=0)

    return verts, faces


def get_seg_at_location(coords, volume_id=None, raw_coords=False,
                        raw_vox_dims=None, chunksize=10e3, max_retries=10,
                        session=None):
    """Return meshes for given object ID.

    Parameters
    ----------
    coords :            list-like
                        List of X/Y/Z coordinates to query.
    volume_id :         str | None, optional
                        ID of segmentation volume to use. If not provided, will
                        use global.
    raw_coords :        bool, optional
                        Whether ``coords`` is in raw coordinates. If True, will
                        not convert ``coords`` into voxel coordinates.
    raw_vox_dims :      tuple, optional
                        Size of voxels. If not provided will attempt to get
                        voxel dimensions from ``get_volume_info``.
    chunksize :         int, optional
                        Use to split query in chunks.
    max_retries :       int, optional
                        Max number of retries when fetching a chunk of segment
                        IDs.
    session :           AuthorizedSession
                        Get from ``brainmappy.acquire_credentials``.
                        If None, will search in globals.


    Returns
    -------
    List of segmentation IDs
                        Segment ID "0" indicates unmapped location.

    """

    session = _eval_session(session)
    volume_id = _eval_volumeId(volume_id)

    coords = np.array(coords) if not isinstance(coords, np.ndarray) else coords

    if not raw_coords:
        if isinstance(raw_vox_dims, type(None)):
            vinfo = get_volume_info(volume_id, session=session)
            raw_vox_dims = [vinfo[0]['pixelSize'][d] for d in ['x', 'y', 'z']]

        if not isinstance(raw_vox_dims, np.ndarray):
            raw_vox_dims = np.array(raw_vox_dims)

        coords = coords / raw_vox_dims

    # Coords must not be float
    coords = coords.astype(int)

    # The backend is better at fetching data if each chunk contains spatial
    # close points:
    n_chunks = math.ceil(len(coords) / chunksize)
    centroid, labels = kmeans2(coords.astype(float), k=n_chunks)

    url = _make_url('v1', 'volumes', volume_id, 'values')

    seg_ids = np.zeros(len(coords))
    for i in trange(n_chunks,
                    desc='Fetching segmentation IDs',
                    leave=False):
        chunk = coords[labels == i]

        post = dict(locations=[','.join(c) for c in chunk.astype(str)])

        # Try this max_retries times
        for _ in range(int(max_retries)):
            resp = session.post(url, json=post)
            if resp.status_code == 200:
                break
        # Final raise if even the last request failed
        resp.raise_for_status()

        try:
            seg_ids[labels == i] = resp.json()['uint64StrList']['values']
        except KeyError:
            raise KeyError('Unable to parse response: {}'.format(resp.json()))

    return seg_ids


def _make_url(*args, **GET):
    """Make brainmaps url from given arguments.

    Parameters
    ----------
    *args
                Will be turned into the URL. For example::

                    >>> _make_url('skeleton', 'list')
                    'https://brainmaps.googleapis.com/skeleton/list'

    **GET
                Keyword arguments are assumed to be GET request queries
                and will be encoded in the url. For example::

                    >>> remote_instance.make_url('skeleton', node_gt: 100)
                    'https://brainmaps.googleapis.com/skeleton?node_gt=100'

    Returns
    -------
    url :       str

    """
    # Generate the URL
    url = 'https://brainmaps.googleapis.com/'

    for arg in args:
        arg_str = str(arg)
        joiner = '' if url.endswith('/') else '/'
        relative = arg_str[1:] if arg_str.startswith('/') else arg_str
        url = url + joiner + relative
    if GET:
        url += '?{}'.format(urllib.parse.urlencode(GET))
    return url
