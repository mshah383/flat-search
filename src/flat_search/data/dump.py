import os
from typing import List
from flat_search.data import Property
import logging
import json
from os.path import join
from datetime import datetime


def dump_properties(properties: List[Property]) -> str:
    """ dump properties to file and return path to the file written """

    now = datetime.now()
    filename = now.strftime('%Y-%m-%d_%H-%M-%S.json')
    path = join("data", filename)
    logging.info(
        f'dumping properties to json file at {path}: {[x.short_summary() for x in properties]}')
    logging.info(f"Total: {len(properties)} properties being dumped.")
    os.makedirs(os.path.dirname(path), exist_ok=True)

    try:
        dump = Property.schema().dump(properties, many=True)
        ids = {x.id: i for i, x in enumerate(properties)}

        with open(path, 'w') as f:
            json.dump({
                "properties": dump,
                "ids": ids
            }, f, indent=4)
    except:
        logging.exception("Exception in writing to file")
    return path
