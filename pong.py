# The original server didn't even know about the pong multiplayer
# protocol, it just relayed "Forward" messages between clients and let
# them sort it all out.  In practice this worked but if anybody with
# a sort of twisted Joker mind ever read the ShiftOS source then this
# could have led to mischief and malice.
# This implementation mediates the protocol to make sure messages are
# only going where they should.  That makes it more complicated but
# on the plus side it's hopefully also more reliable even when
# everyone's playing by the rules.

import datetime

from messagehandler import forwardhandler, handler

class PongMatchmaking:
	def __init__(self):
		self.players = {}
		
		self.current_heartbeat = 0
	def join(self, newcomer):
		for opponent in self.players.values():
			opponent.connection.send_message("pong_handshake_matchmake", newcomer.name)
			newcomer.connection.send_message("pong_handshake_matchmake", opponent.name)
		self.players[newcomer.name] = newcomer
	def leave(self, player):
		try:
			del self.players[player.name]
		except KeyError:
			return
		for opponent in self.players.values():
			opponent.connection.send_message("pong_handshake_left", player.name)
	def heartbeat(self):
		for player in list(self.players.values()): # copy to be able to delete
			if self.current_heartbeat - player.last_heartbeat >= 3:
				player.connection.infobox("Your connection to Pong has timed out.", "Timed out")
				player.leave()
			else:
				player.send_heartbeat()
		self.current_heartbeat += 1
	def handshake(self, leader, follower_name):
		try:
			follower = self.players[follower_name]
		except KeyError:
			return False
		if follower.opponent is not None:
			return False
		
		leader.opponent = follower
		leader.is_leader = True
		follower.opponent = leader
		follower.is_leader = False
		follower.handshake_complete = False
		
		# If the opponent GUID is null-or-whitespace then the client
		# won't send pong_mp_left.  Other than that, the value doesn't
		# matter.
		follower.connection.send_message("pong_handshake_chosen", "_")
		return True

class PongPlayer:
	def __init__(self, connection):
		self.connection = connection
		
		# We have to store this, because it's used as the key sent to
		# the clients to identify each other but it can change at any
		# time.
		self.name = self.connection.authsession.User.DisplayName
		
		# The heartbeat 'freezes' while the server is waiting for the
		# client to finish the handshake.  This means that a
		# mischievous client can't leave someone else hanging by
		# responding to the heartbeats and deliberately ignoring the
		# handshake.  As a bonus it clears up the connection a little.
		self.frozen = False
		self.heartbeat()
		
		self.y = 0
		
		self.connected = True
		self.connection.factory.pong.join(self)
		
		self.opponent = None
	def leave(self):
		self.connected = False
		self.connection.factory.pong.leave(self)
		if self.opponent is not None:
			self.opponent.opponent = None
			
			# In the special situation that the follower leaves before
			# the handshake is complete, the leader is still fit to
			# choose another follower.
			if not self.is_leader and not self.handshake_complete:
				self.opponent.connection.infobox(f"{self.name} is no longer available.", "Matchmaking failed")
			
			# in all other circumstances, including leader leaving
			# part-way through handshake, the other player's state has
			# changed and can't be recovered, so Pong has to quit.
			else:
				self.opponent.connection.send_message("pong_mp_left")
	
	def send_heartbeat(self):
		if not self.frozen:
			self.connection.send_message("pong_handshake_resendid")
	def heartbeat(self):
		if not self.frozen:
			self.last_heartbeat = self.connection.factory.pong.current_heartbeat
	def freeze(self):
		self.frozen = True
	def unfreeze(self):
		self.frozen = False
		self.heartbeat()
	
	def complete_handshake(self):
		if self.is_leader:
			raise ValueError("The handshake can only be completed by a follower")
		
		self.handshake_complete = True
		self.opponent.connection.send_message("pong_handshake_complete", "_")


class PongState:
	def __init__(self, connection):
		self.connection = connection
		self.player = None
	def busy(self):
		return self.player is not None and self.player.connected
	def join(self):
		if self.busy():
			self.connection.infobox("You can't play multiple simultaneous games of online Pong...nobody is that good")
			return
		self.player = PongPlayer(self.connection)
	def leave(self):
		if self.busy():
			self.player.leave()
	def heartbeat(self):
		if self.busy():
			self.player.heartbeat()

# Note that this is a normal handler.  This is sent as a normal
# message only once at the start of matchmaking; after that, it's resent
# as a forward.
@handler("pong_handshake_matchmake")
def pong_handshake_matchmake(connection, contents):
	connection.pong.join()

# We send out a pong_handshake_resendid to every matchmaking player
# every 5 seconds as a heartbeat, and a working client will respond with
# a pong_handshake_matchmake immediately.
@forwardhandler("pong_handshake_matchmake")
def pong_handshake_matchmake_forward(connection, contents, name):
	connection.pong.heartbeat()

@forwardhandler("pong_handshake_chosen")
def pong_handshake_chosen(connection, contents, name):
	if not connection.factory.pong.handshake(connection.pong.player, name):
		connection.infobox(f"{name} is no longer available.", "Matchmaking failed")

@forwardhandler("pong_handshake_complete")
def pong_handshake_complete(connection, contents, name):
	connection.pong.player.complete_handshake()

@forwardhandler("pong_handshake_left")
def pong_handshake_left(connection, contents, name):
	connection.factory.pong.leave(connection.pong.player)

@forwardhandler("pong_mp_setopponenty", int)
def pong_mp_setopponenty(connection, y, name):
	try:
		assert -2147483648 <= y <= 2147483647
	except:
		connection.error("Y co-ordinate out of range")
	
	connection.pong.player.y = y

@forwardhandler("pong_mp_setballpos", str)
def pong_mp_setballpos(connection, point, name):
	if not connection.pong.player.is_leader:
		connection.error("That message can only be used by the leader")
		return
	
	try:
		x, y = point.split(",")
		x = int(x)
		y = int(y)
		assert -2147483648 <= x <= 2147483647
		assert -2147483648 <= y <= 2147483647
	except:
		connection.error("Invalid Point") # har har
	
	connection.pong.player.opponent.connection.send_message("pong_mp_setballpos", f'"{x},{y}"')
	connection.pong.player.opponent.connection.send_message("pong_mp_setopponenty", connection.pong.player.y)
	connection.pong.player.connection.send_message("pong_mp_setopponenty", connection.pong.player.opponent.y)

@forwardhandler("pong_mp_left")
def pong_mp_left(connection, contents, name):
	connection.pong.leave()

@forwardhandler("pong_mp_youwin")
def pong_mp_youwin(connection, contents, name):
	connection.pong.player.opponent.connection.send_message("pong_mp_youwin")

@forwardhandler("pong_mp_youlose")
def pong_mp_youlose(connection, contents, name):
	connection.pong.player.opponent.connection.send_message("pong_mp_youlose")

@forwardhandler("pong_mp_cashedout")
def pong_mp_cashedout(connection, contents, name):
	# The client is already out of here immediately after sending the
	# message.
	opponent = connection.pong.player.opponent
	if opponent is not None:
		opponent.connection.send_message("pong_mp_cashedout")
		opponent.opponent = None
		connection.pong.player.opponent = None


