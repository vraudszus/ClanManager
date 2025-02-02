from dataclasses import dataclass
from typing import Callable


@dataclass
class ClanMember:
    rating: float
    ladder: float
    current_war: float
    war_history: float
    avg_fame: float

    previous_league: float
    current_league: float
    previous_trophies: float
    current_trophies: float
    current_season: float
    previous_season: float

    def __init__(self, tag: str, name: str, role: str, trophies: int):
        self.tag: str = tag
        self.name: str = name
        self.role: str = role
        self.trophies: int = trophies


class Clan:
    def __init__(self, initial_members: dict[str, ClanMember] = None):
        self._members: dict[str, ClanMember] = dict(initial_members) if initial_members else {}

    def add(self, member: ClanMember) -> None:
        self._members[member.tag] = member

    def get(self, tag: str) -> ClanMember:
        return self._members[tag]

    def get_members(self) -> list[ClanMember]:
        return list(self._members.values())

    def get_tag_name_map(self) -> dict[str, str]:
        return {k: v.name for k, v in self._members.items()}

    def get_tags(self) -> list[str]:
        return list(self._members.keys())

    def filter(self, condition: Callable[[ClanMember], bool]):
        return Clan({k: v for k, v in self._members.items() if condition(v)})

    def get_min_or_max(self, minimum: bool, prop: str) -> ClanMember:
        if not self._members:
            raise ValueError("Cannot find min/max in an empty clan.")

        try:
            if minimum:
                return min(self._members.values(), key=lambda v: getattr(v, prop))
            else:
                return max(self._members.values(), key=lambda v: getattr(v, prop))
        except AttributeError:
            raise ValueError(f"Field '{prop}' not found in ClanMember objects.")

    def __len__(self) -> int:
        return len(self._members)
