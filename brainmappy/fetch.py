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


"""This module contains functions to fetch data via Google's brainmaps API."""

import functools
import math
import urllib
import warnings

import numpy as np
import pandas as pd
import trimesh as tm

from tqdm import tqdm
from requests_futures.sessions import FuturesSession
from scipy.cluster.vq import kmeans2

from . import utils
from .auth import _eval_session, _eval_volumeId
from .io import parse_raw_ng

__all__ = [
    "get_change_stacks",
    "get_datasets",
    "get_fragments",
    "get_mesh_list",
    "get_meshes_batch",
    "get_projects",
    "get_resource_list",
    "get_schemas",
    "get_seg_at_location",
    "get_volume_info",
    "get_volumes",
]


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

    url = _make_url("$discovery", "rest")
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

    url = _make_url("v1", "volumes")
    resp = session.get(url)

    resp.raise_for_status()

    return resp.json()["volumeId"]


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
    list of dictionaries
                        Dictionaries containing for each scale of this volume::

                         {'volumeSize': {'x': int, 'y': int, 'z': int},
                          'channelCount': int,
                          'channelType': str (e.g. 'UINT64'),
                          'pixelSize': {'x': int, 'y': int, 'z': int},
                          'boundingBox': [{'corner': {},
                                           'size': {'x': int, 'y': int, 'z': int}}]}

    """
    session = _eval_session(session)

    url = _make_url("v1", "volumes", volume_id)
    resp = session.get(url)

    resp.raise_for_status()

    return resp.json()["geometry"]


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

    url = _make_url("v1", "objects", volume_id, "meshes")
    resp = session.get(url)

    resp.raise_for_status()

    return resp.json().get("meshes", None)


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

    url = _make_url("v1", "volumes", volume_id, "objects", object_id, "resources")
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

    url = _make_url("v1", "projects")
    resp = session.get(url)

    resp.raise_for_status()

    return pd.DataFrame.from_records(resp.json()["project"])


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

    url = _make_url("v1", "datasets", project_id=project_id)
    resp = session.get(url)

    resp.raise_for_status()

    return resp.json()["datasetIds"]


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

    url = _make_url("v1", "changes", volume_id, "change_stacks")
    resp = session.get(url)

    resp.raise_for_status()

    return resp.json()["changeStackId"]


def get_fragments(
    object_id,
    mesh_name,
    volume_id=None,
    session=None,
    change_stack_id=None,
):
    """Return fragments constituting a given object.

    Parameters
    ----------
    object_id :         int
                        ID of object.
    mesh_name :         str
                        Name of meshes. Usually corresponds to resolution.
                        See `get_mesh_list()` for available meshes.
    volume_id :         str | None, optional
                        ID of segmentation volume to use. If None, will search
                        in globals.
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

    url = _make_url(
        "v1",
        "objects",
        volume_id,
        "meshes",
        mesh_name + ":listfragments",
        objectId=object_id,
        returnSupervoxelIds=True,
    )

    if change_stack_id:
        url += "&" + urllib.parse.urlencode({"header.changeStackId": change_stack_id})

    resp = session.get(url)
    resp.raise_for_status()

    frags = resp.json()

    if not frags:
        raise ValueError("No fragments found for object {}".format(object_id))

    return list(zip(frags["supervoxelId"], frags["fragmentKey"]))


def get_meshes_batch(
    object_id,
    lod=0,
    volume_id=None,
    session=None,
    change_stack_id=None,
):
    """Return meshes for given object ID.

    Parameters
    ----------
    object_id :         int
                        ID of object.
    lod :               int | str, optional
                        Level of detail. Default is 0 (highest). Can also provide
                        negative integers - e.g. -1 for the lowest available resolution.
                        You can also provide a string which much correspond to the
                        meshes' name - see `get_mesh_list()` for available meshes.
    volume_id :         str | None, optional
                        ID of segmentation volume to use. If not provided, will
                        use global.
    session :           AuthorizedSession
                        Get from ``brainmappy.acquire_credentials``.
                        If None, will search in globals.
    change_stack_id :   str, optional
                        If provided, will use alternative agglomeration stack.

    Returns
    -------
    vertices, faces

    """
    session = _eval_session(session)
    volume_id = _eval_volumeId(volume_id)

    mesh_info = get_mesh_list(volume_id, session=session)

    if isinstance(lod, int):
        mesh_name = mesh_info[lod]["name"]
    elif isinstance(lod, str):
        assert lod in [m["name"] for m in mesh_info]
        mesh_name = lod
    else:
        raise ValueError("lod must be int or str")

    # Get the fragments
    frags = get_fragments(
        object_id=object_id,
        volume_id=volume_id,
        session=session,
        change_stack_id=change_stack_id,
        mesh_name=mesh_name,
    )

    url = _make_url("v1", "objects", "meshes:batch")

    # There is a hard cap of 100 fragments per query
    verts = None
    faces = None
    with tqdm(
        desc="Fetching mesh batches",
        leave=False,
        total=len(frags),
        disable=not utils.use_pbars,
    ) as pbar:
        for i in range(0, len(frags), 100):
            chunk = frags[i : i + 100]

            post = dict(
                volumeId=volume_id,
                meshName=mesh_name,
                batches=[
                    {"object_id": ob, "fragment_keys": [fr]} for (ob, fr) in chunk
                ],
            )

            resp = session.post(url, json=post)

            # Parse binary data
            obj_id, frag_ids, v, f = parse_raw_ng(resp.content)

            # Combine chunks - make sure to offset faces
            faces = f if faces is None else np.append(faces, f + verts.shape[0], axis=0)
            verts = v if verts is None else np.append(verts, v, axis=0)

            pbar.update(len(chunk))

    return tm.Trimesh(verts, faces)


def get_seg_at_location(
    coords,
    volume_id=None,
    change_stack_id=None,
    raw_coords=False,
    raw_px_dims=None,
    max_threads=10,
    session=None,
):
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
    raw_px_dims :       tuple, optional
                        Size of pixels. If not provided will attempt to get
                        voxel dimensions from ``get_volume_info``.
    max_threads :       int, optional
                        Max number of parallel requests. Reduce if you run into
                        any issues.
    session :           AuthorizedSession
                        Get from ``brainmappy.acquire_credentials``.
                        If None, will search in globals.


    Returns
    -------
    List of segmentation IDs
                        Segment ID 0 indicates unmapped location.

    """

    session = _eval_session(session)
    future_session = FuturesSession(session=session, max_workers=max_threads)
    volume_id = _eval_volumeId(volume_id)
    url = _make_url("v1", "volumes", volume_id, "values")

    # Hard coded max chunk size
    chunksize = 2e2

    coords = np.array(coords) if not isinstance(coords, np.ndarray) else coords

    if not raw_coords:
        if isinstance(raw_px_dims, type(None)):
            vinfo = get_volume_info(volume_id, session=session)
            raw_px_dims = [vinfo[0]["pixelSize"][d] for d in "xyz"]
        elif not isinstance(raw_px_dims, np.ndarray):
            raw_px_dims = np.array(raw_px_dims)

        coords = coords / raw_px_dims

    # Coords must not be float
    # Do not remove  ".astype(float)": if coords are objects round() errors out
    coords = np.round(coords.astype(float)).astype(int)

    # Cluster but catch UserWarning if we get less than n_chunks clusters
    n_chunks = math.ceil(len(coords) / chunksize)
    if n_chunks > 1:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            centroid, labels = kmeans2(coords.astype(float), k=n_chunks)
    else:
        labels = np.zeros(len(coords))

    seg_ix = []
    posts = []
    for i in range(n_chunks):
        # Get this chunk's coordinates
        ix = np.where(labels == i)[0]
        chunk = coords[ix]

        # Skip empty chunks
        if chunk.shape[0] == 0:
            continue

        # The kmeans cluster will be spatially close but will vary in size
        # They will become bigger than the 200 cap so we have to chop it up
        for k in range(0, chunk.shape[0], int(chunksize)):
            mini_chunk = chunk[k : k + int(chunksize)]
            seg_ix.append(ix[k : k + int(chunksize)])
            posts.append(dict(locations=[",".join(c) for c in mini_chunk.astype(str)]))

    if change_stack_id:
        for p in posts:
            p['change_spec'] = {'change_stack_id': change_stack_id}

    futures = [future_session.post(url, json=p) for p in posts]

    # Get the responses
    resp = []
    with tqdm(
        desc="Fetching segmentation IDs",
        leave=False,
        total=len(coords),
        disable=not utils.use_pbars,
    ) as pbar:
        for f, s in zip(futures, seg_ix):
            resp.append(f.result())
            pbar.update(len(s))

    # Make sure all futures returned data
    for r in resp:
        r.raise_for_status()

    # Extract IDs
    ids = [r.json()["uint64StrList"]["values"] for r in resp]

    # Populate segment IDs
    seg_ids = np.zeros(len(coords))
    for ix, i in zip(seg_ix, ids):
        seg_ids[ix] = i

    return seg_ids.astype(int)


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
    url = "https://brainmaps.googleapis.com/"

    for arg in args:
        arg_str = str(arg)
        joiner = "" if url.endswith("/") else "/"
        relative = arg_str[1:] if arg_str.startswith("/") else arg_str
        url = url + joiner + relative
    if GET:
        url += "?{}".format(urllib.parse.urlencode(GET))
    return url
