
from datetime import datetime, timedelta
import io
import secrets
import socket

from sqlalchemy.orm.exc import NoResultFound

from database import AuthSession
from mapping import map_from, map_to
from messagehandler import handler
from myconfig import config, mappings
from netclass.jsonconverter import from_json

class InvalidTokenError(Exception):
	pass

class Auth:
	def __init__(self, dbsession, addr):
		self.dbsession = dbsession
		self.addr = addr
	
	def session(self, token):
		try:
			session = self.dbsession.query(AuthSession).filter_by(Token = token).one()
		except NoResultFound:
			raise InvalidTokenError()
		session.LastUsed = datetime.utcnow()
		session.LastIP = self.addr
		return session

	def create_session(self, user, app_name, app_description, version):
		session = AuthSession()
		session.Token = secrets.token_urlsafe()
		session.User = user
		session.AppName = app_name
		session.AppDesc = app_description
		session.Version = version
		
		session.Created = session.LastUsed = datetime.utcnow()
		session.LastIP = self.addr
		self.dbsession.add(session)
		return session


@handler("mud_token_login")
def mud_token_login(connection, contents):
	if connection.authsession is not None:
		connection.error("You're already logged in and tried to log in again.")
		return
	try:
		connection.authsession = connection.auth.session(contents)
		user = connection.authsession.User
		save = user.Save
		if save is None:
			connection.send_message("mud_login_denied")
		else:
			data = {"Upgrades": {u.Name: u.Installed for u in save.Upgrades},
					"CurrentLegions": [], #NYI
					"UniteAuthToken": connection.authsession.Token,
					"StoriesExperienced": [s.Name for s in save.StoriesExperienced],
					"Users": [map_to(u, mappings["ClientSave"]) for u in save.Users]}
			data.update(map_to(user, mappings["UserSave"]))
			data.update(map_to(save, mappings["Save"]))
			connection.send_message("mud_savefile", data)
	except InvalidTokenError:
		connection.send_message("mud_login_denied")

@handler("mud_save", dict)
def mud_save(connection, contents):
	user = connection.authsession.User
	save = user.Save
	if save is None:
		save = Save()
		user.Save = save
	map_from(user, mappings["UserSave"], contents)
	map_from(save, mappings["Save"], contents)
	connection.dbsession.query(Upgrade).filter_by(Save = save).delete()
	if contents["Upgrades"] is not None:
		for k, v in contents["Upgrades"].items():
			connection.dbsession.add(Upgrade(Name = k, Installed = v, Save = save))
	connection.dbsession.query(StoryExperienced).filter_by(Save = save).delete()
	if contents["StoriesExperienced"] is not None:
		for v in contents["StoriesExperienced"]:
			connection.dbsession.add(StoryExperienced(Name = v, Save = save))
	if contents["Users"] is not None:
		users_new = {u["Username"]: u for u in contents["Users"]}
		for usr in connection.dbsession.query(ClientSave).filter_by(Save = save):
			if usr.Username in users_new:
				map_from(usr, mappings["ClientSave"], users_new[usr.Username])
				del users_new[usr.Username]
			else:
				connection.dbsession.delete(usr)
		for data in users_new.values():
			usr = ClientSave(Save = save)
			map_from(usr, mappings["ClientSave"], data)
			connection.dbsession.add(usr)


