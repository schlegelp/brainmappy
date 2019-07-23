# brainmappy

Lightweight Python 3 package for fetching data via Google's brainmaps API.

## Install

`pip3 install git+git://github.com/schlegelp/brainmappy@master`

#### Dependencies
Automatically installed with `pip`:

- `google-api-python-client`
- `oauth2client`
- `numpy`
- `requests_futures`
- `tqdm`

## Brainmaps credentials

1. Get access to Google's brainmaps API.
2. Go to [Google developer's console](https://console.developers.google.com).
3. Create a new project and activate the brainmaps API for this project via
   the dashboard.
4. Generate an OAuth 2.0 client ID for the project and save `client ID` and
   `client secret` as `client_secret.json`

## Examples

First time authenticate:

```Python
import brainmappy as bm

# Authenticate and set these credentials as default
session = bm.acquire_credentials('client_secret.json',
                                 use_stored=False,
                                 make_global=True)
```

Credentials are stored, so from now on you can just run this:

```Python
session = bm.acquire_credentials()
```

Many functions require specifying a volume ID. You can pass this explicitly
or define a single volume as default:

```Python
bm.set_global_volume('772153499790:fafb_v14:fafb_v14_16nm_v00c_split3xfill2')
```

Fetch list of all fragments constituting an object:

```Python
fragments = bm.get_fragments(21716312853)
```

Get mesh for given object:

```Python
verts, faces = bm.get_meshes_batch(21716312853)
```

## Brainmaps Documentation

Documentation for the brainmaps API can be found [here](https://developers.google.com/brainmaps/help_pages/python_quickstart).
