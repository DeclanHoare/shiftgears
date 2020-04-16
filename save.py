# mud save/load

from auth import Auth, InvalidTokenError
from database import ClientSave, Save, StoryExperienced, Upgrade
from mapping import map_from, map_to
from messagehandler import handler
from myconfig import mappings
from netclass.jsonconverter import from_json

@handler("mud_token_login")
def mud_token_login(connection, contents):
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
	
	# No token means the save isn't ready yet
	if contents["UniteAuthToken"] is None or contents["UniteAuthToken"].strip() == "":
		return
	
	# If the server shuts down, all the clients that were left open
	# will reconnect as soon as it comes back on.  But, they don't
	# bother to re-authenticate on their own, so the server has to
	# prompt them to save to get the copy of the auth token that is
	# in the save.
	if connection.authsession is None:
		try:
			connection.authsession = connection.auth.session(contents["UniteAuthToken"])
		except InvalidTokenError:
			connection.error("Your token is incorrect and you could not be re-authenticated with the server")
		return
	
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
