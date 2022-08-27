from pathlib import Path
import subprocess
import re
from typing import Optional, List


FILENAME_STRIP_KEYWORDS = [
    'monstercat release',
    'nerd nation release',
    'monstercat official music video',
    'official audio',
    'official video',
    'official music video',
    'official lyric video',
    'official hd video',
    'extended version',
    'long version',
    '[out now]',
    'clip officiel',
    'hq videoclip',
    'videoclip',
    '(visual)'
    '[original soundtrack]'
]


def is_alpha(c):
    return c == ' ' or c == '-' or c >= 'a' and c <= 'z'


class Metadata:

    def __init__(self, path: Path, debug = False):
        self.path = path
        self.artists: Optional[List[str]] = None
        self.album: Optional[str] = None
        self.title: Optional[str] = None
        self.date: Optional[str] = None
        self.album_artist: Optional[str] = None

        command = [
            'ffmpeg',
            '-loglevel', 'error',
            '-i', path.absolute().as_posix(),
            '-f', 'ffmetadata',
            '-'
        ]
        try:
            result = subprocess.run(command,
                                shell=False,
                                check=True,
                                capture_output=True,
                                text=True)
        except subprocess.CalledProcessError as ex:
            print('metadata read error')
            print('stderr: ', ex.stderr)
            return

        # Example output:
        # -----------------------------------------------
        # ;FFMETADATA1
        # encoded_by=Switch Trial Version © NCH Software
        # comment=
        # track=3
        # album=Elevator Music For An Elevated Mood
        # artist=Cory Wong/Dave Koz
        # album_artist=Cory Wong
        # title=Restoration (feat. Dave Koz)
        # genre=Jazz
        # date=2020
        # encoder=Lavf58.76.100
        # subprocess.run()
        # -----------------------------------------------

        for line in result.stdout.splitlines():
            if line == ';FFMETADATA1':
                continue
            eq = line.index('=')
            key = line[:eq]
            value = line[eq+1:]
            if key == 'album':
                self.album = value
            elif key == 'artist':
                self.artists = value.split('/')
            elif key == 'title':
                self.title = value
            elif key == 'date':
                self.date = value
            elif key == 'album_artist':
                self.album_arist = value

            if debug:
                print(key, value, sep='\t')

    def _meta_title(self) -> Optional[str]:
        if self.artists and self.title:
            title = ' & '.join(self.artists) + ' - ' + self.title
            if self.date:
                title += ' [' + self.date + ']'
            return title
        else:
            return None

    def _filename_title(self) -> str:
        title = self.path.name
        # Remove file extension
        try:
            title = title[:title.rindex('.')]
        except ValueError:
            pass
        # Remove YouTube id suffix
        title = re.sub(r' \[[a-zA-Z0-9\-_]+\]', '', title)
        return title

    def _filename_title_search(self) -> str:
        title = self._filename_title()
        title = title.lower()
        for strip_keyword in FILENAME_STRIP_KEYWORDS:
            title = title.replace(strip_keyword, '')
        # Remove special characters
        title = ''.join([c for c in title if is_alpha(c)])
        title = title.strip()
        return title

    def display_title(self) -> str:
        title = self._meta_title()
        if title:
            return title
        else:
            return self._filename_title() + ' [~]'

    def _is_collection_album(self) -> bool:
        if self.album is None:
            raise ValueError('album name not known')
        for match in ['top 500', 'top 40', 'jaarlijsten']:
            if match in self.album.lower():
                return True
        return False

    def album_search_queries(self):
        if self.album and not self._is_collection_album():
            yield self.album + ' album cover art'
            yield self.album

        if self.artists and self.title:
            yield ' '.join(self.artists) + ' - ' + self.title + ' album cover art'
            yield ' '.join(self.artists) + ' - ' + self.title

        if self.title:
            yield self.title + ' album cover art'
            yield self.title

        yield self._filename_title_search()

    def lyrics_search_queries(self):
        if self.artists and self.title:
            yield ' '.join(self.artists) + ' - ' + self.title

        yield self._filename_title_search()


if __name__ == '__main__':
    meta = Metadata(Path('music', 'Guest-Robin', '03. Restoration (feat. Dave Koz).mp3'), debug = True)
    print('---------------------')
    print(meta.display_title())
    print(list(meta.album_search_queries()))
    print(list(meta.lyrics_search_queries()))
