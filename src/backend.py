import datetime
from typing import List
from selenium.webdriver.common.action_chains import ActionChains
import os
from random import randint
import time
import asyncio
import logging
from dotenv import load_dotenv
from flat_search.backends.za import Za
from flat_search.data import Property
from flat_search.data.changes import PropertyChanges, dump_latest_changes
from flat_search.data.dump import dump_properties
from flat_search.email import send_property_updates_email
from flat_search.settings import Settings, load_settings
from croniter import croniter

from flat_search.util import binomial_trial, random_in_range
load_dotenv()


# problem in https://github.com/mozilla/geckodriver/issues/776 doesn't work in firefox
def _scroll_to_element(s, e):
    s._driver.execute_script(
        'arguments[0].scrollIntoView(true)', e)
    return s


ActionChains.scroll_to_element = _scroll_to_element


def property_filter(p: Property, settings: Settings) -> bool:
    price_above_min = p.price_per_month is not None and \
        p.price_per_month >= settings.min_price
    price_below_max = p.price_per_month <= settings.max_price

    bedrooms_above_min = p.bedrooms is not None and \
        p.bedrooms >= settings.min_bedrooms
    bedrooms_below_max = p.bedrooms <= settings.max_bedrooms

    available_from_above = p.available_from is not None and \
        p.available_from.timestamp() > settings.available_from

    logging.debug(
        f"property: {p.id} filters: price:{p.price_per_month}, price_above_min={price_above_min}, price_below_max:{price_below_max}, bedrooms: {p.bedrooms}, bedrooms_above_min:{bedrooms_above_min}, bedrooms_below_max:{bedrooms_below_max}, available_from: {p.available_from}, available_from_above:{available_from_above}")
    return price_above_min and price_below_max and bedrooms_above_min and bedrooms_below_max and available_from_above


async def execute(settings: Settings):
    logging.info(
        "Executing scraping and json delta notification routines")
    za_provider = Za(settings)

    properties_za = await za_provider.retrieve_all_properties()
    properties_za = list(filter(
        lambda p: property_filter(p, settings), properties_za))

    new_dump_path = dump_properties(properties_za)
    changes = await dump_latest_changes(settings)
    if changes:
        changes, old_properties, new_properties = changes
        send_property_updates_email(
            settings, changes, old_properties, new_properties)
    elif len(os.listdir('data/')) > 1:
        logging.info(f"Deleting dump at: {new_dump_path} as no new changes")
        os.remove(new_dump_path)
    else:
        logging.info(f"Sending first dump via email")
        send_property_updates_email(
            settings, PropertyChanges(
                [x.id for x in properties_za], [], {}), [], properties_za
        )

if __name__ == "__main__":

    while True:
        # load settings each time in case they change, this lets us change things in between runs
        settings = load_settings()
        start = datetime.datetime.now()
        cron_iter = croniter(settings.cron_expression, start)

        next_date: datetime.datetime = cron_iter.get_next(
            ret_type=datetime.datetime)
        random_minutes = random_in_range(
            0, settings.cron_expression_variation)
        logging.info(f"Next cron trigger: {next_date}")
        randomized_trigger = next_date + \
            datetime.timedelta(minutes=random_minutes)
        logging.info(
            f"Adding random variation of {random_minutes:.2f} minutes, new trigger {randomized_trigger}")

        sleep_time = randomized_trigger - datetime.datetime.now()
        logging.info(f"Sleeping for {sleep_time}")

        will_skip = binomial_trial(settings.cron_expression_skip_chance)
        logging.info(f"Will this run be skipped?: {will_skip}")

        time.sleep(sleep_time.total_seconds())

        try:
            if not will_skip:
                asyncio.run(execute(settings))
            else:
                logging.info("Skipping...")
        except Exception as E:
            logging.error(
                f"Exception in scraping run.")
            logging.exception(E)
