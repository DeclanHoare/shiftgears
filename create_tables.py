import database
database.Base.metadata.create_all(database.engine)
session = database.DbSession()

systems = [("DevX", "mud", ["sys", "DevX"]),
			("hacker101", "undisclosed", ["hacker101"]),
			("victortran", "theos", ["victortran"])]

# create the system account

for i, (displayname, sysname, users) in enumerate(systems):
	
	user = database.User()
	user.dontvalidate = True
	user.ID = "00000000-0000-0000-0000-%012d" % i
	user.Email = f"{sysname}@system.invalid"
	user.DisplayName = displayname
	user.SysName = sysname
	session.add(user)
	save = database.Save()
	save.User = user
	save.IsMUDAdmin = True
	session.add(save)
	print(repr(user.Save))
	for username in users:
		clientsave = database.ClientSave()
		clientsave.Username = username
		clientsave.Save = save
		session.add(clientsave)

session.commit()
session.close()