''' PyDip core language tokens
    Copyright (C) 2004-2006 Eric Wald
    Licensed under the Open Software License version 3.0
    
    This module is designed to be used as "from tokens import *".
    Doing so will import all DCSP tokens, with upper-case names,
    including BRA ('(') and KET (')'),
    but not including standard provinces and powers.
'''#'''

from sys import modules

from language import protocol

__all__ = protocol.base_rep.keys()

module = modules[__name__]
for name in __all__:
    setattr(module, name, protocol.base_rep[name])
