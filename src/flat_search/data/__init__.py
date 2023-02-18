"""
Module containing the plain data objects
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional
from datetime import datetime
from time import time

from dataclasses_json import dataclass_json


class PropertyType(Enum):
    FLAT = "flat"
    """ a flat in a larger building sharing walls with other flats """
    STUDIO = "studio"
    """ a one room flat """
    DETACHED_HOUSE = "detached house"
    """ a standalone house """
    TERRACED_HOUSE = "terraced house"
    """ a house connected to other houses """
    ROOM = "room"
    """ a room in a property shared with other rooms and utilities """


@dataclass_json
@dataclass
class Property():
    """ Contains data about a particular flat found online """

    id: str
    """ unique among all other properties from the same provider """

    listing_url: str
    """ the url linking to the add for the property """

    date_found: datetime
    """ the date this property was indexed """

    property_type: PropertyType
    """ the type of this property """

    price_per_month: Optional[int] = None
    """ the price per calendar month without decimals """

    deposit: Optional[int] = None
    """ the initial deposit price without decimals """

    bedrooms: Optional[int] = None
    """ the number of bedrooms inside the property  """

    image_urls: List[str] = field(default_factory=list)
    """ A list of urls to all the available images of the property """

    address: Optional[str] = None
    """ The address of the property if available """

    available_from: Optional[datetime] = None
    """ the date this property is being advertised for """

    date_listed: Optional[datetime] = None
    """ the date this property was listed on the website we are searching through """

    description: str = ""
    """ the description provided for the property """

    def make_random_property():
        """ generates a property instance with randon data """
        from lorem import word, paragraph, sentence
        from random import randint, Random

        RANDOM_IMAGE_URLS = [
            "https://lid.zoocdn.com/u/1200/900/17e60f152629ae93c23da3900e40cae74311c8e0.jpg:p",
            "https://lid.zoocdn.com/u/1200/900/4c47d0c76fd55da441e984b83663babecb6a3770.jpg:p",
            "https://lid.zoocdn.com/u/1200/900/a4cd1785367a53d227ab4c72d745bbf1d996bc09.jpg:p",
            "https://lid.zoocdn.com/u/1200/900/baae1f81c77ec233de9055e883e36709571dd9f1.jpg:p",
            "https://lid.zoocdn.com/645/430/96805cdce251962cc07ed53225ec0ff2d648f386.jpg",
        ]
        RANDOM = Random()

        return Property(
            listing_url="https://www.zoopla.co.uk/to-rent/details/60337626/?search_identifier=69e30057ba2b75d95fbac60db87cceec",
            date_found=datetime.fromtimestamp(time() - randint(0, 60 * 120)),
            price_per_month=randint(500, 5000),
            deposit=randint(1000, 10000),
            bedrooms=randint(1, 5),
            image_urls=RANDOM.choices(RANDOM_IMAGE_URLS, k=randint(0, 4)),
            address=sentence().__next__(),
            available_from=datetime.fromtimestamp(
                time() + randint(0, 60 * 600)),
            description=paragraph().__next__()
        )

    def short_summary(self) -> str:
        """ returns short summary with hyperlinks for command line usage"""
        return f"{self.property_type.name} : {self.address} : {self.listing_url}"


if __name__ == "__main__":
    print(Property.make_random_property())
