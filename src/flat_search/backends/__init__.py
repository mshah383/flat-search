

import json
from typing import List

from flat_search.data import Property, PropertyType
from time import time
from dotenv import load_dotenv
from fp.fp import FreeProxy
# load dotenv if possible
load_dotenv()


class RequestStopwatchLimit():
    """ timer checking a resource is used a maximum number of times within the given time period """

    def __init__(self, period_time_seconds: int, maximum_uses_per_period: int) -> None:
        self.period_time_seconds = period_time_seconds
        self.last_period_start = time()
        self.maximum_uses_per_period = maximum_uses_per_period
        self.uses_left_this_period = self.maximum_uses_per_period

    def consume_and_check_quota(self) -> bool:
        """ reduce counter and return false if quota will be exceeded if the resource is used """
        delta_seconds = time() - self.last_period_start
        if delta_seconds > self.period_time_seconds:
            # reset timer and quota if period ended
            self.last_period_start = time()
            self.uses_left_this_period = self.maximum_uses_per_period
            return True
        else:
            # check we still have uses of the resource left within this time period
            self.uses_left_this_period -= 1
            if self.uses_left_this_period >= 0:
                return True

        return False


class PropertyDataProvider():
    def __init__(self) -> None:
        self.min_price = 0
        self.max_price = 999999
        self.location = ""
        self.property_type_allowlist = [t for t in PropertyType]
        self.request_limiter_minutes = RequestStopwatchLimit(60, 60)
        self.request_limiter_seconds = RequestStopwatchLimit(1, 1)
        self.proxies = FreeProxy(country_id=['GB'], timeout=0.5, anonym=True,
                                 rand=True)

    async def retrieve_all_properties(self) -> List[Property]:
        """ retrieve all properties with the current criteria/filters set while respecting request limits, may throw error if requested too many times.
            :raises:
                ResourceWarning: if used too quickly
        """

        # check we are allowed to send request this second and minute
        if not self.request_limiter_minutes.consume_and_check_quota():
            raise ResourceWarning(
                f"Too many request per second, a maximum of {self.request_limiter_minutes.maximum_uses_per_period} requests per second is allowed.")
        if not self.request_limiter_seconds.consume_and_check_quota():
            raise ResourceWarning(
                f"Too many request per minute, a maximum of {self.request_limiter_seconds.maximum_uses_per_period} requests per minute is allowed.")

        return []

    def set_from_json(self):
        """ looks for file in current directory called `settings.json` to set values from """

        data = json.load(open("settings.json", "r"))
        self.min_price = data["min_price"]
        self.max_price = data["max_price"]
        self.location = data["location"]
        self.property_type_allowlist = [PropertyType[x]
                                        for x in data["property_type_allowlist"]]

    def set_min_price(self, min_price: int) -> "PropertyDataProvider":
        """ set the minimum price filter"""
        self.min_price = min_price
        return self

    def set_max_price(self, max_price: int) -> "PropertyDataProvider":
        """ set the maximum price filter """
        self.max_price = max_price
        return self

    def set_location(self, location: str) -> "PropertyDataProvider":
        """ set the location filter, usually a query string """
        self.location = location
        return self

    def set_property_type_allowlist(self, property_type: List[PropertyType]) -> "PropertyDataProvider":
        """ set the property type filters """
        self.property_type = property_type
        return self
