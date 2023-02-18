from collections import defaultdict
import json
import logging
from typing import Any, Dict, List, Set, Tuple, Union
import os

from flat_search.data import Property
from dataclasses import fields

from flat_search.settings import Settings


class FieldChange():
    def __init__(self, field_name: str, old: Any, new: Any) -> None:
        self.field_name = field_name
        self.old = old
        self.new = new


class PropertyChanges():
    def __init__(self, appended: List[str], removed: List[str], modified: Dict[str, List[FieldChange]]) -> None:
        self.appended = appended
        self.removed = removed
        self.modified = modified

    class Encoder(json.JSONEncoder):
        def default(self, o):
            return o.__dict__


def generate_changes(old: Any, new: Any, excluded_attributes: Set[str] = None) -> PropertyChanges:

    old_ids: Set[str] = {id for id in old["ids"].keys()}
    new_ids: Set[str] = {id for id in new["ids"].keys()}

    appended_ids = new_ids.difference(old_ids)
    removed_ids = old_ids.difference(new_ids)
    retained_ids = old_ids.intersection(new_ids)

    updated_ids = defaultdict(list)
    for id in retained_ids:
        old_index = old["ids"][id]
        new_index = new["ids"][id]

        old_property = old["properties"][old_index]
        new_property = new["properties"][new_index]

        for field in fields(Property):
            if field.name in excluded_attributes:
                continue

            old_value = old_property[field.name]
            new_value = new_property[field.name]
            if field.compare and old_value != new_value:
                updated_ids[id].append(FieldChange(
                    field.name, old_value, new_value))

    return PropertyChanges(list(appended_ids), list(removed_ids), updated_ids)


def dump_changes_between(settings: Settings, dump_old_path: str, dump_new_path: str) -> Tuple[PropertyChanges, List[Property], List[Property]]:
    """ finds deltas between two json dumps of properties. Returns changes and new property values"""

    with open(dump_old_path, 'r') as o:
        with open(dump_new_path, 'r') as n:
            old_dump = json.load(o)
            new_dump = json.load(n)
            diff = generate_changes(
                old_dump, new_dump, excluded_attributes=set(["date_found", "listing_url"]))

            if not settings.send_removed_properties:
                diff.removed = []

            if diff.appended or diff.removed or diff.modified:
                with open(dump_new_path.removesuffix(".json") + "_diff.json", 'w') as d:
                    json.dump(diff, d, indent=4,
                              cls=PropertyChanges.Encoder)
                    return (diff, Property.schema().load(old_dump["properties"], many=True), Property.schema().load(new_dump["properties"], many=True))
            else:
                return None


async def dump_latest_changes(settings: Settings) -> Union[Tuple[PropertyChanges, List[Property], List[Property]], None]:
    """ finds newest and second newest dumps then compares them and dumps the change log then returns the changes if there are any and the two property lists """
    dump_dir = "data"
    files = sorted([x for x in os.listdir(dump_dir)
                   if not "diff" in x and x.endswith(".json")])

    if len(files) >= 2:
        new_file_path = os.path.join(dump_dir, files[-1])
        old_file_path = os.path.join(dump_dir, files[-2])
        logging.info(
            f"Comparing old dump: {old_file_path} to new dump {new_file_path}")
        return dump_changes_between(settings,
                                    old_file_path, new_file_path)

    return None
