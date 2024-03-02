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

# eq and frozen to make it hashable (Alternative: Implement __hash__())
@dataclass(eq=True, frozen=True)
class Song:
    artist: str
    title: str
    added_by: str

def get_songs():
    songs = []
    fields = 'items(added_by.id,track(artists.name,name))'
    items = spotify.playlist_items(config.playlist_id, fields=fields, limit=100, offset=0, market=None, additional_types=('track')) # not 'episode'
    for item in items['items']:
        track = item['track']
        song = Song(artist=', '.join([a['name'] for a in track['artists']]),
                    title=track['name'],
                    added_by=item['added_by']['id'])
        songs.append(song)
    #next(result) for paged
    return songs

songs = None

async def poll_spotify(bot: signalbot.SignalBot):
    global songs

    logging.info(datetime.datetime.now())
    try:
        songs_new = set(get_songs())
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
    logging.info(f'Added {added}')
    logging.info(f'Removed {removed}')
    # Collect one big message and send at once
    msg = []
    if added:
        msg.append('\n'.join(f'🤖⚡ In: {s.artist} - {s.title} ({s.added_by})' for s in added))
    if removed:
        # The one the song was added by is not the one who removed it,
        # so skip that field
        msg.append('\n'.join(f'🤖⚡ Ut: {s.artist} - {s.title}' for s in removed))
    if msg:
        await bot.send(config.signal_group_id, '\n'.join(msg))
    songs = songs_new

class PingCommand(signalbot.Command):
    async def handle(self, c: signalbot.Context):
        if c.message.text == "Ping":
            await c.send("Pong")

async def hello_to_self(bot: signalbot.SignalBot):
    await bot.send(config.signal_phone_num, '🤖 Spotify Signal bot started!')

def start_signal_bot():
    bot = signalbot.SignalBot({
        "signal_service": config.signal_service,
        "phone_number": config.signal_phone_num
    })
    bot.register(PingCommand(), contacts=False, groups=["testgrupp"]) 
    bot.scheduler.add_job(poll_spotify, 'interval', (bot,), seconds=10)
    bot.scheduler.add_job(hello_to_self, args=(bot,))
    bot.start()

def main():
    connect_spotify()
    start_signal_bot()

main()
