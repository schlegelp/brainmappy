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
#
#    You should have received a copy of the GNU General Public License
#    along


""" This module contains functions to fetch data via Google's brainmaps API.
"""

from .auth import _eval_service, _eval_volumeId
from .io import parse_raw_ng

import googleapiclient
import numpy as np


def get_fragments(object_id, volume_id=None, service=None, change_stack_id=None):
    """ Return fragments constituting a given object.

    Parameters
    ----------
    object_id :         int
                        ID of object.
    volume_id :         str | None, optional
                        ID of segmentation volume to use. If not provided, will
                        use global.
    service :           brainmaps API service, optional
                        Get from ``pymaid.neuroglancer.auth.create_service``.
                        If not provided, will use global.
    change_stack_id :   str, optional
                        If provided, will use alternative agglomeration stack.

    Returns
    -------
    list
                    List of object ID -> fragment ID mapping.
    """

    service = _eval_service(service)
    volume_id = _eval_volumeId(volume_id)

    me = service.objects().meshes()

    post = dict(objectId=object_id,
                volumeId=volume_id,
                meshName='mcws_quad1e6',
                returnSupervoxelIds=True)

    if change_stack_id:
        post['header_changeStackId'] = change_stack_id

    frags = me.listfragments(**post).execute()

    return list(zip(frags['supervoxelId'], frags['fragmentKey']))


def get_meshes_batch(object_id, volume_id=None, service=None,
                     change_stack_id=None):
    """ Return meshes for given object ID.

    Parameters
    ----------
    object_id :         int
                        ID of object.
    volume_id :         str | None, optional
                        ID of segmentation volume to use. If not provided, will
                        use global.
    service :           brainmaps API service, optional
                        Get from ``pymaid.neuroglancer.auth.create_service``.
                        If not provided, will use global.
    change_stack_id :   str, optional
                        If provided, will use alternative agglomeration stack.

    Returns
    -------
    verts, faces
    """

    service = _eval_service(service)
    volume_id = _eval_volumeId(volume_id)

    # Get the fragments
    frags = get_fragments(object_id, volume_id, service, change_stack_id)

    # Get the binary data
    me = service.objects().meshes()

    # There is a hard cap of 100 fragments per query
    verts = None
    faces = None
    for i in range(0, len(frags), 100):
        chunk = frags[i: i + 100]
        # Prepare request
        req = me.batch(body = dict(
                                   volumeId = volume_id,
                                   meshName = 'mcws_quad1e6',
                                   batches = [{'object_id': ob,
                                               'fragment_keys': [fr]}
                                              for (ob, fr) in chunk]
                                   )
                      )
        # We have to ignore postproc to get the binary data
        # decoding throws an error otherwise anyway
        def pass_through(resp, content):
            return content
        req.postproc = pass_through

        # Get the binary data
        bin_data = req.execute()

        # Parse binary data
        obj_id, frag_ids, v, f = parse_raw_ng(bin_data)

        # Combine chunks - make sure to offset faces
        faces = f if faces is None else np.append(faces,
                                                  f + verts.shape[0],
                                                  axis=0)
        verts = v if verts is None else np.append(verts,
                                                  v, axis=0)


    return verts, faces

