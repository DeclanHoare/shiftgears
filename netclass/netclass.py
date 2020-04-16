
# The netclasses derive this so they can be identified.
class netclass_root:
	pass

classes = {}

def netclass(name, assembly, members):
	member_names = [n for _, n in members]
	class proxy(netclass_root):
		def __init__(self, *args, **kwargs):
			if args == ():
				super().__setattr__("_contents", kwargs)
			else:
				super().__setattr__("_contents", dict(zip(member_names, args)))
			self._validate()
		
		def _validate(self):
			if set(member_names) != set(self._contents.keys()):
				raise TypeError("The instance does not have the correct members")
				for typ, name in members:
					val = self._contents[name]
					if not isinstance(val, typ):
						raise TypeError(f"{name} is {val}, must be {typ}")
		
		@staticmethod
		def from_dict(d):
			cleaned = {}
			for typ, name in members:
				val = d[name]
				if isinstance(val, dict) and issubclass(typ, netclass_root):
					val = typ.from_dict(val)
				cleaned[name] = val
			return proxy(**cleaned)
		
		def __getattr__(self, member):
			try:
				return self._contents[member]
			except KeyError:
				raise AttributeError(f"No such member {member}")
		
		def __setattr__(self, member, value):
			if member in self._members:
				self._contents[member] = value
			else:
				raise AttributeError(f"No such member {member}")
	
	proxy._name = name
	proxy._assembly = assembly
	proxy._members = members
	proxy.__name__ = name.split(".")[-1]
	classes[name] = proxy
	return proxy
