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
   `client secret`.

## Examples

Authenticate:

```Python
from brainmappy import auth

# Set a default volume for convenience
auth.set_global_volume('12345678:some_volume_of_interest')

# Authenticate using your client ID and secret
s = auth.create_service(auth.acquire_credentials(CLIENT_ID, CLIENT_SECRET),
                        make_global=True)
```

Fetch all fragments constituting an object

```Python
from brainmappy import fetch

verts, faces = fetch.get_meshes_batch(21716312853)
```