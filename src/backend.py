import os
from random import randint
import time
import asyncio
import logging
from dotenv import load_dotenv
from flat_search.backends.za import Za
from flat_search.data.changes import dump_latest_changes
from flat_search.data.dump import dump_properties
from flat_search.email import send_property_updates_email
from flat_search.settings import Settings, load_settings

load_dotenv()
logging.basicConfig(level=logging.DEBUG)


async def execute(settings: Settings):
    za_provider = Za(settings)

    properties_za = await za_provider.retrieve_all_properties()
    await dump_properties(properties_za)
    changes = await dump_latest_changes()
    if changes:
        changes, all_properties = changes
        send_property_updates_email(settings, changes, all_properties)

if __name__ == "__main__":

    settings = load_settings()
    scrape_period_seconds = randint(
        settings.scrape_delay_minimum_seconds, settings.scrape_delay_maximum_seconds)
    last_execution_time = time.time() - scrape_period_seconds

    while True:
        if time.time() - last_execution_time > float(scrape_period_seconds):
            logging.info(
                "Executing scraping and json delta notification routines")

            # load settings each time in case they change
            settings = load_settings()
            try:
                asyncio.run(execute(settings))
            except Exception as E:
                logging.error(
                    f"Exception in execution, retrying in {scrape_period_seconds}s")
                logging.exception(E)

            last_execution_time = time.time()
            scrape_period_seconds = randint(
                settings.scrape_delay_minimum_seconds, settings.scrape_delay_maximum_seconds)
            logging.info(f"Sleeping for {scrape_period_seconds}s")
            time.sleep(scrape_period_seconds)
        else:
            logging.info("Waiting for next scraping time slot...")
            time.sleep(10)
