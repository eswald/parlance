r'''Test cases for the Parlance internal web server
    Copyright (C) 2009  Eric Wald
    
    This module tests a few pages that make the internal server useful.
    
    Parlance may be used, modified, and/or redistributed under the terms of
    the Artistic License 2.0, as published by the Perl Foundation.
'''#'''

import unittest
from itertools import islice

from pkg_resources import resource_stream
from twisted.web.http import HTTPClient

from parlance.test import fails
from parlance.test.network import NetworkTestCase

class DataPageTestCase(NetworkTestCase):
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
            def make_request(self):
                self.sendCommand("GET", path)
                self.sendHeader("Host", "parlance.example.org")
                self.endHeaders()
            def handleStatus(self, version, status, message):
                self.status = status
            def handleResponse(self, data):
                self.data = data
        
        self.fake_client(FetchProtocol)
        self.manager.process(self.time_limit)
        self.assertContains(fragment, self.factory.client.data)
        self.assertEqual(self.factory.client.status, str(status))
    
    def test_dummy_page(self):
        # /docs/dummy.html should return a 404 error
        self.assertPageContains("/docs/dummy.html", "No Such Resource", 404)
    
    @fails
    def test_syntax_page(self):
        # /docs/syntax.html should load the syntax page
        resource = resource_stream("parlance", "data/syntax.html")
        for line in resource:
            if "version" in line:
                break
        self.assertPageContains("/docs/syntax.html", line)

if __name__ == "__main__":
    unittest.main()
