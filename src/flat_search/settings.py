

from dataclasses import dataclass
import json
from typing import List

from dataclasses_json import dataclass_json

from flat_search.data import PropertyType


@dataclass_json
@dataclass
class Settings():
    property_type_allowlist: List[PropertyType]
    """ the type of property to keep track of """

    min_price: int
    """ the minimum monthly price necessary to include a property """

    max_price: int
    """ the maximum monthly price necessary to include a property """

    location: str
    """ the location query string to use to filter the search """

    scrape_delay_minimum_seconds: int
    """ the minimum time to wait after each scrape (full)"""

    scrape_delay_maximum_seconds: int
    """ the maximum time to wait after each scrape (full)"""

    email_recipients: List[str]
    """ the emails to use when sending property updates """

    email_template: str
    """ path to the email template to be used by jinja 2 with the `properties` list exposed containing dictionaries with keys of types - `value`: `Property` and `updates`: List[str] """

    za_area: str
    """ the area to be used by the za property provider """


def load_settings() -> Settings:
    """ looks for settings.json file in the current directory and parses it into a Settings object"""
    with open("settings.json", "r") as f:
        data = f.read()
        settings = Settings.schema().loads(data)
        return settings
