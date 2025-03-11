from typing import Callable

from player_ranking.models.clan_member import ClanMember


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

    def get_min(self, prop: str) -> int | float:
        if not self._members:
            return 0
        return getattr(min(self._members.values(), key=lambda v: getattr(v, prop)), prop)

    def get_max(self, prop: str) -> int | float:
        if not self._members:
            return 0
        return getattr(max(self._members.values(), key=lambda v: getattr(v, prop)), prop)

    def __len__(self) -> int:
        return len(self._members)
