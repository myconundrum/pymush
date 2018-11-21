from mushstate import mush



def aliasMatch(dbref,val):
	val = val.upper()
	for s in mush.db[dbref].aliases:
		if (val == s.upper()):
			return True
	return False