
import decimal
import json

from .netclass import netclass_root

class _encoder(json.JSONEncoder):
	def default(self, obj):
		if isinstance(obj, netclass_root):
			return obj._contents
		elif isinstance(obj, decimal.Decimal):
			return float(obj)
		else:
			return super().default(obj)

def from_json(t, j):
	print(repr(j))
	val = json.loads(j)
	if issubclass(t, netclass_root):
		val = t.from_dict(val)
	if not isinstance(val, t):
		raise ValueError(f"the JSON value was of type {type(val)}, not {t}")
	return val

def to_json(obj):
	return json.dumps(obj, cls=_encoder)
