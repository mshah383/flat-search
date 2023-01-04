"""
Module containing the plain data objects
"""

from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime


@dataclass
class Property():
    """ Contains data about a particular flat found online """

    listing_url: str
    """ the url linking to the add for the property """

    date_found: datetime
    """ the date this property was indexed """

    price_per_month: Optional[int] = None
    """ the price per calendar month without decimals """

    deposit: Optional[int] = None
    """ the initial deposit price without decimals """

    bedrooms: Optional[int] = None
    """ the number of bedrooms inside the property  """

    image_urls: List[str] = []
    """ A list of urls to all the available images of the property """

    address: Optional[str] = None
    """ The address of the property if available """

    available_from: Optional[datetime] = None
    """ the date this property is being advertised for """

    description: str = ""
    """ the description provided for the property """
