from enum import Enum
import logging
import random
from time import sleep
from typing import Callable, List, Tuple

from selenium.webdriver.remote.webdriver import WebDriver

from flat_search.util import binomial_trial, sleep_random_range


class FailureBehaviour(Enum):
    SKIP = 0
    REPEAT = 1
    BREAK = 2


class SkipBehaviour(Enum):
    CONTINUE = 0
    BREAK = 1


class ScrapeStrategy():
    """ a deceptive strategy with 2 goals:
        1) gather data - perform some steps in sequence while traversing the website and gathering data
        2) act human like - scroll randomly, click at listing details etc.

        strategies are represented by markov-like chains where data gathering paths
        are interrupted with defined probabilities to stray from pure data scraping and perform unrelated activities.
    """

    def __init__(self,
                 name: str,
                 probability: float = 1,
                 delay: Tuple[float, float] = None,
                 steps: List["ScrapeStrategy"] = None,
                 on_fail: FailureBehaviour = FailureBehaviour.BREAK,
                 on_skip: SkipBehaviour = SkipBehaviour.CONTINUE) -> None:
        """
            name -- the name of this strategy (shown in logs)
            steps -- if given acts like a parent node whose `_strategy` method is ignored rather it's made up by the sequence of strategies given
            probability -- the probability that this strategy is executed by a parent
            delay: tuple (min seconds,max seconds) of minimum and maximum seconds to wait before executing this strategy
            starter_strategy -- the strategy taken to get to a valid start state, i.e. navigate to the correct page. executed if something goes wrong before this node
            on_fail -- what to do if this strategy fails (default: FailureBehaviour.SKIP)
            on_skip -- what to do if this strategy is not selected for running ? keep going with the rest of the steps or halt the current parent strategy?
        """
        assert (probability <= 1 and probability >= 0)
        self.name = f"({name})"
        assert (self.name != None)
        self.steps = steps
        self.probability = probability
        self.on_fail = on_fail
        self.on_skip = on_skip
        self.delay = delay
        if not self.delay:
            self.delay = (0, 0)

    def log_prefix(self, level, step=None):
        post_string = ""

        if isinstance(step, tuple):
            post_string = f"[{step[0] + 1}/{step[1]}]"
        return '--'*level + f'> {post_string} '

    def execute_strategy(self, driver: WebDriver, level=0) -> bool:
        """ execute the strategy. return the status of execution.

            True implies that no strategies with FailureBeahviour.BREAK have failed
            False implies that a strategy at some point with FailureBehaviour.BREAK has indeed failed

            skipped behaviours or ignored failures do not count as failures!
        """
        assert driver

        if self.steps:
            level += 1

            strategy_idx = 0

            while strategy_idx + 1 <= len(self.steps):
                logging.info(
                    f"{self.log_prefix(level,step=(strategy_idx,len(self.steps)))}Executing step: {strategy_idx + 1} of strategy: {self.name} from page: `{driver.title}`")
                strategy = self.steps[strategy_idx]

                sleep_random_range(*self.delay)

                if binomial_trial(strategy.probability):
                    logging.info(
                        f"{self.log_prefix(level)}Executing: {strategy.name} on page `{driver.title}`")
                    success = strategy.execute_strategy(driver, level=level)

                    if success or strategy.on_fail == FailureBehaviour.SKIP:
                        strategy_idx += 1
                    elif strategy.on_fail == FailureBehaviour.BREAK:
                        return False
                else:
                    logging.info(
                        f"{self.log_prefix(level)}Skipping strategy {strategy.name} with probability {strategy.probability}")
                    if strategy.on_skip == SkipBehaviour.BREAK:
                        logging.info(
                            f"{self.log_prefix(level)}Skipping rest of the steps as well due to skip behaviour")
                        break
                    else:
                        strategy_idx += 1

            return True
        else:
            try:
                self._strategy(driver, level + 1)
                return True
            except Exception as E:
                logging.exception(
                    f"Error in strategy : {self}.")
                return False

    def _strategy(self, driver: WebDriver, level: int = 0):
        """ the strategy to be implemented by each individual implementation, do not override the execute function unless you know what you are doing """
        raise NotImplementedError()

    def __str__(self) -> str:
        if self.steps:
            return "[" + ",".join([x.__str__() for x in self.steps]) + "]"
        else:
            return self.name
