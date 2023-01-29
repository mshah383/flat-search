from asyncio import sleep
from datetime import datetime
from typing import Any, Callable, Tuple, Union, List
from flat_search.backends import PropertyDataProvider
from flat_search.data import Property, PropertyType
import requests as r
from fake_useragent import UserAgent
from os import getenv
from random import randint
import logging
from bs4 import BeautifulSoup, Tag
from dateparser.search import search_dates
from urllib.parse import urlparse

from flat_search.settings import Settings


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
        self.url = getenv("ZA_URL_FORMAT",
                          "set the ZA_URL_FORMAT variable in .env file") + "&is_retirement_home=false"
        url_kwargs = {
            "area": self.settings.za_area,
            "location_query": self.settings.location,
            "price_min": self.settings.min_price,
            "price_max": self.settings.max_price,
        }

        self.base_url = "{uri.scheme}://{uri.netloc}".format(uri=urlparse(
            self.url.format(**url_kwargs, page_no=0)))

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

    async def retrieve_all_properties(self) -> List[Property]:
        """ retrieve all properties with the current criteria/filters set while respecting request limits, may throw error if requested too many times.
                    :raises:
                        Exception: if used too quickly
                """
        await super().retrieve_all_properties()
        # generate new user agent
        ua = UserAgent(browsers=['edge', 'chrome', 'safari']).random

        # kwargs without page number
        url = self.url
        for property_type in Za.format_property_types(self.settings.property_type_allowlist):
            url += f"&property_sub_type={property_type}"

        if PropertyType.ROOM not in self.settings.property_type_allowlist:
            url += f"&is_shared_accommodation=false"

        # select a proxy once per scrape attempt
        proxy = self.proxies.get(True)
        logging.info(f"Selected proxy: {proxy}")
        kwargs = {
            "proxies": {
                "http": proxy
            },
            "headers": {
                'User-Agent': ua,
                'Referer': url.split("?")[0],
            }
        }

        url_kwargs = {
            "area": self.settings.za_area,
            "location_query": self.settings.location,
            "price_min": self.settings.min_price,
            "price_max": self.settings.max_price,
        }

        # try to get all the available pages, they might change last number available dynamically so keep track of that
        current_page, has_more_pages = 1, True
        all_properties = []
        while has_more_pages:
            try:
                new_properties, has_more_pages = self.parse_page(
                    current_page, url, url_kwargs, kwargs)
                all_properties.extend(new_properties)
                current_page += 1
                sleep_time = randint(1, 3)
                logging.info(
                    f"Pretending to be human for {sleep_time}s Zzzz...")
                await sleep(sleep_time)
            except Exception as E:
                logging.error(
                    "Error in parsing page, throwing upwards to prevent incomplete data")
                raise E

        return all_properties

    def parse_page(self, page_no, url, url_kwargs, request_kwargs) -> Tuple[List[Property], bool]:
        """ parses a single page of html content from the provider and returns the properties as well as the last available page """
        # update referer to point to previous page if we are not on the first one
        if page_no > 1:
            request_kwargs['headers']['Referer'] = url.format(
                **url_kwargs, page_no=page_no - 1)

        current_page_url = url.format(**url_kwargs, page_no=page_no)
        page = r.get(current_page_url,
                     verify=True, **request_kwargs)
        if not page.ok:
            raise RuntimeError("Couldn't scrape page: {}. Ignoring further pages. status:{}, content: {}",
                               page_no, page.status_code, page.content)
        else:
            logging.info(
                f"Received response for page: {page_no}: {page.status_code}")
            page = BeautifulSoup(page.content, 'html.parser')

        # figure out if more pages exist
        at_least_one_more_page_navigable = page.find("nav", attrs={"aria-label": "pagination"}
                                                     ).find_all("a")[-1].attrs.get("href", None) is not None
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
                                                      lambda: listing_div.find(
                                                          "span", string=lambda x: x is not None and "Bedrooms" in x).findNextSibling("span").text)

            image_urls: List[Tag] = Za.result_or_none_if_throws("Failed to get image URLS",
                                                                lambda:
                                                                [x.attrs.get("src")
                                                                 for x in listing_div.find_all("img")])

            address = Za.result_or_none_if_throws("Failed to get address",
                                                  lambda: " ".join([x.text for x in listing_div.find(
                                                      attrs={"data-testid": "listing-title"}).next_siblings]))

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
                                                        lambda: listing_div.find(
                                                            attrs={"data-testid": "listing-title"}).text)

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
            f"Properties found on page: {page_no} : {[x.short_summary() for x in properties]}")
        return (properties, at_least_one_more_page_navigable)
