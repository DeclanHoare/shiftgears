# SQL Tables

# This shits a mess but hey it's python...

import contextlib
import enum
import os

from sqlalchemy import Boolean, Column, create_engine, DateTime, ForeignKey, Integer, MetaData, String, Table, Text, Unicode, UnicodeText
from sqlalchemy.dialects.mysql import BIGINT, DOUBLE
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import backref, relationship, RelationshipProperty, sessionmaker, validates
from sqlalchemy.sql import func

from mapping import Direction
from myconfig import config, mappings

Base = declarative_base()

engine = create_engine(config["dbaddr"])
DbSession = sessionmaker(bind = engine)

class ValidationError(Exception):
	pass

def validated(col, validator = None, strip = False, min_length = None, min_value = None, max_value = None):
	
	def validate_string(row, key, val, encoding = None):
		if not isinstance(val, str):
			raise ValidationError(f"{col.name} must be a string")
		if encoding is not None:
			try:
				val.encode(encoding)
			except UnicodeEncodeError: # this exc is also used for ASCII!
				raise ValidationError(f"{col.name} must be a valid {encoding} string")
		
		if strip:
			val = val.strip()
		if min_length is not None and len(val) < min_length:
			raise ValidationError(f"{col.name} must be at least {min_length} characters long")
		if col.type.length is not None and len(val) > col.type.length:
			raise ValidationError(f"{col.name} cannot be more than {col.type.length} characters long")
		return val
	
	def validate_number(row, key, val, min, max, t):
		if not isinstance(val, t):
			raise ValidationError(f"{val} must be {t.__name__}")
		if min is not None and val < min:
			raise ValidationError(f"{col.name} cannot be less than {min}")
		if max is not None and val > max:
			raise ValidationError(f"{col.name} cannot be greater than {max}")
		return val
	
	@validates(col.name)
	def validate(row, key, val):
		if hasattr(row, "dontvalidate"):
			return val
		if validator is not None:
			val = validator(row, key, val)
		if val is None:
			if col.nullable:
				return None
			else:
				raise ValidationError(f"{col.name} cannot be null")
		
		min = min_value
		max = max_value
		
		if isinstance(col.type, String) or isinstance(col.type, Text):
			val = validate_string(row, key, val, "ASCII")
		elif isinstance(col.type, Unicode) or isinstance(col.type, UnicodeText):
			val = validate_string(row, key, val, "UTF-8")
		
		elif isinstance(col.type, Boolean) and not isinstance(val, bool):
			raise ValidationError(f"{col.name} must be a boolean")


		elif isinstance(col.type, Integer):
			if min is None:
				min = -(1 << 31)
			if max is None:
				max = (1 << 31) - 1
			val = validate_number(row, key, val, min, max, int)
		elif isinstance(col.type, BIGINT):
			if min is None:
				min = 0 if col.type.unsigned else -(1 << 63)
			if max is None:
				max = 1 << (63 if col.type.unsigned else 64)
			val = validate_number(row, key, val, min, max, int)
		elif isinstance(col.type, DOUBLE):
			val = validate_number(row, key, val, min, max, float)
		return val
	return col, validate

def validate_email(row, key, val):
	if val.count("@") == 1 and ".." not in val.split("@")[-1]:
		return val
	else:
		raise ValidationError("Invalid email")

class User(Base):
	__tablename__ = "User"
	
	# This is a GUID
	ID = Column(String(36), nullable = False, primary_key = True)
	
	Email, ValidateEmail = validated(Column("Email", Unicode(254), nullable = False, unique = True),
		validate_email, strip = True)
	Password = Column(String(60))
	
	DisplayName, ValidateDisplayName = validated(
		Column("DisplayName", Unicode(255), unique = True, nullable = False),
		strip = True, min_length = 1)
	
	SysName, ValidateSysName = validated(
		Column("SysName", Unicode(255), unique = True, nullable = False),
		strip = True, min_length = 5)
	
	FullName, ValidateFullName = validated(
		Column("FullName", Unicode(255), nullable = False, default = ""),
		strip = True)
	
	Codepoints, ValidateCodepoints = validated(Column("Codepoints", BIGINT(unsigned = True), nullable = False, default = 0))
	PongLevel, ValidatePongLevel = validated(Column("PongLevel", Integer), min_value = 1, max_value = 42)
	PongCP, ValidatePongCP = validated(Column("PongCP", BIGINT(unsigned = True)))
	
	Sessions = relationship("AuthSession", back_populates = "User")

class AuthSession(Base):
	__tablename__ = "AuthSession"
	Token = Column(String(43), primary_key = True)
	UserID = Column(String(36), ForeignKey("User.ID"))
	User = relationship("User", back_populates = "Sessions")
	AppName, ValidateAppName = validated(Column("AppName", Unicode(255), nullable = False), strip = True)
	AppDesc, ValidateAppDesc = validated(Column("AppDesc", Unicode(255), nullable = False), strip = True)
	Version, ValidateVersion = validated(Column("Version", Unicode(255), nullable = False), strip = True)
	Created = Column(DateTime)
	LastUsed = Column(DateTime)
	LastIP = Column(String(39), nullable = False)

# Save is out to a separate table cause the player can delete it without
# deleting their whole account
class Save(Base):
	__tablename__ = "Save"
	
	ID = Column(Integer, primary_key = True)
	
	UserID = Column(String(36), ForeignKey("User.ID"))
	User = relationship("User", backref = backref("Save", uselist = False))
	
	MusicVolume, ValidateMusicVolume = validated(Column("MusicVolume", Integer, nullable = False, default = 0))
	SfxVolume, ValidateSfxVolume = validated(Column("SfxVolume", Integer, nullable = False, default = 0))
	
	Upgrades = relationship("Upgrade", backref = "Save")
	
	# I think if the StoryPosition is changed back to 0 after the Oobe then ShiftOS will softlock.
	# Keep an eye on this...
	StoryPosition, ValidateStoryPosition = validated(Column("StoryPosition", Integer, nullable = False, default = 0))
	
	Language, ValidateLanguage = validated(Column("Language", Unicode(255)))
	MyShop, ValidateMyShop = validated(Column("MyShop", Unicode(255)))
	
	MajorVersion, ValidateMajorVersion = validated(Column("MajorVersion", Integer, nullable = False, default = 0))
	MinorVersion, ValidateMinorVersion = validated(Column("MinorVersion", Integer, nullable = False, default = 0))
	Revision, ValidateRevision = validated(Column("Revision", Integer, nullable = False, default = 0))
	
	IsPatreon = Column(Boolean, nullable = False, default = False)
	Class, ValidateClass = validated(Column("Class", Integer, nullable = False, default = 0),
		min_value = 0, max_value = 8)
	RawReputation, ValidateRawReputation = validated(Column("RawReputation", DOUBLE, nullable = False, default = 0))
	
	Password, ValidatePassword = validated(Column("Password", Unicode(255)))
	PasswordHashed, ValidatePasswordHashed = validated(Column("PasswordHashed", Boolean, nullable = False, default = False))
	
	ShiftnetSubscription, ValidateShiftnetSubscription = validated(Column("ShiftnetSubscription", Integer, nullable = False, default = False),
		min_value = 0, max_value = 3)
	
	IsMUDAdmin = Column(Boolean, nullable = False, default = False)
	
	LastMonthPaid, ValidateLastMonthPaid = validated(Column("LastMonthPaid", Integer, nullable = False, default = 0))
	
	StoriesExperienced = relationship("StoryExperienced", backref = "Save")
	Users = relationship("ClientSave", backref = "Save")

class Upgrade(Base):
	__tablename__ = "Upgrade"
	ID = Column(Integer, primary_key = True)
	SaveID = Column(Integer, ForeignKey("Save.ID"))
	Name, ValidateName = validated(Column("Name", Unicode(255)))
	Installed, ValidateInstalled = validated(Column("Installed", Boolean, nullable = False))

class StoryExperienced(Base):
	__tablename__ = "StoryExperienced"
	ID = Column(Integer, primary_key = True)
	SaveID = Column(Integer, ForeignKey("Save.ID"))
	Name, ValidateName = validated(Column("Name", Unicode(255)))
	Name = Column(Unicode(255))

class ClientSave(Base):
	__tablename__ = "ClientSave"
	ID = Column(Integer, primary_key = True)
	SaveID = Column(Integer, ForeignKey("Save.ID"))
	Username, ValidateUsername = validated(Column("Username", Unicode(255)))
	Password, ValidatePassword = validated(Column("Password", Unicode(255)))
	Permissions, ValidatePermissions = validated(Column("Permissions", Integer, nullable = False, default = 0), min_value = 0, max_value = 3)

