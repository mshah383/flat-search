import logging
import random
from typing import *
from flat_search.data import Property
from flat_search.scraping import ScrapeStrategy, SkipBehaviour
from selenium.webdriver.remote.webdriver import WebDriver

from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.common.keys import Keys
from flat_search.util import binomial_trial, random_in_range, sleep_random_range


class ArbitraryStrategy(ScrapeStrategy):
    """ scraping strategy backed by a lambda """

    def __init__(self, name: str, behaviour: Callable[[WebDriver], None], *args, **kwargs) -> None:
        super().__init__(name, *args, **kwargs)
        self.behaviour = behaviour

    def _strategy(self, driver: WebDriver, level: int):
        self.behaviour(driver)


class LoopWhile(ScrapeStrategy):
    """ executes its steps in a loop untill the given condition is satisfied or the steps fail.

        if the condition is satisfied *before* any of the steps are executed, no action will be taken.

        Optionally performs post-loop cleanup action before the exit condition is checked.

        i.e.:
        ```python
        while condition(driver):
            ... # execute steps
            cleanup(driver)
        ```
    """

    def __init__(self, name: str, condition: Callable[[WebDriver, int, int], bool] = None, cleanup: Callable[[WebDriver, int, int], None] = None, *args, **kwargs) -> None:
        """
            condition -- the condition checked at the *beginning* of each iteration if None loops untill failure
            cleanup -- optional cleanup function executed at the end of the loop, should this fail, the whole strategy fails
        """
        super().__init__(name, *args, **kwargs)
        self.condition = condition
        self.cleanup = cleanup
        self.index = 0

    def ordinal(self, n: int) -> str:
        """ return the english ordinal for a number i.e. 1st, 2nd, 3rd etc"""
        return "%d%s" % (
            n, "tsnrhtdd"[(n//10 % 10 != 1)*(n % 10 < 4)*n % 10::4])

    def execute_strategy(self, driver: WebDriver, level=0) -> bool:
        try:
            while self.condition(driver, self.index, level):
                logging.info(
                    f"{self.log_prefix(level)}Condition satisfied, looping for the {self.ordinal(self.index + 1)} time")
                if not super().execute_strategy(driver, level + 1):
                    return False
                self.cleanup(driver, self.index, level)
                if self.delay:
                    sleep_random_range(*self.delay)
                self.index += 1
            else:
                logging.info(
                    f"{self.log_prefix(level)}Condition failed, breaking loop")
            return True
        except Exception as E:
            logging.exception(
                f"Exception in LoopUntill cleanup or condition function")
            return False


class NavigateTo(ScrapeStrategy):
    """ Navigate to arbitrary url """

    def __init__(self, url: str, *args, **kwargs) -> None:
        super().__init__(f"Navigate to {url}", *args, **kwargs)
        self.url = url

    def _strategy(self, driver: WebDriver):
        driver.get(self.url)


class PagedPropertyListingStrategy(ScrapeStrategy):
    """ a scraping approach for property websites where the listings are available via one listing directory which can have multiple pages, and where clicking a listing takes you to a `detail` view.

        This approach will go through the following steps:

        1) warmup/query - navigate to `listing` directory via legitimate means i.e. type out the query, press search etc
        2) scroll through - scroll through the directory to get complete idea of the available listings
            2a) while scrolling occasionally click on some listings and scroll on the detail page as well
            2b) while scrolling occasionally try a random query from predefined options and scroll there without getting any data
        3) go to next page, then repeat from 2

     """

    def __init__(self,
                 #  warmup/query settings
                 query_url: str,
                 query_decoy_queries: List[str],
                 query_decoy_probability: float,
                 query_decoy_max: int,
                 query_true_query: str,
                 query_textbox_locator: Tuple[By, str],
                 query_btn_locator: Tuple[By, str],
                 # random walk settings
                 walk_listing_locator: Tuple[By, str],
                 walk_listing_look_probability: float,
                 walk_listing_click_probability: float,
                 walk_listing_look_delay: Tuple[float, float],
                 walk_next_page_btn_locator: Tuple[By, str],
                 walk_query_pages_max: int,
                 # parsing settings
                 parse_function: Callable[[str], List[Property]],
                 *args, **kwargs) -> None:
        """
            query_url -- the url at which we find query textbox and submit button
            query_decoy_queries -- the queries from which we do not want to retrieve any data, but want to act more natural with
            query_decoy_probability -- the probability each individual decoy will be used
            query_decoy_max -- the maximum number of decoys to use each time
            query_decoy_walk_probability -- the probability that a given decoy will be scrolled through given that it was selected to run
            query_true_query -- the actual query we want to retrieve data from
            query_textbox_locator -- the locator used to navigate to a textbox on the `query_url`
            query_btn_locator -- the locator used to navigate to the submit button on the `query_url`
            walk_listing_locator -- once a query is entered this locator is used to identify individual listings (should be many)
            walk_listing_look_probability -- the probability that we `look` at one the listings (independent)
            walk_listing_click_probability -- the probability, given that we `looked` at one of the listings, that we'll click and scroll through for details
            walk_listing_look_delay -- if we `look` at one of the listings, the time we delay for to act like we're looking
            walk_next_page_btn_locator -- the locator for the next page button, if one cannot be found it is assumed this is the last page
            walk_query_pages_max -- the number of pages to walk through at most
            parse_function -- the method to use to parse listing data once on one of the query listing pages (the main working horse)
            listing_url -- either a plain url for the listing page if it's just one page, or a callable which given a page number returns the url of that page
        """
        self.walk_query_pages_max = walk_query_pages_max
        self.data = []
        steps = []
        no_decoys = random.randint(0, query_decoy_max)
        logging.info(
            f"{self.log_prefix(0)}Number of decoys chosen: {no_decoys}")
        decoy_queries_chosen = random.sample(
            query_decoy_queries, k=no_decoys)

        for idx, query in enumerate([*decoy_queries_chosen, query_true_query]):
            # fake queries have an equal chance of happening
            if idx + 1 <= len(decoy_queries_chosen):
                probability_enter_query = query_decoy_probability
                # we only parse data in case of real query
                probability_scrape = 0
                prefix = "Decoy"
                max_pages = 1

            else:
                # real query always gets looked at fully, and gets a full walk cuz why not
                probability_enter_query = 1
                probability_scrape = 1
                prefix = "True"
                max_pages = walk_query_pages_max

            steps.append(
                ScrapeStrategy(name=f"{prefix} Query: `{query}`", delay=(6, 10), steps=[
                    EnterPropertyQuery(query_url, query, query_textbox_locator,
                                       query_btn_locator, delay=(1, 3), probability=probability_enter_query,
                                       on_skip=SkipBehaviour.BREAK),  # skip other steps if we don't enter query
                    LoopWhile(name=f"Scraping page",
                              condition=lambda d, i, l: self.has_clickable_next_page_btn(
                                  d, i, walk_next_page_btn_locator, l, max_pages=max_pages),
                              cleanup=lambda d, i, l: self.click_next_page_btn(
                                  d, i, walk_next_page_btn_locator, l),
                              delay=(1, 3),
                              steps=[
                                  ArbitraryStrategy(
                                      name="Parse Data", behaviour=lambda d: self.data.extend(parse_function(d.page_source)), probability=probability_scrape),
                                  ListingPageRandomWalk(walk_listing_locator, walk_listing_look_probability,
                                                        walk_listing_click_probability, walk_listing_look_delay, delay=(1, 3))
                              ])
                ])
            )
        # order not important make it more random
        random.shuffle(steps)

        super().__init__(
            f"Scraping `{query_url}`", *args, steps=steps, **kwargs)

    def has_clickable_next_page_btn(self, driver: WebDriver, i: int, btn_locator, level: int, max_pages: int):
        if i + 1 > max_pages:
            logging.info(
                f"{self.log_prefix(level)}Condition: Scraped enough pages.")
            return False
        try:
            WebDriverWait(driver, 5).until(
                expected_conditions.element_to_be_clickable(btn_locator))
            logging.info(
                f"{self.log_prefix(level)}Condition: found next page button with locator: {btn_locator} on page {i + 1}.")
            return True
        except:
            logging.info(
                f"{self.log_prefix(level)}Condition: Could not find next page button with locator: {btn_locator} on page {i + 1}.")
            return False

    def click_next_page_btn(self, driver: WebDriver, i, btn_locator, level: int):
        elem = driver.find_element(*btn_locator)
        ActionChains(driver).scroll_to_element(elem).perform()
        elem.click()

    def get_data(self) -> List[Property]:
        return self.data


class EnterPropertyQuery(ScrapeStrategy):
    """ enter website, navigate to textbox, type in query, submit.

        fails if it cannot find element or enter text into it.
    """

    def __init__(self, url: str, query: str, textbox_locator: Tuple[By, str], btn_locator: Tuple[By, str], *args, **kwargs) -> None:
        super().__init__(
            f"EnterQuery: `{query}`", *args, **kwargs)
        self.url = url
        self.query = query
        self.textbox_locator = textbox_locator
        self.btn_locator = btn_locator

    def _strategy(self, driver: WebDriver, level: int):
        # navigate to website
        logging.info(
            f"{self.log_prefix(level)}Navigating to home page: {self.url}")
        driver.get(self.url)

        logging.info(f"{self.log_prefix(level)}waiting for text box to load")
        WebDriverWait(driver, 10).until(
            expected_conditions.presence_of_element_located(self.textbox_locator))

        # enter query into textbox
        textbox = driver.find_element(*self.textbox_locator)
        logging.info(
            f"{self.log_prefix(level)}Using textbox locator: {self.textbox_locator} found: {(textbox.tag_name,textbox.get_attribute('id'))}")

        action = ActionChains(driver).scroll_to_element(
            textbox).move_to_element(textbox).click(textbox)
        # send keys in a human like manner (average delay between keystrokes is 0.167ms)
        for c in self.query:
            action = action.send_keys(c).pause(
                (random.random() * 0.05) + 0.167)
        action.perform()

        logging.info(f"{self.log_prefix(level)}waiting for button to load")
        WebDriverWait(driver, 10).until(
            expected_conditions.presence_of_element_located(self.btn_locator))

        # find button to submit and click it
        button = driver.find_element(*self.btn_locator)
        logging.info(
            f"{self.log_prefix(level)}Using button locator: {self.btn_locator} found: {(button.tag_name,button.get_attribute('id'))}")

        button.click()


class ListingPageRandomWalk(ScrapeStrategy):
    """ Scrolls through listing page and randomly goes into listing details """

    def __init__(self, listing_locator: Tuple[By, str], listing_look_probability: float, listing_click_probability: float, look_delay: Tuple[float, float] = None, *args, **kwargs) -> None:
        super().__init__("Scroll", *args, **kwargs)
        self.listing_locator = listing_locator
        self.listing_look_probability = listing_look_probability
        self.listing_click_probability = listing_click_probability
        self.look_delay = look_delay
        if not self.look_delay:
            self.look_delay = (0, 0)

    def _strategy(self, driver: WebDriver, level: int):

        # beep boop i am a human, i scroll through me listings
        # each listing has a chance of being looked at in detail and a chance of being selected

        index = 0
        listings = []
        while True:

            if not listings:
                logging.info(
                    f"{self.log_prefix(level)}waiting for listing elements")
                WebDriverWait(driver, 10).until(
                    expected_conditions.presence_of_all_elements_located(self.listing_locator))

                listings = driver.find_elements(*self.listing_locator)
                logging.info(
                    f"{self.log_prefix(level)}Using locator: {self.listing_locator} found: {[(l.tag_name, l.get_property('id')) for l in listings]} ")

            if index + 1 > len(listings):
                break

            listing = listings[index]
            #  scroll to the listing
            logging.info(
                f"{self.log_prefix(level)}Scrolling to: {listing.get_property('id')} at {listing.location}")

            ActionChains(driver).scroll_to_element(
                listing).pause(random_in_range(0.1, 0.5)).perform()
            index += 1
            if binomial_trial(self.listing_look_probability):
                logging.info(
                    f"{self.log_prefix(level)}Looking closer at: {listing.get_property('id')}")
                #  look at it a wee while
                sleep_random_range(*self.look_delay)

                if binomial_trial(self.listing_click_probability):
                    logging.info(
                        f"{self.log_prefix(level)}Clicking: {listing.get_property('id')}")
                    #  the action equivalent doesn't work
                    listing.click()
                    sleep_random_range(4, 6)
                    ActionChains(driver).send_keys(Keys.ARROW_DOWN).perform()
                    sleep_random_range(0.1, 0.7)
                    ActionChains(driver).send_keys(Keys.ARROW_UP).perform()
                    sleep_random_range(0.1, 0.7)

                    logging.info(
                        f"{self.log_prefix(level)}Going back")
                    driver.back()
                    sleep_random_range(2, 5)
                    listings = []
