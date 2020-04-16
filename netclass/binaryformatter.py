# Copyright 2020 Declan Hoare

# This should really be split into two layers:
# - binaryformatter.py deals with transforming Python objects into
#	NRBF meta-dictionaries and vice versa.
# - nrbf.py reads and writes the binary structure.
# To do this, netfleece should ideally be patched, because as-is, it
# changes the meta-dictionaries somewhat from how they are in the file:
# in particular, after reading *AndTypes records it will consume the
# following records and move them to a 'Values' member on the lead
# record.
# Anyway, I think the interface of this module is fine, so it will do
# as a black box for now.

import struct

import netfleece
from netfleece.netfleece import RecordTypeEnum

from .netclass import netclass_root, classes

def deserialise(stream):
	def extract_value(meta): #Recover the underlying structure from NRBF meta-dictionary
		if "Value" in meta:
			return meta["Value"]
		elif "Values" in meta:
			return classes[meta["ClassInfo"]["Name"]].from_dict(
				{n.split("<")[1].split(">")[0]: extract_value(v) # They look like this: <Name>k__BackingField for some reason
					for n, v in zip(meta["ClassInfo"]["MemberNames"], meta["Values"])})
		elif meta["RecordTypeEnum"] == "ObjectNull":
			return None
		else:
			raise ValueError(f"Unknown value format: {meta}")
	dnb = netfleece.DNBinary(stream, expand = True)
	dnb.parse()
	meta = dnb.backfill()
	return extract_value(meta)

# Serialisation is limited, mostly only supporting the features needed
# for ShiftOS
_nrbf_header = b"\0\x01\0\0\0\xFF\xFF\xFF\xFF\x01\0\0\0\0\0\0\0"
_nrbf_footer = b"\x0B"

s32 = struct.Struct("<i")

def serialise(stream, obj):
	
	assemblies = [None]
	last_id = 0
	
	def write_byte(val):
		stream.write(bytes([val]))
	def write_s32(val):
		stream.write(s32.pack(val))
	def write_string(s):
		data = s.encode("utf-8")
		n = len(data)
		if n > 0x7FFFFFFF:
			raise ValueError(f"String is too long ({n} bytes)")
		while n > 0x7F:
			write_byte((n & 0x7F) | 0x80)
			n >>= 7
		write_byte(n)
		stream.write(data)
	
	def next_id():
		nonlocal last_id
		last_id += 1
		return last_id
	
	def write_record_type(typ):
		write_byte(typ.value)
	
	def write_library(name):
		library_id = len(assemblies)
		write_record_type(RecordTypeEnum.BinaryLibrary)
		write_s32(library_id)
		write_string(name)
		assemblies.append(name)
		return library_id
	
	def library(name):
		return assemblies.index(name)
	
	def write_object_string(object_id, val):
		write_record_type(RecordTypeEnum.BinaryObjectString)
		write_s32(object_id)
		write_string(val)
	
	def write_object_null():
		write_record_type(RecordTypeEnum.ObjectNull)
	
	def write_class_with_members(object_id, val):
		library_id = library(val._assembly)
		write_record_type(RecordTypeEnum.ClassWithMembers)
		write_s32(object_id)
		write_string(val._name)
		write_s32(len(val._members))
		for typ, name in val._members:
			write_string(f"<{name}>k__BackingField")
		write_s32(library_id)
	
	def walk_library(it):
		if isinstance(it, netclass_root):
			if it._assembly not in assemblies:
				write_library(it._assembly)
			for typ, name in it._members:
				walk_library(it._contents[name])
	
	def walk(it):
		object_id = next_id()
		if isinstance(it, netclass_root):
			write_class_with_members(object_id, it)
			for typ, name in it._members:
				walk(it._contents[name])
		elif isinstance(it, str):
			write_object_string(object_id, it)
		elif it is None:
			write_object_null()
		else:
			raise TypeError("Type not supported!")
		return object_id
	
	stream.write(_nrbf_header)
	walk_library(obj)
	walk(obj)
	stream.write(_nrbf_footer)

