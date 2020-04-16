
from netclass.jsonconverter import from_json, to_json
from servermessage import ServerMessage

handlers = {}
forwardhandlers = {}

def handler(name, t = None, dct = handlers):
	def decorator(fun):
		dct[name] = (fun if t is None
			else lambda conn, c, *a: fun(conn, from_json(t, c), *a))
		return fun
	return decorator

def forwardhandler(name, t = None):
	return handler(name, t, dct = forwardhandlers)

# "Forward" messages are meant to be sent to other clients, and the
# original server did this without validating them at all.  This
# gives clients all the same power over each other as the server has
# over them, all the way up to arbitrary code execution...not a good
# idea.  Instead forwards are treated as just a different kind of
# message for the server to handle.  Forward-handlers get the GUID
# which in this case is a target, unlike normal handlers, where it is
# discarded because it is on the source connection.
@handler("mud_forward", ServerMessage)
def mud_forward(connection, contents):
	if contents.Name in forwardhandlers:
		return forwardhandlers[contents.Name](connection, contents.Contents, contents.GUID)

