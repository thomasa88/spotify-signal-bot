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

scope = ['playlist-read-private playlist-modify-private']

spotify = None

def connect_spotify():
    # spotify stores the token in the file '.cache'
    global spotify
    spotify = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id=config.client_id, client_secret=config.client_secret, redirect_uri=config.redirect_uri, scope=scope))

@dataclass
class Song:
    id: str
    artist: str
    title: str
    added_by: str
    
    def __hash__(self) -> int:
        return hash(self.id)

def get_songs():
    song_list = []
    fields = 'items(added_by.id,track(id,artists.name,name))'
    items = spotify.playlist_items(config.playlist_id, fields=fields, limit=100, offset=0, market=None, additional_types=('track')) # not 'episode'
    for item in items['items']:
        track = item['track']
        song = Song(
            id=track['id'],
            artist=', '.join([a['name'] for a in track['artists']]),
            title=track['name'],
            added_by=item['added_by']['id'])
        song_list.append(song)
    #next(result) for paged
    return set(song_list)

songs = None

async def poll_spotify(bot: signalbot.SignalBot):
    global songs

    logging.info(datetime.datetime.now())
    try:
        songs_new = get_songs()
    except requests.exceptions.ConnectionError as e:
        # Happens e.g. after computer sleep
        logging.info('Disconnected', e)
        connect_spotify()
    logging.info(f'Got song list. {len(songs_new)} songs.')

    if songs is None:
        # Get the baseline
        songs = songs_new
        logging.info(f'Initial song list stored')
        return

    added = songs_new - songs
    removed = songs - songs_new
    logging.debug(f'Added {added}')
    logging.debug(f'Removed {removed}')
    # Collect one big message and send at once
    msg = []
    if added:
        msg.append('\n'.join(f'⚡ In: {s.artist} - {s.title} ({s.added_by})' for s in added))
    if removed:
        # The one the song was added by is not the one who removed it,
        # so skip that field
        msg.append('\n'.join(f'⚡ Ut: {s.artist} - {s.title}' for s in removed))
    if msg:
        await bot.send(config.signal_group_id, '\n'.join(msg))
    songs = songs_new

MASH_PATTERN = re.compile('[^A-Za-z0-9]')
def remove_song(query):
    global songs
    # Make sure that we have a fresh list
    songs = get_songs()
    # Simple mashing: Only keep English letters. Should handle hyphens, extra
    # spaces and strange acutes in the input.
    mashed_query = MASH_PATTERN.sub('', query).lower()
    for song in songs:
        mashed_song = MASH_PATTERN.sub('', song.artist + song.title).lower()
        if mashed_query in mashed_song:
            logging.info(f'Removing {song}')
            spotify.playlist_remove_all_occurrences_of_items(
                config.playlist_id, [song.id])
            return True
    else:
        logging.info(f'No matching sound found: "{query}"')
        return False

class RemoveCommand(signalbot.Command):
    OUT_PATTERN = re.compile('!ut (.+)', re.IGNORECASE)

    async def handle(self, c: signalbot.Context):
        if m := self.OUT_PATTERN.match(c.message.text):
            query = m.group(1)
            logging.info(f'Remove "{query}"')
            MIN_LEN = 6
            if len(query) < MIN_LEN:
                # No short strings, to avoid bad matches
                await c.react('⛔')
                await c.reply(f'Ange minst {MIN_LEN} tecken!')
                return
            ok = remove_song(query)
            if ok:
                await c.react('🤖')
            else:
                await c.react('🤷')

async def hello_to_self(bot: signalbot.SignalBot):
    await bot.send(config.signal_phone_num, '🤖 Spotify Signal bot started!')

def run_signal_bot():
    bot = signalbot.SignalBot({
        "signal_service": config.signal_service,
        "phone_number": config.signal_phone_num
    })
    bot.register(RemoveCommand(), contacts=False, groups=[config.signal_group_id])  # should work with string names as well
    bot.scheduler.add_job(poll_spotify, 'interval', (bot,), seconds=10)
    bot.scheduler.add_job(hello_to_self, args=(bot,))
    bot.start()

def main():
    connect_spotify()
    run_signal_bot()

main()
