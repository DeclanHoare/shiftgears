#!/usr/bin/env python3
from twisted.internet.endpoints import TCP4ServerEndpoint
from twisted.internet import reactor

from mud import MudConnectionFactory

endpoint = TCP4ServerEndpoint(reactor, 13370)
endpoint.listen(MudConnectionFactory())
reactor.run()


