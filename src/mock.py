import json
import os
from sys import argv
import sys
from typing import Any, Dict
from uuid import uuid4
import requests
from flask import request

from flask import Flask, jsonify, render_template
from threading import Thread
import logging
logging.basicConfig(level=logging.DEBUG)


def view(template, url):
    print(f"Routing via: {url}, returning: {template}")
    return lambda *args, **kwargs: render_template(
        template, *args, url=url, **kwargs)


class MockServer(Thread):
    def __init__(self, mappings: Dict[str, str], port=5000):
        super().__init__()
        self.port = port
        self.app = Flask(__name__, template_folder="../mocks")
        self.url = "http://localhost:%s" % self.port

        @self.app.before_request
        def before_request():
            ip_addr = request.environ.get(
                'HTTP_X_FORWARDED_FOR', request.remote_addr)
            logging.info(
                f"IP_DEDUCED: {ip_addr}, HEADERS: {request.headers} ")
        for mapping in mappings:
            print(mapping)
            self.app.add_url_rule(mapping["pattern"], mapping["template"], view_func=view(
                mapping["template"], self.url))
        print(self.app.view_functions)
        print(self.app.url_map)

    def run(self):
        self.app.run(port=self.port)


if __name__ == "__main__":

    if len(argv) == 1:
        print("requires path to mock file as argument")
        sys.exit(1)
    mock_file = argv[1]
    with open(mock_file, "r") as f:
        server = MockServer(json.load(f))
        server.run()
