import enum
import os

# A mapping defines how to convert part of a row to a dictionary for
# an API response, and how to insert data from a received dictionary
# back into the row.  In other words it allows you to quickly select
# and rename a lot of fields.  This module deals with parsing them.
# They are used in database and the path is chosen in myconfig.

class Direction(enum.Flag):
	TO = enum.auto()
	FROM = enum.auto()

Direction.BOTH = Direction.TO|Direction.FROM

_direction_symbols = [("<", Direction.TO), (">", Direction.FROM)]

def load_mappings(path):
	mappings = {}
	for fn in os.listdir(path):
		with open(os.path.join(path, fn)) as f:
			mapping = []
			for l in f:
				l = l.strip()
				if l == "" or l.startswith("#"):
					continue
				cols = l.split()
				dictname = cols.pop(0)
				if cols:
					direction = Direction(0)
					dirstring = cols.pop(0)
					for sym, val in _direction_symbols:
						if sym in dirstring:
							direction |= val
				else:
					direction = Direction.BOTH
				if cols:
					tablename = cols.pop(0)
				else:
					tablename = dictname
				mapping.append((dictname, direction, tablename))
			mappings[fn] = mapping
	return mappings

def map_to(row, mapping):
	return {dictname: getattr(row, tablename) for dictname, direction, tablename in mapping if direction & direction.TO}

def map_from(row, mapping, data):
	for dictname, direction, tablename in mapping:
			if direction & direction.FROM:
				setattr(row, tablename, data[dictname])

