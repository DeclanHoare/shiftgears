import os
import json

import mapping

os.chdir(os.path.dirname(os.path.realpath(__file__)))
with open("config.json") as f:
	config = json.load(f)

mappings = mapping.load_mappings("mappings")
