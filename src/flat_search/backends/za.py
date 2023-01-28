from asyncio import sleep
from datetime import datetime
import os
from typing import Any, Callable, Tuple, Union, List
from flat_search.backends import PropertyDataProvider
from flat_search.data import Property, PropertyType
import requests as r
from fake_useragent import UserAgent
from os import getenv
from fp.fp import FreeProxy
from random import choice, randint
import logging
from bs4 import BeautifulSoup, NavigableString, Tag
import dateparser
from urllib.parse import urlparse


class Za(PropertyDataProvider):
    """ requires ZA_URL_FORMAT env variable to be present.
        requires the following format keys to be in the url:
        - area - one of valid areas
        - location_query - additional location query i.e. postocde
        - price_min
        - price_max
        - page_no - the 1 indexed page number
        """

    def __init__(self, area="London") -> None:
        super().__init__()
        self.area = area
        self.url = getenv("ZA_URL_FORMAT",
                          "set the ZA_URL_FORMAT variable in .env file")
        self.url_kwargs = {
            "area": self.area,
            "location_query": self.location,
            "price_min": self.min_price,
            "price_max": self.max_price,
        }

        self.base_url = "{uri.scheme}://{uri.netloc}/".format(uri=urlparse(
            self.url.format(**self.url_kwargs, page_no=0)))

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
        for property_type in Za.format_property_types(self.property_type_allowlist):
            url += f"&property_sub_type={property_type}"
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

        # try to get all the available pages, they might change last number available dynamically so keep track of that
        current_page, last_page = 1, 1
        all_properties = []
        while current_page <= last_page:
            try:
                new_properties, last_page = self.parse_page(
                    current_page, url, kwargs)
                all_properties.extend(new_properties)
                current_page += 1
                sleep_time = randint(1, 3)
                logging.info(
                    f"Pretending to be human for {sleep_time}s Zzzz...")
                await sleep(sleep_time)
            except Exception as E:
                logging.exception(
                    "Error in parsing page, ignoring further pages untill next attempt")
                return all_properties

        return all_properties

    def parse_page(self, page_no, url, request_kwargs) -> Tuple[List[Property], int]:
        """ parses a single page of html content from the provider and returns the properties as well as the last available page """
        # update referer to point to previous page if we are not on the first one
        if page_no > 1:
            request_kwargs['headers']['Referer'] = url.format(
                **self.url_kwargs, page_no=page_no - 1)

        current_page_url = url.format(**self.url_kwargs, page_no=page_no)
        page = r.get(current_page_url,
                     verify=True, **request_kwargs)
        if not page.ok:
            raise RuntimeError("Couldn't scrape page: {}. Ignoring further pages. status:{}, content: {}",
                               page_no, page.status_code, page.content)
        else:
            logging.info(
                f"Received response for page: {page_no}: {page.status_code}")
            page = BeautifulSoup(page.content, 'html.parser')

        # find number of pages total
        *_, last_page_li = page.find(name="ol").children
        last_page = int(last_page_li.text.strip())

        properties: List[Property] = []

        listing_div: Union[Tag, None]
        for listing_div in page.find_all(id=lambda x: x is not None and x.startswith("listing_")):

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

            available_from = Za.result_or_default_if_throws(None,
                                                            lambda: dateparser.parse(listing_div.find(string=lambda x: x is not None and x.strip(
                                                            ).startswith("Available")).text, languages=['es'], settings={'DATE_ORDER':  'DMY'}))

            date_listed = Za.result_or_none_if_throws("Failed to get date listed",
                                                      lambda: dateparser.parse(listing_div.find(string=lambda x: x is not None and x.strip(
                                                      ).startswith("Listed on")).text, languages=['es'], settings={'DATE_ORDER':  'DMY'}))

            listing_title = Za.result_or_none_if_throws("Failed to get listing description",
                                                        lambda: listing_div.find(
                                                            attrs={"data-testid": "listing-title"}).text)

            description = listing_title

            property_type = Za.result_or_none_if_throws(
                "Failed to get property type",
                lambda: Za.read_property_type_from_title(listing_title))

            properties.append(
                Property(listing_url, date_found, property_type=property_type,
                         price_per_month=price_per_month, bedrooms=bedrooms, image_urls=image_urls, address=address,
                         available_from=available_from, date_listed=date_listed,
                         description=description)
            )

        logging.info(
            f"Properties found on page: {page_no} : {[x.short_summary() for x in properties]}")
        return (properties, last_page)


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(format='%(levelname)s:%(message)s',
                        level=logging.DEBUG)

    async def main():
        backend = Za(area="London").set_min_price("0").set_max_price(
            "1300").set_property_type_allowlist([PropertyType.FLAT]).set_location("NW10")

        return await backend.retrieve_all_properties()

    asyncio.run(main())
