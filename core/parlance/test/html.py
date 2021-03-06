r'''Test cases for the Parlance internal web server
    Copyright (C) 2009  Eric Wald
    
    This module tests a few pages that make the internal server useful.
    
    Parlance may be used, modified, and/or redistributed under the terms of
    the Artistic License 2.0, as published by the Perl Foundation.
'''#'''

import unittest
from itertools import islice

from twisted.web.http import HTTPClient

from parlance.fallbacks import defaultdict
from parlance.test.network import NetworkTestCase

class WebpageTestCase(NetworkTestCase):
    def setUp(self):
        NetworkTestCase.setUp(self)
        self.connect_server()
        self.time_limit = 5
    
    def assertPageContains(self, path, fragment, status=200):
        class FetchProtocol(HTTPClient):
            def connectionMade(self):
                HTTPClient.connectionMade(self)
                self.data = None
                self.make_request()
                self.headers = defaultdict(list)
            def make_request(self):
                self.sendCommand("GET", path)
                self.sendHeader("Host", "parlance.example.org")
                self.endHeaders()
            def handleStatus(self, version, status, message):
                self.status = status
            def handleHeader(self, key, val):
                self.headers[key].append(val)
            def handleResponse(self, data):
                self.data = data
        
        self.fake_client(FetchProtocol)
        self.manager.process(self.time_limit)
        self.assertContains(fragment, self.factory.client.data)
        self.assertEqual(self.factory.client.status, str(status))

class DataPageTestCase(WebpageTestCase):
    def test_dummy_page(self):
        # /docs/dummy.html should return a 404 error
        self.assertPageContains("/docs/dummy.html", "No Such Resource", 404)
    
    def test_syntax_page(self):
        # /docs/syntax.html should load the syntax page
        line = "<h1>Parlance Message Syntax</h1>"
        self.assertPageContains("/docs/syntax.html", line)
    
    def test_standard_page(self):
        # /docs/standard.cfg should load the standard variant file,
        # with a text/plain mimetype and UTF-8 charset.
        line = "Standard Map"
        self.assertPageContains("/docs/standard.cfg", line)
        self.assertEqual(self.factory.client.headers["Content-Type"],
            ["text/plain; charset=UTF-8"])

class RootPageTestCase(WebpageTestCase):
    def test_dummy_page(self):
        # /dummy.html should return a 404 error
        self.assertPageContains("/dummy.html", "No Such Resource", 404)
    
    def test_root_page(self):
        # Todo: / should return something useful
        self.assertPageContains("/", "No Such Resource", 404)

if __name__ == "__main__":
    unittest.main()
