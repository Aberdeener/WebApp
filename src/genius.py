import json
import html
import logging
import traceback
from dataclasses import dataclass
import sys

import requests
from bs4 import BeautifulSoup, NavigableString, PageElement, Tag

import cache
import settings


log = logging.getLogger('app.genius')


@dataclass
class Lyrics:
    source_url: str | None
    lyrics_html: str


def _search(title: str) -> str | None:
    """
    Returns: URL of genius lyrics page, or None if no page was found.
    """
    r = requests.get("https://genius.com/api/search/multi",
                     timeout=10,
                     params={"per_page": "1", "q": title},
                     headers={'User-Agent': settings.webscraping_user_agent})

    search_json = r.json()
    for section in search_json["response"]["sections"]:
        if section['type'] == 'top_hit':
            for hit in section['hits']:
                if hit['index'] == 'song':
                    return hit['result']['url']

    return None


def _html_tree_to_lyrics(elements: list[PageElement], level=0) -> str:
    lyrics_str = ''
    for element in elements:
        if isinstance(element, NavigableString):
            # print(level, '\tstr\t', str(element))
            lyrics_str += html.escape(str(element))
        elif isinstance(element, Tag):
            # print(level, '\ttag\t', element.name, '\t', str(element))
            if element.name == 'br':
                lyrics_str += '<br>'
            else:
                # Probably an element like <a>, <p>, <i> with important text inside it.
                lyrics_str += _html_tree_to_lyrics(element.contents, level + 1)
        else:
            log.warning('Encountered unexpected element type: %s', type(element))
    return lyrics_str


def _extract_lyrics(genius_url: str) -> str | None:
    """
    Extract lyrics from the supplied Genius lyrics page
    Parameters:
        genius_url: Lyrics page URL
    Returns: A list where each element is one lyrics line.
    """
    # Firstly, a request is made to download the standard Genius lyrics page. Inside this HTML is
    # a bit of inline javascript.
    r = requests.get(genius_url,
                     timeout=10,
                     headers={'User-Agent': settings.webscraping_user_agent})
    text = r.text
    # Find the important bit of javascript using these known parts of the code
    start = text.index('window.__PRELOADED_STATE__ = JSON.parse(') + 41
    end = text.index("}');") + 1
    # Inside the javascript bit that has now been extracted, is a string. This string contains
    # JSON data. Because it is in a string, some characters are escaped. These need to be
    # un-escaped first.
    info_json_string = text[start:end].replace('\\"', "\"").replace("\\'", "'").replace('\\\\', '\\').replace('\\$', '$').replace('\\`', '`')
    try:
        # Now, the JSON object is ready to be parsed.
        info_json = json.loads(info_json_string)
    except json.decoder.JSONDecodeError as ex:
        log.info('Error retrieving lyrics: json decode error at %s', ex.pos)
        log.info('Neighbouring text: "%s"', info_json_string[ex.pos-20:ex.pos+20])
        raise ex
    # For some reason, the JSON object happens to contain lyrics HTML. This HTML is parsed
    # using BeautifulSoup. The _html_tree_to_lyrics() function is responsible for extracting
    # text from this HTML tree.
    lyric_html = info_json['songPage']['lyricsData']['body']['html']
    soup = BeautifulSoup(lyric_html, 'lxml')
    p = soup.find('p')
    if not isinstance(p, Tag):
        log.warning('Cannot extract lyrics from URL: %s', genius_url)
        log.warning('It is probably marked as unreleased')
        return None

    return _html_tree_to_lyrics(p.contents)


def get_lyrics(query: str) -> Lyrics | None:
    """
    Search for the given query, then extract lyrics from that page (if found). This function
    will return lyrics from cache if it has been cached before.
    Parameters:
        query: Search query
    Returns: Lyrics object, or None if no lyrics were found
    """
    cache_key = 'genius3' + query
    cached_data = cache.retrieve_json(cache_key)

    if cached_data is not None:
        if not cached_data['found']:
            log.info('Returning no lyrics, from cache')
            return None

        log.info('Returning cached lyrics')
        return Lyrics(cached_data['source_url'], cached_data['lyrics'])

    log.info('Searching lyrics: %s', query)
    try:
        genius_url = _search(query)
    except Exception:
        log.info('Search error')
        traceback.print_exc()
        # Return not found now, but don't cache so we try again in the future when the bug is fixed
        return Lyrics(None, 'Error during lyrics search, please report this issue if it persists.')

    if genius_url is None:
        log.info('No lyrics found')
        cache.store_json(cache_key, {'found': False})
        return None

    log.info('Found URL: %s', genius_url)

    try:
        lyrics_html = _extract_lyrics(genius_url)

        if lyrics_html is None:
            cache.store_json(cache_key, {'found': False})
            return None
    except Exception:
        log.info('Error retrieving lyrics')
        traceback.print_exc()
        # Don't cache so we try again in the future when the bug is fixed
        return Lyrics(genius_url, 'Error retrieving lyrics, please report this issue. Make sure to include the source URL in your report. Please look at the logs for a more detailed message, if you are able to.')

    cache.store_json(cache_key,
                     {'found': True,
                      'source_url': genius_url,
                      'lyrics': lyrics_html})

    return Lyrics(genius_url, lyrics_html)


if __name__ == '__main__':
    if len(sys.argv) == 3:
        if sys.argv[1] == 'search':
            print(_search(sys.argv[2]))
            sys.exit(0)
        elif sys.argv[1] == 'extract':
            lyrics = _extract_lyrics(sys.argv[2])
            if lyrics is None:
                print('no lyrics found')
            else:
                for line in lyrics.split('<br>'):
                    print(line)
            sys.exit(0)

    print('Usage:')
    print(f' - {sys.argv[0]} search [search query]')
    print(f' - {sys.argv[0]} extract [genius url]')
