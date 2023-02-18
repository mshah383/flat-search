import random
from time import sleep


def random_in_range(min: float, max: float):
    range = max - min
    return range * random.random() + min


def sleep_random_range(min: float, max: float):
    time = random_in_range(min, max)
    if time > 0.0001:
        sleep(time)


def binomial_trial(p: float) -> bool:
    """ if p is between 0 and 1, returns true if the binomial trial succeeded """
    if p == 0:
        return False
    elif p == 1:
        return True
    else:
        return random.random() < p
