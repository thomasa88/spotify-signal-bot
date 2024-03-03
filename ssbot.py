import requests
import requests_oauthlib
import time
import datetime
import asyncio
import signalbot
import logging
from dataclasses import dataclass
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import re

import config

logging.basicConfig(
    format='%(asctime)s %(levelname)-8s %(message)s',
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S')

scope = ['playlist-modify-public playlist-read-private playlist-modify-private']

spotify = None
songs_cache = None
# To be used when the bots adds a song for another user
# song_id -> alias
added_by_override: dict[str, str] = {}

def connect_spotify():
    # spotify stores the token in the file '.cache'
    global spotify
    spotify = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id=config.client_id, client_secret=config.client_secret, redirect_uri=config.redirect_uri, scope=scope))
    
    # Do a request to force authorization, if needed (will create ".cache" file)
    #get_songs()
    logging.warning(f'Spotify user: {spotify.current_user()}')

@dataclass
class Song:
    id: str
    artist: str
    title: str
    added_by: str
    
    def __hash__(self) -> int:
        return hash(self.id)

def flatten_artists(artists_dict):
    return ', '.join([a['name'] for a in artists_dict])

def get_songs():
    song_list = []
    fields = 'items(added_by.id,track(id,artists.name,name))'
    items = spotify.playlist_items(config.playlist_id, fields=fields, limit=100, offset=0, market=None, additional_types=('track')) # not 'episode'
    for item in items['items']:
        track = item['track']
        song = Song(
            id=track['id'],
            artist=flatten_artists(track['artists']),
            title=track['name'],
            added_by=item['added_by']['id'])
        song_list.append(song)
    #next(result) for paged
    return set(song_list)


async def poll_spotify(bot: signalbot.SignalBot):
    global songs_cache

    logging.info('Poll Spotify')
    try:
        songs_new = get_songs()
    except requests.exceptions.ConnectionError as e:
        # This happened after a computer sleep.
        # Hopefully this place is the only one where we trigger a connection
        # error. Other places should be fine, but quite silent to the users
        # if we don't add error handling.
        logging.warning(f'Spotify request connect error. We will try again later. {e}')
        return
    logging.info(f'Got song list. {len(songs_new)} songs.')

    if songs_cache is None:
        # Get the baseline
        songs_cache = songs_new
        logging.info(f'Initial song list stored')
        return

    added = songs_new - songs_cache
    removed = songs_cache - songs_new
    logging.debug(f'Added {added}')
    logging.debug(f'Removed {removed}')
    # Collect one big message and send at once
    msg = []
    if added:    
        # added_by: Override the username if we added it on behalf of another user
        msg.append('\n'.join(f'⚡ In: {s.artist} - {s.title} ({consume_added_by_override(s)})' for s in added))
    if removed:
        # The one the song was added by is not the one who removed it,
        # so skip that field
        msg.append('\n'.join(f'⚡ Ut: {s.artist} - {s.title}' for s in removed))
    if msg:
        await bot.send(config.signal_group_id, '\n'.join(msg))
    songs_cache = songs_new

def get_display_name_or_id(user_id: str) -> str:
    display_name = spotify.user(user_id)['display_name']
    if display_name:
        return display_name
    else:
        return user_id

def consume_added_by_override(song: Song):
    if override_name := added_by_override.pop(song.id, None):
        return override_name
    else:
        return get_display_name_or_id(song.added_by)

MASH_PATTERN = re.compile('[^A-Za-z0-9]')
def remove_song(query):
    global songs_cache
    # Simple mashing: Only keep English letters. Should handle hyphens, extra
    # spaces and strange acutes in the input.
    mashed_query = MASH_PATTERN.sub('', query).lower()
    if not songs_cache:
        raise Exception('Empty songs cache')
    for song in songs_cache:
        mashed_song = MASH_PATTERN.sub('', song.artist + song.title).lower()
        if mashed_query in mashed_song:
            logging.info(f'Removing {song}')
            spotify.playlist_remove_all_occurrences_of_items(
                config.playlist_id, [song.id])
            return True
    else:
        logging.info(f'No matching sound found: "{query}"')
        return False

def add_song(query):
    resp = spotify.search(query, limit=1, type='track')
    tracks = resp['tracks']
    if tracks['total'] < 1:
        logging.info(f'Found no matches for "{query}"')
        return None

    track = tracks['items'][0]
    artist = flatten_artists(track['artists'])
    title = track['name']
    logging.info(f"Found {artist} - {title}")
    spotify.playlist_add_items(config.playlist_id, [track['uri']])
    
    added_song = Song(
        id=track['id'],
        artist=flatten_artists(track['artists']),
        title=track['name'],
        added_by='?')
    return added_song

class RemoveCommand(signalbot.Command):
    OUT_PATTERN = re.compile('!ut (.+)', re.IGNORECASE)

    async def handle(self, c: signalbot.Context):
        if m := self.OUT_PATTERN.match(c.message.text):
            try:
                query = m.group(1)
                logging.info(f'Remove "{query}"')
                MIN_LEN = 6
                if len(query) < MIN_LEN:
                    # No short strings, to avoid bad matches
                    await c.react('⛔')
                    await c.reply(f'Ange minst {MIN_LEN} tecken!')
                    return
                if not songs_cache:
                    await poll_spotify(c.bot)
                ok = remove_song(query)
                if ok:
                    await c.react('🤖')
                else:
                    await c.react('🤷')
            except Exception as e:
                logging.error(e)
                await c.react('⚠️')
                return

class AddCommand(signalbot.Command):
    OUT_PATTERN = re.compile('!in (.+)', re.IGNORECASE)

    async def handle(self, c: signalbot.Context):
        if m := self.OUT_PATTERN.match(c.message.text):
            try:
                query = m.group(1)
                logging.info(f'Add "{query}"')
                MIN_LEN = 6
                if len(query) < MIN_LEN:
                    # No short strings, to avoid bad matches
                    await c.react('⛔')
                    await c.reply(f'Ange minst {MIN_LEN} tecken!')
                    return
                added_song = add_song(query)
                
                if added_song:
                    # The added_by will be the bot user, so override it
                    # We don't have the Spotify name, so the signal name
                    # (as our current user sees it) will have to do..
                    user_signal_name = c.message.raw_message['envelope']['sourceName']
                    added_by_override[added_song.id] = user_signal_name
                    await c.react('🤖')
                else:
                    await c.react('🤷')
            except Exception as e:
                logging.error(e)
                await c.react('⚠️')
                return

async def hello_to_self(bot: signalbot.SignalBot):
    await bot.send(config.signal_phone_num, '🤖 Spotify Signal bot started!')

def run_signal_bot():
    bot = signalbot.SignalBot({
        "signal_service": config.signal_service,
        "phone_number": config.signal_phone_num
    })
    bot.register(RemoveCommand(), contacts=False, groups=[config.signal_group_id])  # should work with string names as well
    bot.register(AddCommand(), contacts=False, groups=[config.signal_group_id])
    bot.scheduler.add_job(poll_spotify, 'interval', (bot,), seconds=10)
    bot.scheduler.add_job(hello_to_self, args=(bot,))
    bot.start()

def main():
    connect_spotify()
    run_signal_bot()

main()
