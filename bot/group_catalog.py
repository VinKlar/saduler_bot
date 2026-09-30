import json
import re
from pathlib import Path


CATALOG_PATH = Path(__file__).with_name("group_catalog.json")


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().casefold().replace("ё", "е")


def normalize_group(value: str) -> str:
    return normalize_text(value).replace(" ", "").rstrip(".")


class GroupCatalog:
    def __init__(self, data: dict):
        self.source = data.get("source")
        self.directions = data.get("directions", [])
        self._directions_by_id = {item["id"]: item for item in self.directions}
        self._groups = {
            normalize_group(group): item
            for group, item in data.get("groups", {}).items()
        }

    @classmethod
    def load(cls, path: Path = CATALOG_PATH):
        with path.open("r", encoding="utf-8") as file:
            return cls(json.load(file))

    def find_group(self, query: str):
        return self._groups.get(normalize_group(query))

    def get_direction(self, direction_id: str):
        return self._directions_by_id.get(direction_id)

    def get_profile(self, direction_id: str, profile_id: str):
        direction = self.get_direction(direction_id)
        if not direction:
            return None
        return next(
            (item for item in direction["profiles"] if item["id"] == profile_id),
            None,
        )

    def search_directions(self, query: str) -> list[dict]:
        normalized_query = normalize_text(query)
        if not normalized_query:
            return []

        code_match = re.search(r"\d{2}\.\d{2}\.\d{2}", normalized_query)
        requested_code = code_match.group(0) if code_match else None
        name_query = normalized_query
        if requested_code:
            name_query = normalize_text(normalized_query.replace(requested_code, ""))

        matches = []
        for direction in self.directions:
            codes = direction["code"].split("/")
            if requested_code and requested_code not in codes:
                continue

            direction_name = normalize_text(direction["name"])
            if name_query and name_query not in direction_name and direction_name not in name_query:
                continue

            if requested_code or name_query in direction_name:
                matches.append(direction)

        return matches


GROUP_CATALOG = GroupCatalog.load()
