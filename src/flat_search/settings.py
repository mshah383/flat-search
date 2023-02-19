

from dataclasses import dataclass
import logging
import os
from typing import List

from logging.handlers import TimedRotatingFileHandler

from dataclasses_json import dataclass_json

from flat_search.data import PropertyType


@dataclass_json
@dataclass
class Settings():
    property_type_allowlist: List[PropertyType]
    """ the type of property to keep track of """

    query: str
    """ the query to use for location of the search """

    decoy_queries: List[str]
    """ alternative queries we can use to pretend we're human, try to use very similar queries to what you're looking for
        i.e. London -> London NW10, London SW11 etc..
    """

    decoy_probability: float
    """ the probability that each decoy will fire individually (0-1) """

    max_decoys: int
    """ the maximum number of decoys to be selected each scrape with the given probability"""

    min_price: int
    """ the minimum monthly price necessary to include a property """

    max_price: int
    """ the maximum monthly price necessary to include a property """

    min_bedrooms: int
    """ maximum number of bedrooms """

    max_bedrooms: int
    """ maximum number of bedrooms """

    available_from: float
    """ the timestamp for available from minimum date """

    scrape_max_pages: int
    """ the maximum number of pages to scrape each time """

    send_removed_properties: bool
    """ whether or not to update you on removed properties (not advised) """

    cron_expression_variation: float
    """ random number of minutes to add unpredictability """

    cron_expression_skip_chance: float
    """ the chance a scrape will just be ignored """

    cron_expression: str
    """" the cron expression to use for scheduling scrape runs +/- cron_expression_variation in minutes """

    email_recipients: List[str]
    """ the emails to use when sending property updates """

    email_template: str
    """ path to the email template to be used by jinja 2 with the `properties` list exposed containing dictionaries with keys of types - `value`: `Property` and `updates`: List[str] """

    no_proxy: bool
    """ WARNING, only enable this if you know what you're doing """

    za_url: str
    """ the url from which to begin scraping with za"""

    logging_level: str
    """  the log level, options: """


def load_settings() -> Settings:
    """ looks for settings-<os.getenv('ENV')>.json file in the current directory and parses it into a Settings object"""
    SETTINGS_LOCATION = f"settings-{str(os.getenv('ENV', 'dev'))}.json"
    print(f"loading settings from: {SETTINGS_LOCATION}")

    with open(SETTINGS_LOCATION, "r") as f:
        data = f.read()
        settings: Settings = Settings.schema().loads(data)

        if settings.no_proxy:
            logging.warn("NOT USING PROXY!")

        print(f"log level: {settings.logging_level}")
        os.makedirs('logs', exist_ok=True)
        logging.basicConfig(
            level=logging._nameToLevel[settings.logging_level], force=True)
        logging.getLogger().addHandler(TimedRotatingFileHandler(
            'logs/log', when='D', interval=1, backupCount=7))
        # for n, l in logging.getLogger().manager.loggerDict.items():
        #     if not n.startswith('root'):
        #         l.disabled = True
        return settings
