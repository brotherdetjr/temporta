from dataclasses import dataclass


@dataclass
class CreatePlayer:
    player_id: str


@dataclass
class CreateUniverse:
    parent_id: int | None = None


@dataclass
class CreateLocation:
    name: str
    universe_id: int
    description: str


@dataclass
class ConnectLocations:
    from_name: str
    to_name: str
    universe_id: int
    travel_time: int


@dataclass
class CreateCharacter:
    player_id: str | None = None
    universe_id: int | None = None
    parent_id: int | None = None
