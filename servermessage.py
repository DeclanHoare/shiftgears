
from netclass import netclass
from netobject import NetObject, NetObjectStream

ServerMessage = netclass("ShiftOS.Objects.ServerMessage",
	"ShiftOS.Objects, Version=1.0.0.0, Culture=neutral, PublicKeyToken=null",
	[(str, "Name"), (str, "Contents"), (str, "GUID")])

class ServerMessageStream(NetObjectStream):
	def netObjectReceived(self, obj):
		if not isinstance(obj.Object, ServerMessage):
			raise TypeError(f"An object was received on the ServerMessageStream of type {type(obj.Object)}")
		
		self.serverMessageReceived(obj.Object)
	
	def sendServerMessage(self, message):
		if not isinstance(message, ServerMessage):
			raise TypeError(f"The ServerMessageStream can only send ServerMessage, not {type(obj)}")
		
		# Although the real ShiftOS fills in the Name field on the
		# NetObject, it does not ever read it, so it's not really
		# part of the protocol.
		self.sendNetObject(NetObject(None, message))

