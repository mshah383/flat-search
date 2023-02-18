from asyncio import sleep
from datetime import datetime
from typing import Any, Callable, Union, List
from flat_search.backends import PropertyDataProvider, Proxy
from flat_search.data import Property, PropertyType
import logging
from bs4 import BeautifulSoup, Tag
from dateparser.search import search_dates
from urllib.parse import urlparse
from flat_search.scraping.strategy import PagedPropertyListingStrategy

from flat_search.settings import Settings
import time
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver


class Za(PropertyDataProvider):
    """ requires ZA_URL_FORMAT env variable to be present.
        requires the following format keys to be in the url:
        - area - one of valid areas
        - location_query - additional location query i.e. postocde
        - price_min
        - price_max
        - page_no - the 1 indexed page number
        """

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self.url = urlparse(settings.za_url)

        if settings.no_proxy:
            # don't be crazy! don't get ip banned
            assert (self.url.netloc.startswith("localhost")
                    or self.url.netloc.startswith('127'))

        self.base_url = "{uri.scheme}://{uri.netloc}".format(uri=self.url)

    def result_or_none_if_throws(logged_error_msg: str, callable: Callable[[], Union[Any, None]]):
        """ calls the given function and on an exception, logs it then returns None otherwise returns the result """
        try:
            return callable()
        except Exception as E:
            logging.error(logged_error_msg)
            logging.exception(E)
            return None

    def result_or_default_if_throws(default: Union[Any, None], callable: Callable[[], Union[Any, None]]):
        """ calls the given function and on an exception, logs it then returns None otherwise returns the result """
        try:
            return callable()
        except Exception as E:
            return default

    def format_property_types(property_types: List[PropertyType]) -> List[str]:
        """ maps property types to required format strings """
        output = []
        for property_type in property_types:
            if property_type is property_type.DETACHED_HOUSE:
                output.append("detached")
                output.append("bungalow")
            elif property_type in [property_type.FLAT, property_type.STUDIO]:
                output.append("flats")
            elif property_type is property_type.TERRACED_HOUSE:
                output.append("terraced")
                output.append("semi_detached")
            elif property_type is property_type.ROOM:
                pass
        return output

    def read_property_type_from_title(property_title: str) -> PropertyType:
        listing_title_lowercase = property_title.lower()
        property_type = PropertyType.FLAT
        if "studio" in listing_title_lowercase:
            property_type = PropertyType.STUDIO
        elif "room" in listing_title_lowercase:
            property_type = PropertyType.ROOM
        elif "terrace" in listing_title_lowercase or "semi" in listing_title_lowercase or "maisonette" in listing_title_lowercase:
            property_type = PropertyType.TERRACED_HOUSE
        elif "property" in listing_title_lowercase or "detached" in listing_title_lowercase:
            property_type = PropertyType.DETACHED_HOUSE
        return property_type

    async def _retrieve_all(self, driver: WebDriver, proxy: Union[Proxy, None]) -> List[Property]:
        settings = {
            #  warmup settings
            "query_url": self.url._replace(scheme=proxy.url.scheme).geturl() if proxy else self.url.geturl(),
            "query_decoy_queries":  self.settings.decoy_queries,
            "query_decoy_probability": self.settings.decoy_probability,
            "query_decoy_max": self.settings.max_decoys,
            "query_true_query": self.settings.query,
            "query_textbox_locator": (By.TAG_NAME, "input"),
            "query_btn_locator": (By.XPATH, "//*[text()='Search']"),
            # random walk settings
            "walk_listing_locator": (By.XPATH, "//*[contains(@id, 'listing_')]"),
            "walk_listing_look_probability": 0.1,
            "walk_listing_click_probability": 0.3,
            "walk_listing_look_delay": (0, 0.2),
            "walk_next_page_btn_locator": (By.XPATH, "//*[contains(.,'Next')]"),
            "walk_query_pages_max": self.settings.scrape_max_pages,
            # parsing settings
            "parse_function": self.parse_page
        }
        strategy = PagedPropertyListingStrategy(**settings)
        logging.info(f"Executing za scraping strategy")
        if strategy.execute_strategy(driver):
            data = strategy.get_data()
            return data
        else:
            raise Exception("Error in strategy")

    def parse_page(self, page: str) -> List[Property]:
        """ parses a single page of html content from the provider and returns the properties as well as the last available page """
        # update referer to point to previous page if we are not on the first one

        page = BeautifulSoup(page, 'html.parser')

        properties: List[Property] = []

        listing_div: Union[Tag, None]
        for listing_div in page.find_all(id=lambda x: x is not None and x.startswith("listing_")):
            _id = listing_div.attrs.get("id").split("_")[1]

            price_per_month = int(listing_div.find(attrs={
                "data-testid": "listing-price"})
                .text
                .strip()
                .removesuffix(" pcm")
                .replace(',', '')
                [1:])

            relative_listing_url = listing_div.find('a', attrs={
                "href": lambda x: x is not None and x.startswith("/to-rent/details")
            }).attrs.get('href')

            listing_url = f"{self.base_url}{relative_listing_url}"

            date_found = datetime.now()

            bedrooms = Za.result_or_default_if_throws(1,
                                                      lambda: int(listing_div.find(
                                                          "span", string=lambda x: x is not None and "Bedrooms" in x).findNextSibling("span").text))

            image_urls: List[Tag] = Za.result_or_none_if_throws("Failed to get image URLS",
                                                                lambda:
                                                                [x.attrs.get("src") for x in listing_div.find_all("img")
                                                                 if "static_agent_logo" not in x.attrs.get("src")])

            address = Za.result_or_none_if_throws("Failed to get address",
                                                  lambda: " ".join([" ".join(x.text.split()).strip() for x in listing_div.find(
                                                      attrs={"data-testid": "listing-title"}).next_siblings if str(x)])
                                                  )

            available_from_text = Za.result_or_default_if_throws(None,
                                                                 lambda: listing_div.find(string=lambda x: x is not None and x.strip(
                                                                 ).startswith("Available")).text)
            if available_from_text is None:
                available_from = None
            else:
                (_, available_from), *_ = search_dates(available_from_text, languages=[
                    'es'], settings={'DATE_ORDER':  'DMY'}) or [(None, None)]

            date_listed_text = Za.result_or_none_if_throws("Failed to get date listed",
                                                           lambda: listing_div.find(string=lambda x: x is not None and x.strip(
                                                           ).startswith("Listed")).text)
            if date_listed_text is None:
                date_listed = None
            else:
                (_, date_listed), *_ = search_dates(date_listed_text, languages=[
                    'es'], settings={'DATE_ORDER':  'DMY'}) or [(None, None)]

            listing_title = Za.result_or_none_if_throws("Failed to get listing description",
                                                        lambda: " ".join(listing_div.find(
                                                            attrs={"data-testid": "listing-title"}).text.split()).strip())

            description = listing_title

            property_type = Za.result_or_none_if_throws(
                "Failed to get property type",
                lambda: Za.read_property_type_from_title(listing_title))
            properties.append(
                Property(_id, listing_url, date_found, property_type=property_type,
                         price_per_month=price_per_month, bedrooms=bedrooms, image_urls=image_urls, address=address,
                         available_from=available_from, date_listed=date_listed,
                         description=description)
            )
        logging.info(
            f"properties found on current page: {[x.short_summary() for x in properties]}")
        return properties
