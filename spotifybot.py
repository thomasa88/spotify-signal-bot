import requests
import requests_oauthlib
import time
import datetime

import config

scope = ['playlist-read-private playlist-modify-private']

# oauth = requests_oauthlib.OAuth2Session(config.client_id, redirect_uri=config.redirect_uri,
#                           scope=scope)

# authorization_url, state = oauth.authorization_url(
#         'https://accounts.spotify.com/authorize',
#         # access_type and prompt are Google specific extra
#         # parameters.
#         # access_type="offline", prompt="select_account"
#         )

# print(f'Please go to {authorization_url} and authorize access.')

# authorization_response = input('Enter the full callback URL: ')

# token_url = 'https://accounts.spotify.com/api/token'

# # token = oauth.fetch_token(
# #         token_url,
# #         authorization_response=authorization_response,
# #         # Google specific extra parameter used for client
# #         # authentication
# #         #client_secret=config.client_secret)
# # )

# from requests.auth import HTTPBasicAuth

# auth = HTTPBasicAuth(config.client_id, config.client_secret)

# # Fetch the access token

# token = oauth.fetch_token(token_url, auth=auth,
#         authorization_response=authorization_response)


# r = oauth.get('https://api.spotify.com/v1/playlists/{config.playlist_id}')

import spotipy
from spotipy.oauth2 import SpotifyOAuth

#scope = "user-library-read"

sp = None

def connect():
    # spotify stores the token in the file '.cache'
    global sp
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id=config.client_id, client_secret=config.client_secret, redirect_uri=config.redirect_uri, scope=scope))

# results = sp.current_user_saved_tracks()
# for idx, item in enumerate(results['items']):
#     track = item['track']
#     print(idx, track['artists'][0]['name'], " – ", track['name'])

#print(sp.playlist(config.playlist_id))

#playlist_add_items(playlist_id, items, position=None)
# playlist_items(playlist_id, fields=None, limit=100, offset=0, market=None, additional_types=('track', 'episode'))
#playlist_remove_all_occurrences_of_items(playlist_id, items, snapshot_id=None)
# fields=None gets all field values
# fields = None
# fields = ['added_by.id', 'track(artists(name),name)']
#tracks = sp.playlist_tracks(config.playlist_id, fields=fields, limit=100, offset=0, market=None, additional_types=('track', ))


def get_songs():
    songs = []
    fields = 'items(added_by.id,track(artists.name,name))'
    items = sp.playlist_items(config.playlist_id, fields=fields, limit=100, offset=0, market=None, additional_types=('track')) # not 'episode'
    # print(items)
    # import json
    # print(json.dumps(items, indent=2))
    for item in items['items']:
        track = item['track']
        artist = ', '.join([a['name'] for a in track['artists']])
        title = track['name']
        added_by = item['added_by']['id']
        print(f'{artist} - {title}, added by {added_by}')
        songs.append((artist, title, added_by))
    #next(result) for paged
    return songs


connect()

songs = set(get_songs())
while True:
    print(datetime.datetime.now())
    try:
        songs_new = set(get_songs())
    except requests.exceptions.ConnectionError as e:
        # Happens e.g. after computer sleep
        print('Disconnected', e)
        connect()
        
        
    print('Added', songs_new - songs)
    print('Removed', songs - songs_new)
    # Sleep shorter if there has been a change - someone is editing the list!
    time.sleep(10)
