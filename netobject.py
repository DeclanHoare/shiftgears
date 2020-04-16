
import io

from netclass import netclass, binaryformatter
from payload import PayloadStream

NetObject = netclass("NetSockets.NetObject",
	"NetSockets, Version=1.1.0.0, Culture=neutral, PublicKeyToken=null",
	[(str, "Name"), (object, "Object")])

class NetObjectStream(PayloadStream):
	def payloadReceived(self, payload):
		with io.BytesIO(payload) as buf:
			obj = binaryformatter.deserialise(buf)
		if not isinstance(obj, NetObject):
			raise TypeError(f"An object was received on the NetObjectStream of type {type(obj)}")
		self.netObjectReceived(obj)
	def sendNetObject(self, obj):
		if not isinstance(obj, NetObject):
			raise TypeError(f"The NetObjectStream can only send NetObject, not {type(obj)}")
		with io.BytesIO() as buf:
			binaryformatter.serialise(buf, obj)
			self.sendPayload(buf.getvalue())
