from typing import Optional
import logging
import traceback
import urllib

import requests
import musicbrainzngs

import cache
import image


musicbrainzngs.set_useragent('Super fancy music player 2.0', 0.1, 'https://github.com/DanielKoomen/WebApp')

log = logging.getLogger('app.musicbrainz')


def _search_release(title: str) -> Optional[str]:
    """
    Search for a release id using the provided search query
    """
    r = musicbrainzngs.search_releases(title)['release-list']
    if len(r) > 0:
        return r[0]['id']
    else:
        return None


def _get_image_url(release_id: str) -> Optional[str]:
    """
    Get album cover URL from MusicBrainz release id
    """
    try:
        imgs = musicbrainzngs.get_image_list(release_id)['images']

        for img in imgs:
            if img['front']:
                return img['image']
        return None
    except musicbrainzngs.musicbrainz.ResponseError as ex:
        if isinstance(ex.cause, urllib.error.HTTPError) and ex.cause.code == 404:
            return None
        raise ex

def get_cover(title: str) -> Optional[bytes]:
    """
    Get album cover for the given song title
    Returns: Image bytes, or None of no album cover was found.
    """
    cache_key = 'musicbrainz cover' + title
    cached_data = cache.retrieve(cache_key)

    if cached_data is not None:
        if cached_data == b'magic_no_cover':
            log.info('Returning no cover, from cache')
            return None
        log.info('Returning cover from cache')
        return cached_data

    try:
        release = _search_release(title)
        if release is None:
            log.info('No release found')
            cache.store(cache_key, b'magic_no_cover')
            return None

        image_url = _get_image_url(release)

        if image_url is None:
            log.info('Release has no cover image attached')
            cache.store(cache_key, b'magic_no_cover')
            return None

        r = requests.get(image_url,
                         timeout=10)
        image_bytes = r.content

        if not image.check_valid(image_bytes):
            log.warning('Returned image seems to be corrupt')
            return None

        cache.store(cache_key, image_bytes)
        log.info('Found suitable cover art')
        return image_bytes
    except Exception as ex:
        log.info('Error retrieving album art from musicbrainz: %s', ex)
        traceback.print_exc()
        return None
