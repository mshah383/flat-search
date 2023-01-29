import os
import time
import asyncio
import logging
from dotenv import load_dotenv
from flat_search.backends.za import Za
from flat_search.data.changes import dump_latest_changes
from flat_search.data.dump import dump_properties

load_dotenv()
logging.basicConfig(level=logging.DEBUG)


async def execute():
    za_provider = Za("London")
    za_provider.set_from_json()

    properties_za = await za_provider.retrieve_all_properties()
    await dump_properties("za", properties_za)
    await dump_latest_changes("za")

if __name__ == "__main__":

    scrape_period_seconds = int(os.getenv("SCRAPE_PERIOD_MINUTES", 5)) * 60
    last_execution_time = time.time() - scrape_period_seconds

    while True:
        if time.time() - last_execution_time > float(scrape_period_seconds):
            logging.info(
                "Executing scraping and json delta notification routines")
            try:
                asyncio.run(execute())
            except Exception as E:
                logging.error(
                    f"Exception in execution, retrying in {scrape_period_seconds}s")
                logging.exception(E)

            last_execution_time = time.time()
            logging.info(f"Sleeping for {scrape_period_seconds}s")
            time.sleep(scrape_period_seconds)
        else:
            logging.info("Waiting for next execution slot...")
            time.sleep(10)
