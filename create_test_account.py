
import base64
import json
import uuid

import requests

uniq = str(uuid.uuid4())[:8].upper()

displayname = f"u{uniq}"
sysname = f"s{uniq}"
email = f"{uniq}@getshiftos.ml"
password = "P@ssw0rd"

auth = "Basic " + base64.b64encode(f"{email}:{password}".encode()).decode()

token = requests.get("http://getshiftos.ml/Auth/Register",
	params = {"appname": "ShiftGears", "appdesc": "ShiftGears testing software", "version": "45", "displayname": displayname, "sysname": sysname},
	headers = {"Authentication": auth}).text.strip()

print(token)
