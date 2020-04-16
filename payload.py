
import struct

from twisted.internet.protocol import Protocol

s32 = struct.Struct("<i")

class PayloadStream(Protocol):
	"""'Payloads' are length-prefixed binary blobs used in NetSockets."""
	def __init__(self):
		self.__length = None
		self.__buffer = b""
	def dataReceived(self, data):
		self.__buffer += data
		while True:
			if self.__length is None and len(self.__buffer) >= 4:
				self.__length = s32.unpack(self.__buffer[:4])[0]
				self.__buffer = self.__buffer[4:]
				if self.__length < 0:
					raise ValueError(f"Invalid (negative) payload length {self.__length}")
			if self.__length is not None and len(self.__buffer) >= self.__length:
				payload = self.__buffer[:self.__length]
				self.__buffer = self.__buffer[self.__length:]
				self.__length = None
				self.payloadReceived(payload)
				continue
			break
	def sendPayload(self, data):
		self.transport.write(s32.pack(len(data)) + data)

