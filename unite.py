import base64
import re
import traceback
import uuid

import bcrypt
import flask
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import NoResultFound

from auth import Auth, InvalidTokenError
from database import User, DbSession, ValidationError
import mapping
from myconfig import mappings

app = flask.Flask(__name__)

def cb_decorator(fn):
	return lambda *args, **kwargs: lambda cb: fn(*args, **kwargs, cb = cb)

@cb_decorator
def db_route(path, cb):
	@app.route(path, endpoint = path)
	def db_handler(*args, **kwargs):
		dbsession = DbSession()
		try:
			ret = cb(*args, **kwargs, dbsession = dbsession)
		except (ValidationError, NoResultFound):
			traceback.print_exc()
			return flask.Response(status = 400)
		try:
			dbsession.commit()
		except IntegrityError as ex:
			# 1062 is the SQL error code for duplicate entry.
			# That's a user input error, but if we get some other kind
			# of integrity error, then it's a server error.
			if ex.orig.args[0] == 1062:
				return flask.Response(status = 400)
			else:
				raise
		dbsession.close()
		return ret
	return db_handler

# /Auth/ endpoints use basic authentication and create new tokens.
@cb_decorator
def auth_route(path, cb):
	@db_route(f"/Auth{path}")
	def auth_handler(*args, dbsession, **kwargs):
		try:
			kind, value = flask.request.headers["Authentication"].split(" ")
			assert kind == "Basic"
			email, password = base64.b64decode(value).decode().split(":")
		except (KeyError, ValueError, AssertionError):
			print("no basic auth")
			return flask.Response(status = 401)
		email = email.strip()
		return cb(*args, **kwargs, dbsession = dbsession, email = email, password = password)
	return auth_handler

# /API/ endpoints use token authentication and operate as a
# Unite user.
@cb_decorator
def api_route(path, cb):
	@db_route(f"/API{path}")
	def api_handler(*args, dbsession, **kwargs):
		try:
			kind, token = flask.request.headers["Authentication"].split(" ")
			assert kind == "Token"
			auth = Auth(dbsession, flask.request.remote_addr)
			authsession = auth.session(token)
		except (KeyError, ValueError, AssertionError, InvalidTokenError):
			return flask.Response(status = 401)
		return cb(*args, **kwargs, dbsession = dbsession, authsession = authsession)
	return api_handler

@auth_route("/Register")
def register(email, password, dbsession):
	
	def error(message):
		return flask.jsonify({"ClassName":"System.Exception","Message":message,"Data":None,"InnerException":None,"HelpURL":None,"StackTraceString":None,"RemoteStackTraceString":None,"RemoteStackIndex":0,"ExceptionMethod":None,"HResult":-2146233088,"Source":None})
	
	try:
		displayname = flask.request.args["displayname"]
		sysname = flask.request.args["sysname"]
		appname = flask.request.args["appname"][:255]
		appdesc = flask.request.args["appdesc"][:255]
		version = flask.request.args["version"][:255]
	except KeyError as ex:
		return error(str(ex))
	
	# Additional constraints for password
	if len(password) < 7:
		return error("Password too short")
	requirements = [".*[A-Z].*", ".*[a-z].*", ".*[0-9].*"]
	for expr in list(requirements):
		if re.compile(expr).match(password) is None:
			return error("Password does not meet the requirements")
	
	password = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
	
	try:
		user = User(ID = str(uuid.uuid4()), Email = email, Password = password, DisplayName = displayname, SysName = sysname)
	except ValidationError:
		return error(str(ex))
	dbsession.add(user)
	
	try:
		dbsession.commit()
	except IntegrityError as ex:
		if ex.orig.args[0] == 1062:
			dbsession.rollback()
			return error(ex.orig.args[1])
		else:
			raise

	auth = Auth(dbsession, flask.request.remote_addr)
	return auth.create_session(user, appname, appdesc, version).Token

@auth_route("/Login")
def login(email, password, dbsession):
	if email == "" or password == "":
		return flask.Response(status = 400)
	
	try:
		appname = flask.request.args["appname"][:255]
		appdesc = flask.request.args["appdesc"][:255]
		version = flask.request.args["version"][:255]
	except KeyError:
		return flask.Response(status = 400)
	
	try:
		user = dbsession.query(User).filter_by(Email = email).one()
	except NoResultFound:
		print("acct does not exist")
		return flask.Response(status = 401)
	
	if user.Password is None: # login disabled
		print("login disabled")
		return flask.Response(status = 401)
	
	if not bcrypt.checkpw(password.encode(), user.Password.encode()):
		print("password incorrect")
		return flask.Response(status = 401)
	
	auth = Auth(dbsession, flask.request.remote_addr)
	return auth.create_session(user, appname, appdesc, version).Token


@api_route("/GetDisplayName/<uid>")
def get_display_name(uid, dbsession, authsession):
	return dbsession.query(User).filter_by(ID = uid).one().DisplayName

@api_route("/GetPongHighscores")
def get_pong_highscores(dbsession, authsession):
	return flask.jsonify({"Pages": 0, # unused
		"Highscores": [mapping.map_to(user, mappings["PongHighscore"])
			for user in dbsession.query(User).all()
			if user.PongLevel is not None and user.PongCP is not None]})

@api_route("/GetEmail")
def get_email(dbsession, authsession):
	return authsession.User.Email

def gettersetters(name, convert = lambda v: v):
	@api_route(f"/Get{name}")
	def getter(dbsession, authsession):
		return str(getattr(authsession.User, name))
	@api_route(f"/Set{name}/<value>")
	def setter(value, dbsession, authsession):
		setattr(authsession.User, name, convert(value))
		return flask.Response(status = 200)

@api_route("/GetPongCP")
def get_pong_cp(dbsession, authsession):
	return str(authsession.User.PongCP or 0)

@api_route("/SetPongCP/<value>")
def set_pong_cp(value, dbsession, authsession):
	value = int(value)
	if authsession.User.PongCP is not None and value <= authsession.User.PongCP:
		return flask.Response(status = 400)
	authsession.User.PongCP = value
	return flask.Response(status = 200)

@api_route("/GetPongLevel")
def get_pong_level(dbsession, authsession):
	return str(authsession.User.PongLevel or 0)

@api_route("/SetPongLevel/<value>")
def set_pong_cp(value, dbsession, authsession):
	value = int(value)
	if authsession.User.PongLevel is not None and value <= authsession.User.PongLevel:
		return flask.Response(status = 400)
	authsession.User.PongLevel = value
	return flask.Response(status = 200)

gettersetters("SysName")
gettersetters("DisplayName")
gettersetters("FullName")
gettersetters("Codepoints", convert = int)


