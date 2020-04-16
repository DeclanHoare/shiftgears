
import traceback
import uuid

from twisted.internet.protocol import Factory

from auth import Auth
from database import DbSession
from netclass import netclass_root, jsonconverter
from servermessage import ServerMessage, ServerMessageStream

import pong
import save
from messagehandler import handlers

class MudConnection(ServerMessageStream):
	def __init__(self, factory, addr):
		self.factory = factory
		self.addr = addr
		self.authsession = None
		super().__init__()
	def connectionMade(self):
		self.dbsession = DbSession()
		
		self.pong = pong.PongState(self)
		
		self.auth = Auth(self.dbsession, self.addr.host)
		print(f"{self.addr.host} connected.")
		self.send_message("Welcome", str(uuid.uuid4()))
		
		# If the server shuts down, all the clients that were left open
		# will reconnect as soon as it comes back on.  But, they don't
		# bother to re-authenticate on their own, so the server has to
		# prompt them to save to get the copy of the auth token that is
		# in the save.  When the client joins on its own startup,
		# and authenticates anyway, hopefully this won't matter...
		#self.run_command("sos.save")
		# but it is commented out cause the lua script doesn't work
	def connectionLost(self, reason):
		print(f"{self.addr.host} disconnected.")
		self.closing = True
		self.pong.leave()
		self.dbsession.close()
	def serverMessageReceived(self, message):
		if message.Name not in ["pong_mp_setballpos", "pong_mp_setopponenty"]:
			print(f"{self.addr.host}: {message.Name}({repr(message.Contents)})")
		if message.Name in handlers:
			try:
				handlers[message.Name](self, message.Contents)
				self.dbsession.commit()
			except:
				self.dbsession.rollback()
				self.error(traceback.format_exc())
				traceback.print_exc()
		else:
			self.error(f"Unimplemented message {message.Name}.  Thanks for using Shift Gears!")
	
	def send_message(self, name, contents = None, guid = None):
		if contents is not None and not isinstance(contents, str):
			contents = jsonconverter.to_json(contents)
		guid = str(guid)
		self.sendServerMessage(ServerMessage(name, contents, guid))
	
	def error(self, message):
		# The content of the Error message is deserialised at the other
		# end as an Exception, but only the Message member is read.
		self.send_message("Error", {"ClassName":"System.Exception","Message":message,"Data":None,"InnerException":None,"HelpURL":None,"StackTraceString":None,"RemoteStackTraceString":None,"RemoteStackIndex":0,"ExceptionMethod":None,"HResult":-2146233088,"Source":None})
	
	# executes Lua code on the client...its that easy
	def run(self, script):
		self.send_message("run", {"script": script})
	
	# executes a ShiftOS command on the client
	def run_command(self, cmd):
		# We don't use trm_invokecommand because it expects the prompt
		# to be sent to it before the command and it's not always
		# feasible to figure out what the prompt is.
		self.run(f"sos.runCommand({repr(cmd)})")
	
	def infobox(self, msg, title = "MUD"):
		self.invoke_command("infobox.show" + jsonconverter.to_json({"title": title, "msg": msg}))

class MudConnectionFactory(Factory):
	def __init__(self):
		self.pong = pong.PongMatchmaking()
	def buildProtocol(self, addr):
		return MudConnection(self, addr)
