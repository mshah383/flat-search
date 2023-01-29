

import json
from typing import List

from flat_search.data import Property, PropertyType
from time import time
from dotenv import load_dotenv
from fp.fp import FreeProxy

from flat_search.settings import Settings
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
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
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
