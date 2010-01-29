r'''Parlance internal website
    Copyright (C) 2009  Eric Wald
    
    This module sets up the resources for the internal website,
    to be used by the network classes.
    
    Parlance may be used, modified, and/or redistributed under the terms of
    the Artistic License 2.0, as published by the Perl Foundation.
'''#'''

from twisted.web.error import NoResource
from twisted.web.resource import Resource

class Website(Resource):
    def getChild(self, name, request):
        return NoResource()
