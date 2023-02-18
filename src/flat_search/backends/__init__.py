import logging
import os
import json
from typing import Dict, List, Tuple
from fake_useragent import UserAgent

from flat_search.data import Property
from time import time
from dotenv import load_dotenv
from selenium.webdriver import FirefoxOptions
from seleniumwire import webdriver
from seleniumwire.request import Request as SWRequest
from selenium.webdriver.remote.webdriver import WebDriver
from flat_search.email import send_error_email
from flat_search.settings import Settings
import requests
from urllib.parse import ParseResult, urlparse
from copy import deepcopy
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


class Proxy():
    def __init__(self, url: str, timeout=3, used_times=0, times_down=0, total_failures=0) -> None:
        self.url = urlparse(url)
        self.timeout = timeout
        self.used_times = used_times
        self.times_down = times_down
        self.total_failures = total_failures

    def check_proxy(self) -> bool:
        try:
            url = f'https://www.toolsvoid.com/proxy-test/'

            protocol = self.url.scheme
            logging.info(
                f"Checking {protocol} proxy {self.url.hostname}:{self.url.port} with timeout: {self.timeout}s")
            headers = {
                'User-Agent': UserAgent().random
            }
            proxies = {}
            if protocol == 'http':
                proxies['http'] = self.url.geturl()
            if protocol == 'https':
                proxies['https'] = self.url.geturl()
            with requests.get(url, proxies=proxies, timeout=self.timeout, headers=headers) as r:
                logging.info(f"Got response: {r}")
                return r.text.count("NO PROXY DETECTED") == 1
        except requests.exceptions.RequestException as E:
            logging.info(f"Timed out. with exception: {E}")
            self.times_down += 1
        return False

    def add_failure(self):
        self.total_failures += 1

    def get_proxies_dict(self) -> Dict:
        protocol = self.url.scheme
        proxies = {}
        if protocol == 'http':
            proxies['http'] = self.url.geturl()
        if protocol == 'https':
            proxies['https'] = self.url.geturl()
        return proxies

    def get_and_use(self) -> ParseResult:
        self.used_times += 1

        return self.url


class PropertyDataProvider():
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

        self.request_limiter_minutes = RequestStopwatchLimit(60, 60)
        self.request_limiter_seconds = RequestStopwatchLimit(1, 1)
        self.proxies: List[Proxy] = []
        if not settings.no_proxy:
            try:
                with open('proxies.json') as f:
                    for p in json.load(f):
                        self.proxies.append(Proxy(
                            str(p['url']),
                            timeout=int(p.get('timeout', 3)),
                            used_times=int(p.get('used_times', 0)),
                            times_down=int(p.get('times_down', 0)),
                            total_failures=int(p.get('total_failures', 0))
                        ))
            except Exception as E:
                logging.exception(
                    "Exception in opening proxies.json file, no_proxy setting is off")
                raise E

    def update_proxy_file(self):
        with open('proxies.json', 'w') as f:
            output = [x.__dict__ for x in deepcopy(self.proxies)]
            for dict in output:
                dict['url'] = dict['url'].geturl()
            json.dump(output, f, indent=4)

    def make_fake_user(self) -> Tuple[WebDriver, Proxy]:

        # setup driver
        opts = FirefoxOptions()
        opts.add_argument("--headless")
        if os.getenv("ENV", "dev") == "dev":
            service_args = ['--marionette-port', '2828', '--connect-existing']
        else:
            service_args = []

        profile = webdriver.FirefoxProfile()

        # choose random user agent
        user_agent = UserAgent().random
        logging.info(f"Setting User-Agent to: {user_agent}")
        proxy: Proxy = None
        if not self.settings.no_proxy:
            # rotate proxies to spread use equally amongst those which were not failed
            non_failed = [x for x in self.proxies if x.total_failures == 0]
            if not non_failed:
                raise Exception(
                    "`no_proxy` setting is off and no clean proxies could be found (total_failures == 0)")

            # prefer least used proxies with smallest number of timeouts (10 timeouts is equivalent to 1 used time as a weight)
            for p in sorted(non_failed, key=lambda x: x.used_times*10 + x.times_down):
                if p.check_proxy():
                    proxy = p
                    break

            if proxy:
                url = proxy.get_and_use()
                logging.info(f"Found proxy: {url.hostname}:{url.port}")
                self.update_proxy_file()
            else:
                self.update_proxy_file()
                raise Exception(
                    "All proxies timed out, replace unusable proxies")

        driver = webdriver.Firefox(
            options=opts, service_args=service_args, seleniumwire_options={
                'proxy': proxy.get_proxies_dict() if proxy else {}
            })

        def interceptor(request: SWRequest):
            if request.headers.get('user-agent', None):
                request.headers.replace_header('user-agent', user_agent)

        driver.request_interceptor = interceptor

        driver.implicitly_wait(10)
        return (driver, proxy)

    async def _retrieve_all(self, driver: WebDriver, proxy: Proxy) -> List[Property]:
        raise NotImplementedError("Implement _retrieve_all!")

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

        driver, proxy = self.make_fake_user()

        try:
            properties = await self._retrieve_all(driver, proxy)
            logging.info(f"found {len(properties)} properties.")
            driver.quit()
            return properties
        except Exception as E:
            proxy.add_failure()
            self.update_proxy_file()
            send_error_email(self.settings, proxy, E)
            logging.exception(
                f"Exception in backend: {self.__class__.__name__}, marking proxy as failure")
            raise E
