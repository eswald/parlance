r'''Parlance internal website
    Copyright (C) 2009  Eric Wald
    
    This module sets up the resources for the internal website,
    to be used by the network classes.
    
    Parlance may be used, modified, and/or redistributed under the terms of
    the Artistic License 2.0, as published by the Perl Foundation.
'''#'''

from pkg_resources import resource_stream
from twisted.web.error import NoResource
from twisted.web.resource import Resource

class DataResource(Resource):
    def __init__(self, resource):
        Resource.__init__(self)
        self.resource = resource
    
    def render_GET(self, request):
        return str.join("", self.resource)

class ResourceDirectory(Resource):
    def __init__(self, package, path):
        Resource.__init__(self)
        self.package = package
        self.path = path
    
    def getChild(self, name, request):
        try:
            resource = resource_stream(self.package, self.path + name)
        except IOError:
            return NoResource()
        else:
            return DataResource(resource)

def website(server):
    root = Resource()
    root.putChild("docs", ResourceDirectory("parlance", "data/"))
    return root
