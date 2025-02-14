from pathlib import Path
import logging
from sqlite3 import Connection
from dataclasses import dataclass
import time

import db
import metadata
import music
import settings


log = logging.getLogger('app.scanner')


def scan_playlists(conn: Connection) -> set[str]:
    """
    Scan playlist directories, add or remove playlists from the database
    where necessary.
    """
    paths_db = {row[0] for row in conn.execute('SELECT path FROM playlist').fetchall()}
    paths_disk = {p.name for p in Path(settings.music_dir).iterdir() if p.is_dir() and not p.name.startswith('.trash.')}

    add_to_db = []

    for path in paths_db:
        if path not in paths_disk:
            log.info('Removing playlist: %s', path)
            conn.execute('DELETE FROM playlist WHERE path=?', (path,))

    for path in paths_disk:
        if path not in paths_db:
            log.info('Adding playlist: %s', path)
            add_to_db.append((path,))

    conn.executemany('INSERT INTO playlist (path) VALUES (?)', add_to_db)

    return paths_disk


@dataclass
class QueryParams:
    main_data: dict[str, str|int|None]
    artist_data: list[dict[str, str]]
    tag_data: list[dict[str, str]]


def query_params(relpath: str, path: Path) -> QueryParams:
    """
    Create dictionary of track metadata, to be used as SQL query parameters
    """
    meta = metadata.probe(path)

    main_data: dict[str, str|int|None] = {'path': relpath,
                                          'duration': meta.duration,
                                          'title': meta.title,
                                          'album': meta.album,
                                          'album_artist': meta.album_artist,
                                          'track_number': meta.track_number,
                                          'year': meta.year}
    if meta.artists is None:
        artist_data = []
    else:
        artist_data = [{'track': relpath,
                        'artist': artist} for artist in meta.artists]
    tag_data = [{'track': relpath,
                 'tag': tag} for tag in meta.tags]

    return QueryParams(main_data, artist_data, tag_data)


def scan_tracks(conn: Connection, playlist_name: str) -> None:
    """
    Scan for added, removed or changed tracks in a playlist.
    """
    log.info('Scanning playlist: %s', playlist_name)

    paths_db: set[str] = set()

    for track_relpath, track_db_mtime in conn.execute('SELECT path, mtime FROM track WHERE playlist=?',
                                          (playlist_name,)).fetchall():
        track_path = music.from_relpath(track_relpath)
        if not track_path.exists():
            log.info('deleting: %s', track_relpath)
            conn.execute('DELETE FROM track WHERE path=?', (track_relpath,))
            conn.execute('''
                         INSERT INTO scanner_log (timestamp, action, playlist, track)
                         VALUES (?, 'delete', ?, ?)
                         ''', (int(time.time()), playlist_name, track_relpath))
            continue

        paths_db.add(track_relpath)

        file_mtime = int(track_path.stat().st_mtime)
        if file_mtime != track_db_mtime:
            log.info('changed, update: %s (%s, %s)', track_relpath, file_mtime, track_db_mtime)
            params = query_params(track_relpath, track_path)
            conn.execute('''
                         UPDATE track
                         SET duration=:duration,
                             title=:title,
                             album=:album,
                             album_artist=:album_artist,
                             track_number=:track_number,
                             year=:year,
                             mtime=:mtime
                         WHERE path=:path
                        ''',
                        {**params.main_data,
                         'mtime': file_mtime})
            conn.execute('DELETE FROM track_artist WHERE track=?', (track_relpath,))
            conn.executemany('INSERT INTO track_artist (track, artist) VALUES (:track, :artist)', params.artist_data)
            conn.execute('DELETE FROM track_tag WHERE track=?', (track_relpath,))
            conn.executemany('INSERT INTO track_tag (track, tag) VALUES (:track, :tag)', params.tag_data)

            conn.execute('''
                         INSERT INTO scanner_log (timestamp, action, playlist, track)
                         VALUES (?, 'update', ?, ?)
                         ''', (int(time.time()), playlist_name, track_relpath))

    for track_path in music.scan_playlist(playlist_name):
        relpath = music.to_relpath(track_path)
        if relpath not in paths_db:
            mtime = int(track_path.stat().st_mtime)
            log.info('new track, insert: %s', relpath)
            params = query_params(relpath, track_path)
            conn.execute('''
                         INSERT INTO track (path, playlist, duration, title, album, album_artist, track_number, year, mtime)
                         VALUES (:path, :playlist, :duration, :title, :album, :album_artist, :track_number, :year, :mtime)
                         ''',
                         {**params.main_data,
                          'playlist': playlist_name,
                          'mtime': mtime})
            conn.executemany('INSERT INTO track_artist (track, artist) VALUES (:track, :artist)', params.artist_data)
            conn.executemany('INSERT INTO track_tag (track, tag) VALUES (:track, :tag)', params.tag_data)

            conn.execute('''
                         INSERT INTO scanner_log (timestamp, action, playlist, track)
                         VALUES (?, 'insert', ?, ?)
                         ''', (int(time.time()), playlist_name, relpath))


def scan(conn: Connection) -> None:
    """
    Main function for scanning music directory structure
    """
    start_time_ns = time.time_ns()
    playlists = scan_playlists(conn)
    for playlist in playlists:
        scan_tracks(conn, playlist)
    duration_ms = (time.time_ns() - start_time_ns) // 1000000
    log.info('Done scanning all playlists, took %sms', duration_ms)
