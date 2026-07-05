from dataclasses import dataclass, field, asdict
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


@dataclass
class SoundtrackInfo:
    album_name: Optional[str] = None
    composer: Optional[str] = None
    ref: Optional[str] = None
    tracks: List[TrackInfo] = field(default_factory=list)

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
    soundtrack: Optional[SoundtrackInfo] = None

    def add_cast_member(self, member: str):
        if member not in self.cast:
            self.cast.append(member)

    def remove_cast_member(self, member: str):
        if member in self.cast:
            self.cast.remove(member)

    def add_source(self, source: SourceInfo):
        if source not in self.source:
            self.source.append(source)

    def apply_soundtrack(self, soundtrack: SoundtrackInfo):
        self.soundtrack = soundtrack

    def to_dict(self):
        """Serialize to clean dict, including nested SourceInfo objects."""
        return asdict(self)

    def __str__(self):
        return f"CineInfo({self.title}, {self.year}, {self.director})"
