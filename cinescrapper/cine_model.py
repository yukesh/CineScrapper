"""Dataclasses representing cinema metadata stored in MongoDB."""

from dataclasses import asdict, dataclass, field
from typing import List, Optional


@dataclass
class SourceInfo:
    name: str
    link: Optional[str] = None


@dataclass
class TrackInfo:
    number: Optional[int] = None
    title: Optional[str] = None
    lyrics: Optional[str] = None
    singers: Optional[str] = None
    length: Optional[str] = None
    # Individual track selection; default is not selected.
    add_collection: bool = False


@dataclass
class SoundtrackInfo:
    album_name: Optional[str] = None
    composer: Optional[str] = None
    ref: Optional[str] = None
    tracks: List[TrackInfo] = field(default_factory=list)
    # Select the soundtrack as a whole; independent of track flags.
    add_collection: bool = False

    def add_track(self, track: TrackInfo):
        if track not in self.tracks:
            self.tracks.append(track)


@dataclass
class CineInfo:
    title: Optional[str] = None
    year: Optional[int] = None
    director: Optional[str] = None
    cast: List[str] = field(default_factory=list)
    studio: Optional[str] = None
    ref: Optional[str] = None
    source: List[SourceInfo] = field(default_factory=list)
    soundtrack_wiki: Optional[SoundtrackInfo] = None
    # Cinema-level state. These flags are independent of soundtrack/track flags.
    downloaded: bool = False
    add_collection: bool = False

    def add_cast_member(self, member: str):
        if member not in self.cast:
            self.cast.append(member)

    def remove_cast_member(self, member: str):
        if member in self.cast:
            self.cast.remove(member)

    def add_source(self, source: SourceInfo):
        if source not in self.source:
            self.source.append(source)

    @property
    def soundtrack(self) -> Optional[SoundtrackInfo]:
        """Backward-compatible alias for the Wikipedia-scraped soundtrack."""
        return self.soundtrack_wiki

    @soundtrack.setter
    def soundtrack(self, value: Optional[SoundtrackInfo]) -> None:
        self.soundtrack_wiki = value

    def apply_soundtrack(self, soundtrack: SoundtrackInfo):
        """Store scraped soundtrack metadata separately from local tracks."""
        self.soundtrack_wiki = soundtrack

    def to_dict(self):
        """Serialize this cinema and all nested dataclasses to dictionaries."""
        return asdict(self)

    def __str__(self):
        return f"CineInfo({self.title}, {self.year}, {self.director})"
