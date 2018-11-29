
import re
import math
import time
from mushstate import mush
from database import ObjectFlags
from utils import * 
import commands
import random
import fnmatch
import os
import pickle

class EvalEngine:

	def __init__(self,line,enactor,obj):

		self.registers = ["0","0","0","0","0","0","0","0","0","0"]
		self.enactor = enactor
		self.obj     = obj
		self.line    = line
		self.originalLine = line

	def nextTok(self):
		if self.line != None:
			self.line = self.line[1:]


	def getTerms(self,expectedterms = []):

		terms = []
		done = False


		while not done:
			term = self.eval(",)")
			if term != "":
				terms.append(term)
			if self.line == None or self.line[0] == ')':
				done = True
			self.nextTok()
			
		return terms



	def getOneTerm(self):
		
		term = self.eval(")")
		self.nextTok()
		return term
	
	def evalSubstitutions(self,ch):
		if (ch == 'N'):
			return mush.db[self.enactor].name
		elif (ch == 'R'):
			return '\n'
		elif (ch == 'B'):
			return ' '
		elif (ch == '%'):
			return '%'
		elif (ch in '0123456789'):
			return self.registers[int(ch)]

		# BUGBUG: Need to add other substitutions
		return ''


	def dbrefify(self,term):

		term = term.strip().upper()

		if (term == "" or term=="HERE"):
			return mush.db[self.enactor].location # assume no argument defaults to current location of enactor

		if (term == "ME"):
			return self.enactor

		# look in the contents of the current room
		for d in mush.db[mush.db[self.enactor].location].contents:
			if (aliasMatch(d,term)):
				return d 

		# look in inventory
		for d in mush.db[self.enactor].contents:
			if (aliasMatch(d,term)):
				return d

		if (term[0] == '#' and term[1:].isnumeric()):
			dbref = int(term[1:])		
			if mush.db[dbref].location == mush.db[self.enactor].location or mush.db[dbref].location == self.enactor or \
				mush.db[dbref].owner == self.enactor or mush.db[self.enactor].flags & ObjectFlags.WIZARD:
				return dbref if mush.db.validDbref(dbref) else None 

		return None

	#
	# For Mush functions
	# A negative dbref (#-) is considered false
	# The number 0 is considered false
	# An empty string is considered false
	# None string is considered false.
	# anything else is True.
	# 
	def boolify(self,term):
		if (term == None):
			return False
		if (term[0:2] == '#-'): 
			return False
		if (len(term) == 0): 
			return False
		if (self.isnum(term)):
			return self.numify(term) != 0

		return True



	def isInt(self,string):
		try: 
			int(string)
			return True
		except ValueError:
			return False


	def isFloat(self,string):
	    try:
	        float(string)
	        return True
	    except ValueError:
	        return False

	def isnum(self,term):
		return self.isInt(term) or self.isFloat(term)

	def numify(self,term):

		if (self.isInt(term)):
			val = int(term)
		elif(self.isFloat(term)):
			val = float(term)
		else:
			val = 0

		return val

	def getObjAttr(self,term):

		sep = term.find('/')
		if (sep == -1):
			return (self.dbrefify(term),None)
		return (self.dbrefify(term[0:sep]),term[sep+1:].upper())

	
	def _eval_fn(self):

		rStr = ""
		self.line = self.line.strip()

		# look for first term...
		match = re.search(r'\W',self.line)
		if (match):
			# extract the term.
			i = match.start()
			term = self.line[0:i].upper()

			# if the term is the name of a function, call that function, with an argument of the rest of the string.
			if self.line[i]=='(' and term in fnList:
				self.line = self.line[i+1:]
				rStr += fnList[term](self)
			else: 
				# Not a match, so simply add what we found so far to the results string and update the line.
				rStr += self.line[0:i]
				self.line = self.line[i:]

		return rStr

	def eval(self,stops,escaping=False):
		
		rStr = ""

		# ignore empty lines.
		if (self.line == None):
			return ""
			
		# first part of a line is always in fn evaluation mode.
		rStr += self._eval_fn()

		# Now loop through the rest of the string until we reach our stopchars or a special char.
		pattern = re.compile(f"[{stops}\[%]") if not escaping else re.compile(f"[{stops}]")


		while self.line != None:

			match = pattern.search(self.line)
			if (not match): 
				# No more special characters until the end of the string. 
				rStr += self.line 
				self.line = None 
			else:
				i = match.start() 
				rStr += self.line[:i]
				# Check for substitution characters
				if self.line[i] == '%':
					rStr += self.evalSubstitutions(self.line[i+1])
					self.line = self.line[i+2:]
				# check for brackets and recurse if found.
				elif self.line[i] == '[':
					e = EvalEngine(self.line[i+1:],self.enactor,self.obj)
					rStr += e.eval("]")
					self.line = e.line[1:]
				
				# we must have found one of the stop chars. exit.
				else:
					self.line = self.line[i:]
					return rStr

		return rStr





def evalAttribute(ctx,dbref,attr):

	if attr not in mush.db[dbref]:
		return ""
	else:
		e = EvalEngine(mush.db[dbref][attr],ctx.enactor,dbref)
		return e.eval("")
	




def fnAdd(ctx):

	rval = 0
	terms = ctx.getTerms()
	for t in terms:
		rval += ctx.numify(t)

	return str(rval)

def fnAnd(ctx):

	terms = ctx.getTerms()
	for t in terms:
		if (ctx.boolify(t) == False):
			return "0"

	return "1"


def fnAlphaMax(ctx):

	words = ctx.getTerms()
	words.sort(reverse=True)
	return words[0]

def fnAlphaMin(ctx):
	words = ctx.getTerms()
	words.sort()
	return words[0]

def fnAbs(ctx):
	return str(abs(ctx.numify(ctx.getOneTerm())))


def fnAfter(ctx):
	terms = ctx.getTerms()
	words = terms[0].split(terms[1],1)
	return words[1] if len(words) > 1 else ""
	
def fnAcos(ctx):
	term = ctx.getOneTerm()
	return str(math.acos(ctx.numify(term)))
	
def fnAsin(ctx):
	term = ctx.getOneTerm()
	return str(math.asin(ctx.numify(term)))

def fnAtan(ctx):
	term = ctx.getOneTerm()
	return str(math.atan(ctx.numify(term)))

def fnNotImplemented(ctx):
	ctx.getTerms()
	return "#-1 Function Not Implemented"

def fnAPoss(ctx):

	rval = "its"

	sex = evalAttribute(ctx,ctx.dbrefify(ctx.getOneTerm()),"SEX").upper()

	if (sex=="MALE" or sex == "M" or sex == "MAN"):
		rval = "his"
	elif(sex=="FEMALE" or sex =="F" or sex == "WOMAN" ):
		rval = "hers"
	elif(sex == "PLURAL"):
		rval = "theirs"

	return rval

def fnArt(ctx):
	term = ctx.getOneTerm()
	return "an" if term != None and term[0] in "AEIOUaeiou" else "a"
	

# takes up to ten lists of numbers and averages. 
# lists are space delimited and there is a comma between each list
def fnAvg(ctx):

	rval = 0
	count = 0
	lists = ctx.getTerms()
	
	for l in lists:
		for term in l.split(' '):
			count += 1
			rval += ctx.numify(term)

	return str(round(rval/count,6))

def fnBefore(ctx):
	terms = ctx.getTerms()
	words = terms[0].split(terms[1],1)
	return words[0] if len(words) > 1 else ""

def fnCapStr(ctx):
	cap = ctx.getOneTerm()
	return cap.capitalize() if cap != None else ""
	
def fnCat(ctx):
	return " ".join(ctx.getTerms())


def fnCeil(ctx):
	return str(math.ceil(ctx.numify(ctx.getOneTerm())))


def fnCenter(ctx):
	terms = ctx.getTerms()
	if (len(terms) < 2 or len(terms) > 3):
		return "#-1 Function expects 2 or 3 arguments."

	width = ctx.numify(terms[1])
	pad = " " if len(terms) < 3 else terms[2]

	return terms[0].center(width,pad)


def fnComp(ctx):
	terms = ctx.getTerms()
	if (len(terms) != 2):
		return "#-1 Function expects 2 arguments."

	val = 0
	if (terms[0] < terms[1]): 
		val = -1
	elif (terms[0] > terms[1]):
		val = 1

	return str(val)


def fnClone(ctx):

	dbref = ctx.dbrefify(ctx.getOneTerm())
	o = mush.db[dbref]
	if (o.flags & (ObjectFlags.ROOM | ObjectFlags.PLAYER)):
		mush.msgDbref(enactor,"You can only clone things and exits.")
		return "#-1"

	# BUGBUG This is not implemented yet. Needs to be completed.

def fnCon(ctx):
	dbref = ctx.dbrefify(ctx.getOneTerm())
	val =  -1 if len(mush.db[dbref].contents) == 0 else mush.db[dbref].contents[0]
	return str(val)

def fnConvSecs(ctx):
	return str(time.asctime(time.localtime(ctx.numify(ctx.getOneTerm()))))


def fnOr(ctx):
	for t in ctx.getTerms():
		if (ctx.boolify(t) == True):
			return "1"

	return "0"

def fnCos(ctx):
	return str(math.cos(ctx.numify(ctx.getOneTerm)))

def fnCreate(ctx):

	terms = ctx.getTerms()
	if (len(terms)<1 or len(terms)>2):
		return "#-1 Function expects 1 or 2 arguments."

	dbref = mush.db.newObject(mush.db[ctx.enactor])
	mush.db[dbref]["NAME"] = terms[0]
	mush.msgDbref(ctx.enactor,f"Object named {terms[0]} created with ref #{dbref}.")
	mush.log(2,f"{mush.db[ctx.enactor].name}(#{ctx.enactor}) created object named {terms[0]} (#{dbref}).")
	return str(dbref)

	
def fnCTime(ctx):
	return time.ctime(mush.db[ctx.dbrefify(ctx.getOneTerm())].creationTime)


#
# takes a *string* as argument, and finds the last integer part and subs one from that.
# so dec(hi3) => hi2, dec(1.2)=>1.1 
# 
def fnDec(ctx):

	term = ctx.getOneTerm()
	m = re.search(r'-?\d+$',term)
	if (m == None):
		return "#-1 Argument does not end in integer."

	return term[0:m.start()]+str(ctx.numify(m.group())-1)

def fnDefault(ctx):

	terms = ctx.getTerms()
	if len(terms) != 2:
		return "#-1 Function exects two arguments."

	(dbref,attr) = ctx.getObjAttr(terms[0])
	return mush.db[dbref][attr] if attr in mush.db[dbref] else terms[1]

def fnDelete(ctx):
	
	terms = ctx.getTerms()
	if len(terms) != 3:
		return "#-1 Function expects three arguments."

	start 	= ctx.numify(terms[1])
	length 	= ctx.numify(terms[2])

	return terms[0][0:start]+terms[0][start+length:]


def fnDie(ctx):
	
	terms = ctx.getTerms()
	if len(terms) != 2:
		return "#-1 Function expects two arguments."

	return str(sum([random.randint(1,ctx.numify(terms[1])) for x in range(ctx.numify(terms[0]))]))


def fnDig(ctx):
	
	eback = None
	eout = None 

	terms = ctx.getTerms()
	if len(terms) < 1 or len(terms) > 3:
		return "#-1 Function expects one to three arguments."

	if (len(terms) == 3):
		eout = terms[1]
		eback = terms[2]
	if (len(terms)) == 2:
		eout = terms[1]

	return str(commands.doDig(mush.db[ctx.enactor],terms[0],eout,eback))



def fnDist2D(ctx):
	
	terms = ctx.getTerms()
	if len(terms) != 4:
		return "#-1 Function expects four arguments."

	x1 = ctx.numify(terms[0])
	y1 = ctx.numify(terms[1])
	x2 = ctx.numify(terms[2])
	y2 = ctx.numify(terms[3])
	return str(round(math.sqrt((x2 - x1)*(x2 - x1) + (y2 - y1) * (y2 - y1)),6))

def fnDist3D(ctx):
	
	terms = ctx.getTerms()
	if len(terms) != 6:
		return "#-1 Function expects six arguments."

	x1 = ctx.numify(terms[0])
	y1 = ctx.numify(terms[1])
	z1 = ctx.numify(terms[2])
	x2 = ctx.numify(terms[3])
	y2 = ctx.numify(terms[4])
	z2 = ctx.numify(terms[5])

	return str(round(math.sqrt((x2 - x1)*(x2 - x1) + (y2 - y1) * (y2 - y1) + (z2 - z1) * (z2 - z1)),6))

def fnDiv(ctx):
	
	terms = ctx.getTerms()
	if len(terms) != 2:
		return "#-1 Function expects two arguments."
	
	return str(ctx.numify(terms[0])//ctx.numify(terms[1]))


def fnE(ctx):
	
	terms = ctx.getTerms()
	if len(terms) != 0:
		return "#-1 Function expects zero arguments."
	return "2.718281"

def fnEDefault(ctx):

	terms = ctx.getTerms()
	if len(terms) != 2:
		return "#-1 Function exects two arguments." 

	(dbref,attr) = ctx.getObjAttr(terms[0])
	e = EvalEngine(mush.db[dbref][attr] if attr in mush.db[dbref] else terms[1],ctx.enactor,ctx.obj)
	return e.eval("")

def fnEdit(ctx):
	
	terms = ctx.getTerms()
	if len(terms) != 3:
		return "#-1 Function expects three arguments."

	if (terms[1] == '$'):
		s = terms[0] + terms[2]
	elif (terms[1] == '^'):
		s = terms[2] + terms[0]
	else:
		s = terms[0].replace(terms[1],terms[2])
	
	return s

def fnElement(ctx):
	
	terms = ctx.getTerms()
	
	# Not sure why this is what is returned in these cases, but preserved for pennmush compatibility.
	if (len(terms) == 0):
		return "1"
	if (len(terms) == 1):
		return "0"

	c = 1
	for item in terms[0].split(' ' if len(terms) < 3 else terms[2][0]): 
		if fnmatch.fnmatch(item,terms[1]):
			return str(c)
		c+=1
	
	return "0"


def fnElements(ctx):
	
	terms = ctx.getTerms()
	
	if (len(terms) < 2 or len(terms) > 3):
		return "#-1 Function expects two or three arguments."

	sep = terms[2][0] if len(terms) == 3 else ' '
	elements = terms[0].split(sep)
	indices = terms[1].split()
	rval = []

	for i in indices:
		rval.append(elements[ctx.numify(i)-1])

	return sep.join(rval)

def fnEmit(ctx):
	mush.msgLocation(mush.db[ctx.obj].location,ctx.getOneTerm())
	return ""

def fnEnumerate(ctx):
	
	terms = ctx.getTerms()

	sep = ' ' if len(terms) < 2 else terms[1][0]
	connective = 'and' if len(terms) < 3 else terms[2]
	items = terms[0].split(sep)

	if len(items) < 2:
		return terms[0]

	if len(items) == 2:
		return f"{items[0]} {connective} {items[1]}"

	return ", ".join(items[:-1])+", " + connective + " " + items[-1]

def fnEq(ctx):

	terms = ctx.getTerms()	
	if (len(terms) != 2):
		return "#-1 Function expects two arguments"

	if (not ctx.isnum(terms[0] or not ctx.isnum(terms[1]))):
		return "#-1 Arguments must be numbers"

	return "1" if ctx.numify(terms[0]) == ctx.numify(terms[1]) else "0"


def escaper(match):
	return f"\\{match.group(0)}"

def fnEscape(ctx):
	# call eval in special "escaping" mode
	term = ctx.eval(")",True)
	ctx.nextTok()
	return "\\" + re.sub(r"[%;{}\[\]]",escaper,term)

def fnEval(ctx):
	
	terms = ctx.getTerms()	
	if (len(terms) != 2):
		return "#-1 Function expects two arguments"


	dbref = ctx.dbrefify(terms[0])
	attr = terms[1].upper()
	if attr in mush.db[dbref]:
		e = EvalEngine(mush.db[dbref][attr],ctx.enactor,ctx.obj)
		return e.eval("")

	return ""

#
# weird functino. Based on documentation, returns the first exit for object. 
# does so if its a room. 
# otherwise, returns the first room in the location chain of the object.
# for instance -- player in room X carrying object key:
# th exit(key) -> returns dbref(X)
#	
def fnExit(ctx):

	terms = ctx.getTerms()
	if (len(terms) == 0):
		return "#-1"

	dbref = ctx.dbrefify(terms[0])
	
	if mush.db[dbref].flags & ObjectFlags.ROOM:
		for o in mush.db[dbref].contents:
			if mush.db[o].flags & ObjectFlags.EXIT:
				return str(o)
	else:
		while not mush.db[mush.db[dbref].location].flags & ObjectFlags.ROOM:
			dbref = mush.db[dbref].location
	
	return str(dbref)


def fnExp(ctx):
	return str(round(math.exp(ctx.numify(ctx.getOneTerm())),6))


def fnExtract(ctx):
	
	terms = ctx.getTerms()
	if (len(terms) < 3 or len(terms) > 4):
		return "#-1 Function expects 3 or 4 arguments"


	sep = ' ' if len(terms) < 4 else terms[3][0]
	start = ctx.numify(terms[1]) - 1
	length = ctx.numify(terms[2]) 
	items = terms[0].split(sep)

	return sep.join(items[start:start+length])


def fnFDiv(ctx):
	terms = ctx.getTerms()
	if len(terms) != 2:
		return "#-1 Function expects two arguments."

	return str(round(ctx.numify(terms[0])/ctx.numify(terms[1]),6))

def fnFilter(ctx):

	terms = ctx.getTerms()
	if (len(terms)<2 or len(terms) > 3):
		return "#-1 Function expects two or three arguments."

	(dbref,attr) = ctx.getObjAttr(terms[0])
	#
	# BUGBUG Not complete.
	#
	return ""

def fnFirst(ctx):

	terms = ctx.getTerms()
	if (len(terms) > 2):
		return "#-1 Function expects one or two arguments."

	# and empty set of arguements returns empty.
	if (len(terms) == 0):
		return ""

	sep = ' ' if len(terms) != 2 else terms[1][0]
	return terms[0].split(sep)[0]


def fnFlip(ctx):
	return ctx.getOneTerm()[::-1]

def fnFloor(ctx):
	return str(math.floor(ctx.numify(ctx.getOneTerm())))

def fnForEach(ctx):

	terms = ctx.getTerms()
	if (len(terms) != 2):
		return "#-1 Function expects two arguments."
	(dbref,attr) = ctx.getObjAttr(terms[0])
	
	rVal = ""
	if attr in mush.db[dbref]:
		for letter in terms[1]:
			e = EvalEngine(mush.db[dbref][attr],ctx.enactor,ctx.obj)
			e.registers[0] = letter
			rVal += e.eval("")

	return rVal


def fnFreeAttr(ctx):
	
	terms = ctx.getTerms()
	if (len(terms) != 3):
		return "#-1 Function expects three arguments."

	n = 0
	dbref = ctx.dbrefify(terms[0])
	prefix = terms[1].upper()
	suffix = terms[2].upper()
	while True:
		if not f"{prefix}{n}{suffix}" in mush.db[dbref]:
			return str(n)
		n+=1


	return "-1"

def fnFullName(ctx):
	return mush.db[ctx.dbrefify(ctx.getOneTerm())]["NAME"]

def fnFunctions(ctx):
	ctx.getOneTerm()
	return ' '.join(fnList.keys())

def fnGet(ctx):

	term  = ctx.getOneTerm()
	if (term == ""):
		return "#-1 Function expects one argument."

	(dbref,attr) = ctx.getObjAttr(term)

	return "" if attr not in mush.db[dbref] else mush.db[dbref][attr]

def fnGet_Eval(ctx):
	
	term = ctx.getOneTerm()
	if (term == ""):
		return "#-1 Function expects two arguments."
	(dbref,attr) = ctx.getObjAttr(term)
	
	if attr in mush.db[dbref]:
		e = EvalEngine(mush.db[dbref][attr],ctx.enactor,ctx.obj)
		return e.eval("")
		
	return ""


def fnGrab(ctx):
	
	terms = ctx.getTerms()
	if (len(terms) < 2 or len(terms) > 3):
		return "#-1 Function expects two or three arguments."

	sep = terms[2][0] if len(terms) == 3 else ' '
	elements = terms[0].split(sep)
	pattern = terms[1]
	
	for item in elements: 
		if fnmatch.fnmatch(item,pattern):
			return item
		
	return ""


def fnGrabAll(ctx):

	terms = ctx.getTerms()
	if (len(terms) < 2 or len(terms) > 3):
		return "#-1 Function expects two or three arguments."
	
	sep = terms[2][0] if len(terms) == 3 else ' '
	elements = terms[0].split(sep)
	pattern = terms[1]
	
	return  sep.join([x for x in elements if fnmatch.fnmatch(x,pattern)])



def fnGt(ctx):
	
	terms = ctx.getTerms()
	if (len(terms) != 2):
		return "#-1 Function expects two arguments"

	if (not ctx.isnum(terms[0] or not ctx.isnum(terms[1]))):
		return "#-1 Arguments must be numbers"

	return "1" if ctx.numify(terms[0]) > ctx.numify(terms[1]) else "0"

def fnGte(ctx):

	terms = ctx.getTerms()
	if (len(terms) != 2):
		return "#-1 Function expects two arguments"

	if (not ctx.isnum(terms[0] or not ctx.isnum(terms[1]))):
		return "#-1 Arguments must be numbers"

	return "1" if ctx.numify(terms[0]) >= ctx.numify(terms[1]) else "0"

def fnHasAttr(ctx):

	terms = ctx.getTerms()
	
	if (len(terms) != 2):
		return "#-1 Function expects two arguments"
	dbref = ctx.dbrefify(terms[0])
	return "1" if dbref != None and terms[1].upper() in mush.db[dbref] else "0"

def fnHasFlag(ctx):

	terms = ctx.getTerms()
	
	if (len(terms) != 2):
		return "#-1 Function expects two arguments"

	(dbref,attr) = ctx.getObjAttr(terms[0])

	if (attr != None):
		return ("#-1 function not implemented for attribute flags.")

	flag = None
	for x in ObjectFlags:
		if (x.name  == terms[1].upper()):
			flag = x
			break

	return "1" if flag & mush.db[dbref].flags else "0"

def fnHasType(ctx):

	terms = ctx.getTerms()
	
	if (len(terms) != 2):
		return "#-1 Function expects two arguments"

	dbref = ctx.dbrefify(terms[0])
	t = terms[1].upper()

	if t not in ["ROOM","PLAYER","EXIT","THING"]:
		return  "#-1 Unsupported type."

	if (t == "ROOM" and mush.db[dbref].flags & ObjectFlags.ROOM) or \
		(t == "PLAYER" and mush.db[dbref].flags & ObjectFlags.PLAYER) or \
		(t == "EXIT" and mush.db[dbref].flags & ObjectFlags.EXIT) or \
		(t == "THING" and not mush.db[dbref].flags & (ObjectFlags.ROOM | Objectflags.PLAYER | ObjectFlags.EXIT)):
		return "1"

	return "0"

def fnHome(ctx):

	term = ctx.getOneTerm()
	if (term == ""):
		return "#-1 Function expects one argument."

	return f"#{mush.db[ctx.dbrefify(term)].home}"

fnList = {
	
	'ADD'		: fnAdd,
	'ABS'		: fnAbs,
	'ACOS'		: fnAcos,
	'AFTER'		: fnAfter,
	'ALPHAMAX'	: fnAlphaMax,
	'ALPHAMIN'  : fnAlphaMin,
	'AND'		: fnAnd,
	'ANDFLAGS'	: fnNotImplemented,
	'ANSI'		: fnNotImplemented,
	'ANSIIF'	: fnNotImplemented,
	'APOSS'		: fnAPoss,
	'ART'		: fnArt,
	'ASIN'		: fnAsin,
	'ATAN'		: fnAtan,
	'ATRLOCK'	: fnNotImplemented,
	'AVG'		: fnAvg,
	'BEEP'		: fnNotImplemented,
	'BEFORE'	: fnBefore,
	'CAND'		: fnAnd,
	'CAN_SEE'	: fnNotImplemented,
	'CAPSTR'	: fnCapStr,
	'CAT'		: fnCat,
	'CEIL'		: fnCeil,
	'CENTER'	: fnCenter,
	'CHANGE'	: fnNotImplemented, # Elendor specific
	'CLONE'		: fnNotImplemented,
	'CMDS'		: fnNotImplemented,
	'COMP'		: fnComp,
	'CON'		: fnCon,
	'CONN'		: fnNotImplemented,
	'CONTROLS'	: fnNotImplemented,
	'CONVFIRSTON': fnNotImplemented,
	'CONVSECS'	: fnConvSecs,
	'CONVTIME'	: fnNotImplemented,
	'COR'		: fnOr,
	'COS'		: fnCos,
	'CREATE'	: fnCreate,
	'CSTATS'	: fnNotImplemented,
	'CTIME'		: fnCTime,
	'DEC'		: fnDec,
	'DECRYPT'	: fnNotImplemented,
	'DEFAULT'	: fnDefault,
	'DELETE'	: fnDelete,
	'DESCFUN'	: fnNotImplemented,
	'DIE'		: fnDie,
	'DIG'		: fnDig,
	'DIST2D'	: fnDist2D,
	'DIST3D' 	: fnDist3D,
	'DIV'		: fnDiv,
	'DOING'		: fnNotImplemented,
	'E'			: fnE,
	'EDEFAULT'	: fnEDefault,
	'EDIT'		: fnEdit,
	'ELEMENT'	: fnElement,
	'ELEM'		: fnElement,
	'ELEMENTS'	: fnElements,
	'ELOCK'		: fnNotImplemented,
	'EMIT'		: fnEmit,
	'ENCRYPT'	: fnNotImplemented,
	'ENTRANCES'	: fnNotImplemented,
	'ENUMERATE'	: fnEnumerate,
	'EQ'		: fnEq,
	'ESCAPE'	: fnEscape,
	'EVAL'		: fnEval,
	'EVALTHUNKS': fnNotImplemented, # Elendor specific...
	'EXIT'		: fnExit,
	'EXP'		: fnExp,
	'EXTRACT'	: fnExtract,
	'FDIV'		: fnFDiv,
	'FILTER'	: fnFilter,
	'FINDABLE'	: fnNotImplemented,
	'FIRST'		: fnFirst,
	'FLAGS'		: fnNotImplemented,
	'FLIP'		: fnFlip,
	'FLOOR'		: fnFloor,
	'FOLD'		: fnNotImplemented,
	'FORCE'		: fnNotImplemented,
	'FOREACH'	: fnForEach,
	'FREEATTR'	: fnFreeAttr,
	'FULLNAME'	: fnFullName,
	'FUNCTIONS' : fnFunctions,
	'GET'		: fnGet,
	'GET_EVAL'	: fnGet_Eval,
	'GRAB'		: fnGrab,
	'GRABALL'	: fnGrabAll,
	'GREP'		: fnNotImplemented,
	'GREPI'		: fnNotImplemented,
	'GT'		: fnGt,
	'GTE'		: fnGte,
	'HASATTR'	: fnHasAttr,
	'HASATTRVAL': fnHasAttr,
	'HASATTRP'	: fnNotImplemented,
	'HASATTRPVAL': fnNotImplemented,
	'HASFLAG'	: fnHasFlag,
	'HASPOWER'	: fnNotImplemented,
	'HASTHUNK'	: fnNotImplemented,
	'HASTYPE'	: fnHasType,
	'HIDDEN'	: fnNotImplemented,
	'HILITE'	: fnNotImplemented,
	'HOME'		: fnHome,
	'HTMLESCAPE': fnNotImplemented,
	'HTMLOK'	: fnNotImplemented,

}

def testParse():

	tests= {
		"     abc def ghi":"abc def ghi",
		"add(1,2,3)dog house":"6dog house",
		"abs(add(-1,-5,-6))candy":"12candy",
		"add(-1,-5,-6))candy":"-12)candy",		
		"after(as the world turns,world)":" turns",
		"dog was here[add(1,2)]":"dog was here3",
		"[dog was here[add(1,2)]]":"dog was here3",
		"add(dog,1,2,3,4":"10",
		"add(1,2":"3",
		"hello world! [alphamin(zoo,black,orangutang,yes)]":"hello world! black",
		"alphamax(dog,zoo,abacus,cat)":"zoo",
		"1":"1",
		"and(0,1)":"0",
		"and(dog,-12,3,#12)":"1",
		"and(dog,-13,3,#-12)":"0",
		"aposs(me)":"its",
		"aposs(#1)":"its",
		"art(aardvark) aardvark":"an aardvark",
		"art(doghouse) doghouse":"a doghouse",
		"avg(1 2 3 4 5,6 4 3,2,1 0 0 0 3 4 5 6 7 8)":"3.368421",
		"before(as the world turns,world)":"as the ",
		"can_see(me,here)":"#-1 Function Not Implemented",
		"capstr(hello, world!)":"Hello, world!",
		"cat(hello,world,you,crazy,place!)":"hello world you crazy place!",
		"ceil(64.78)":"65",
		"ceil(64.23)":"65",
		"center(Hello World,40,-)":"--------------Hello World---------------",
		"comp(abc,abc)":"0",
		"comp(Abc,abc)":"-1",
		"comp(abc,Abc)":"1",
		"convsecs(123456)":"Fri Jan  2 02:17:36 1970",
		"create(dog,30)":"4", # This is a problem.
		"ctime(me)":"Tue Nov 20 08:08:50 2018",
		"dec(312)":"311",
		"dec(dog12)":"dog11",
		"dec(dog-1)":"dog-2",
		"default(me/description,so weird)":"The Alpha and Omega.",
		"default(me/yoyo,Not a yoyo here.":"Not a yoyo here.",
		"[delete(abcdefgh, 3, 2)]":"abcfgh",
		"dig(house)":"5",
		"dig(house,out,in)":"6",
		"dist2D(1,1,3,3)":"2.828427",
		"dist3D(1,1,1,3,3,3)":"3.464102",
		"div(5,2)":"2",
		"e()":"2.718281",
		"edefault(me/yoyo,so w[e()]ird)":"so w2.718281ird",
		"edit(dog house,dog,cat)":"cat house",
		"edit(dog house,$,cat)":"dog housecat",
		"edit(dog house,^,cat)":"catdog house",
		"elem(this is a test,is, )":"2",
		"element(this|is|a|test,is,|)":"2",
		"elem(this is a test,t?st, )":"4",
		"elements(Foof|Ack|Beep|Moo,3 1,|)":"Beep|Foof",
		"elements(Foo Ack Beep Moo Zot,2 4)":"Ack Moo",
		"emit(foo)":"",
		"enumerate(foo bar)":"foo and bar",
		"enumerate(foo bar baz)":"foo, bar, and baz",
		"enumerate(foo|bar|baz,|,doggie)":"foo, bar, doggie baz",
		"eq(a,b)":"#-1 Arguments must be numbers",
		"eq(1,2,3)":"#-1 Function expects two arguments",
		"eq(2,2)":"1",
		"eq(2,1)":"0",
		"escape(hello world[ dog % ; ] { } hah!)":"\\hello world\\[ dog \\% \\; \\] \\{ \\} hah!",
		"eval(me,description)":"The Alpha and Omega.",
		"exp()":"1.0",
		"exp(0)":"1.0",
		"exp(1)":"2.718282",
		"exp(2)":"7.389056",
		"extract(a|b|c|d,2,2,|)":"b|c",
		"extract(a dog in the house went bark,2,4)":"dog in the house",
		"extract(a dog,4,5)":"",
		"first()":"",
		"first(dog house)":"dog",
		"first(dog^house^was,^)":"dog",
		"flip(foo bar baz)":"zab rab oof",
		"floor(23.12)":"23",
		"add(1,1)":"2",
		"foreach(me/addone,123456)":"234567",
		"freeattr(me,test,foo)":"2",
		"fullname(me)":"God",
		"get(me/nothing)":"",
		"get(me/test1foo)":"FOOBAR",
		"grab(dog|cat|horse|mouse|house|help,h*,|)":"horse",
		"graball(dog|cat|horse|mouse|house|help,h*,|)":"horse|house|help",
		"hasattr(dog,cat)":"0",
		"hasattr(me,cat)":"0",
		"hasattr(me,test1foo)":"1",
		"hasflag(me,god)":"1",
		"hasflag(me,eXit)":"0",
		"hastype(me,DOG)":"#-1 Unsupported type.",
		"hastype(me,EXIT)":"0",
		"hastype(me,PLAYER)":"1",
		"home(me)":"#-1",

		}



	mush.db[1]["ADDONE"]="add(%0,1)"
	mush.db[1]["TEST1FOO"]="FOOBAR"
	mush.db[1]["TEST0FOO"]="FOOBAR"

	mush.log(1,f"MUSH: running {len(tests.keys())} functional tests for EvalEngine.")
	for s in tests:
		e = EvalEngine(s,1,1)
		val = e.eval("")
		if val != tests[s]:
			mush.log(0,f"Test failed! \'{s}\'\n\texpected: \'{tests[s]}\'\n\tactual: \'{val}\'")
		else:
			mush.log(5,f"Test passed! \'{s}\'\n\texpected: \'{tests[s]}\'\n\tactual: \'{val}\'")

	



