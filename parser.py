
import re
import math
import time
from mushstate import mush,_MUSHNAME
from database import ObjectFlags
from utils import * 
import commands
import random
import fnmatch
import os
import pickle
import sys

class EvalEngine:

	def __init__(self,line,enactor,obj,listelem="",listpos=-1):

		self.registers 		= ["0","0","0","0","0","0","0","0","0","0"]
		
		self.enactor 		= enactor
		self.obj     		= obj
		self.line    		= line
		self.originalLine	= line
		#
		# listelem and listpos if specified are used for 
		# list replacements (a la iter() and etc) if specified.
		# 
		self.listElem 		= listelem
		self.listPos 		= listpos

	def splitTerms(self,s):

		terms 		= []
		plevel 		= 1
		blevel 		= 0
		i 			= 0
		termStart 	= 0

		while (plevel or blevel) and i < len(s):
			if s[i] == ')':
				plevel -=1
				if (plevel == 0):
					terms.append(s[termStart:i])
			elif s[i] == '(':
				plevel +=1
			elif s[i] == ']':
				blevel -=1
			elif s[i] == '[':
				blevel +=1
			elif (s[i] == ',' and plevel == 1 and blevel == 0):
				terms.append(s[termStart:i])
				termStart = i+1
			i+=1
		
		if (i == len(s)):
			terms.append(s[termStart:])

		return terms
	
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


	def evalListSubstitutions(self,ch):

		if (ch == '#'):
			return self.listElem
		elif (ch =='@'):
			return str(self.listPos) 
		return f"#{ch}"

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
			dbref = self.numify(term[1:])	
			if mush.db.validDbref(dbref) and (mush.db[dbref].location == mush.db[self.enactor].location or mush.db[dbref].location == self.enactor or \
				mush.db[dbref].owner == self.enactor or mush.db[self.enactor].flags & ObjectFlags.WIZARD):
				return dbref

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

	def _get_fn_terms(self):

		plevel 			= 1
		blevel 			= 0
		i 				= 1
		while (plevel or blevel) and i < len(self.line):
			if self.line[i] == ')':
				plevel -=1
			elif self.line[i] == '(':
				plevel +=1
			elif self.line[i] == ']':
				blevel -=1
			elif self.line[i] == '[':
				blevel +=1
			i+=1

		term = self.line[1:i-1] if not plevel else self.line[1:]		
		self.line = self.line[i:] if i < len(self.line) else ""
		return term

	def _eval_fn(self):

		rStr = ""
		self.line = self.line.strip()

		# look for first term...
		match = re.search(r'\W',self.line)
		if (match):
			# extract the term.
			i = match.start()
			term = "fn_"+self.line[:i].lower()

			# if the term is the name of a function, call that function, with an argument of the rest of the string.
			if self.line[i]=='(' and hasattr(gMushFunctions,term):
				self.line = self.line[i:]
				terms = self._get_fn_terms()
				rStr += getattr(gMushFunctions,term)(self,terms)
			else: 
				# Not a match, so simply add what we found so far to the results string and update the line.
				rStr += self.line[0:i]
				self.line = self.line[i:]

		return rStr

	# instead of continuing with current line, evaluates a different string with the same context.
	def stringEval(self,s):
		e = EvalEngine(s,self.enactor,self.obj,self.listElem,self.listPos)
		e.registers = self.registers
		return e.eval("")

	def evalTerms(self,terms):
		results = []
		for term in self.splitTerms(terms):
			results.append(self.stringEval(term) if term != " " else " ")
		return results

	def evalOneTerm(self,term):
		return self.stringEval(term)

	def eval(self,stops):
		
		rStr = ""

		# ignore empty lines.
		if (self.line == None):
			return ""
			
		# first part of a line is always in fn evaluation mode.
		rStr += self._eval_fn()

		# Now loop through the rest of the string until we reach our stopchars or a special char.
		specialchars = "\[%#]" if self.listPos != -1 else "\[%]"
		pattern = re.compile(f"[{stops}{specialchars}") 

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
				# Check for list element substitutions if they are specified.
				elif self.line[i] == '#':
					rStr += self.evalListSubstitutions(self.line[i+1])
					self.line = self.line[i+2:]
				# check for brackets and recurse if found.
				elif self.line[i] == '[':
					e = EvalEngine(self.line[i+1:],self.enactor,self.obj,self.listElem,self.listPos)
					e.registers = self.registers
					rStr += e.eval("]")
					self.line = None if e.line == None else e.line[1:]
				
				# we must have found one of the stop chars. exit.
				else:
					self.line = self.line[i:]
					return rStr

		return rStr

def evalAttribute(ctx,dbref,attr):

	if attr not in mush.db[dbref]:
		return ""
	else:
		e = EvalEngine(mush.db[dbref][attr],ctx.enactor,dbref,ctx.listElem,ctx.listPos)
		return e.eval("")
	
class MushFunctions():
	def __init__(self):
		pass

	def fn_add(self,ctx,terms):
		rval = 0
		for t in ctx.evalTerms(terms):
			rval += ctx.numify(t)
		return str(rval)

	def fn_and(self,ctx,terms):

		for t in ctx.evalTerms(terms):
			if (ctx.boolify(t) == False):
				return "0"
		return "1"

	def fn_alphamax(self,ctx,terms):
		terms = ctx.evalTerms(terms)
		terms.sort(reverse=True)
		return terms[0]

	def fn_alphamin(self,ctx,terms):
		terms = ctx.evalTerms(terms)
		terms.sort()
		return terms[0]

	def fn_abs(self,ctx,terms):
		return str(abs(ctx.numify(ctx.evalOneTerm(terms))))

	def fn_after(self,ctx,terms):
		terms = ctx.evalTerms(terms)
		if (len(terms) != 2):
			return "#-1 Function expects two arguments."
		words = terms[0].split(terms[1],1)
		return words[1] if len(words) > 1 else ""
		
	def fn_acos(self,ctx,terms):
		return str(math.acos(ctx.numify(ctx.evalOneTerm(terms))))
		
	def fn_andflags(self,ctx,terms):
		return self.fn_notimplemented(ctx)

	def fn_ansi(self,ctx,terms):
		return self.fn_notimplemented(ctx)

	def fn_ansiif(self,ctx,terms):
		return self.fn_notimplemented(ctx)

	def fn_atrlock(self,ctx,terms):
		return self.fn_notimplemented(ctx)

	def fn_beep(self,ctx,terms):
		return self.fn_notimplemented(ctx)

	def fn_can_see(self,ctx,terms):
		return self.fn_notimplemented(ctx)

	def fn_change(self,ctx,terms):
		return self.fn_notimplemented(ctx)

	def fn_clone(self,ctx,terms):
		return self.fn_notimplemented(ctx)

	def fn_cmds(self,ctx,terms):
		return self.fn_notimplemented(ctx)

	def fn_conn(self,ctx,terms):
		return self.fn_notimplemented(ctx)

	def fn_convfirston(self,ctx,terms):
		return self.fn_notimplemented(ctx)

	def fn_controls(self,ctx,terms):
		return self.fn_notimplemented(ctx)

	def fn_convtime(self,ctx,terms):
		return self.fn_notimplemented(ctx)

	def fn_cstats(self,ctx,terms):
		return self.fn_notimplemented(ctx)

	def fn_decrypt(self,ctx,terms):
		return self.fn_notimplemented(ctx)

	def fn_descfun(self,ctx,terms):
		return self.fn_notimplemented(ctx)

	def fn_doing(self,ctx,terms):
		return self.fn_notimplemented(ctx)

	def fn_elock(self,ctx,terms):
		return self.fn_notimplemented(ctx)

	def fn_encrypt(self,ctx,terms):
		return self.fn_notimplemented(ctx)

	def fn_entrances(self,ctx,terms):
		return self.fn_notimplemented(ctx)

	def fn_evalthunks(self,ctx,terms):
		return self.fn_notimplemented(ctx)

	def fn_findable(self,ctx,terms):
		return self.fn_notimplemented(ctx)

	def fn_flags(self,ctx,terms):
		return self.fn_notimplemented(ctx)

	def fn_fold(self,ctx,terms):
		return self.fn_notimplemented(ctx)

	def fn_force(self,ctx,terms):
		return self.fn_notimplemented(ctx)

	def fn_grep(self,ctx,terms):
		return self.fn_notimplemented(ctx)

	def fn_grepi(self,ctx,terms):
		return self.fn_notimplemented(ctx)

	def fn_hasattrp(self,ctx,terms):
		return self.fn_notimplemented(ctx)

	def fn_hasattrpval(self,ctx,terms):
		return self.fn_notimplemented(ctx)

	def fn_haspower(self,ctx,terms):
		return self.fn_notimplemented(ctx)

	def fn_hasthunk(self,ctx,terms):
		return self.fn_notimplemented(ctx)

	def fn_hidden(self,ctx,terms):
		return self.fn_notimplemented(ctx)

	def fn_hilite(self,ctx,terms):
		return self.fn_notimplemented(ctx)

	def fn_htmlescape(self,ctx,terms):
		return self.fn_notimplemented(ctx)

	def fn_htmlok(self,ctx,terms):
		return self.fn_notimplemented(ctx)

	def fn_asin(self,ctx,terms):
		return str(math.asin(ctx.numify(ctx.evalOneTerm(terms))))

	def fn_atan(self,ctx,terms):
		return str(math.atan(ctx.numify(ctx.evalOneTerm(terms))))

	def fn_notimplemented(self,ctx):
		return "#-1 Function Not Implemented"

	def fn_aposs(self,ctx,terms):

		
		dbref = ctx.dbrefify(ctx.evalOneTerm(terms))
		if not mush.db.validDbref(dbref):
			return "#-1 No Match"

		sex = evalAttribute(ctx,dbref,"SEX").upper()
		rval = "its"

		if (sex=="MALE" or sex == "M" or sex == "MAN"):
			rval = "his"
		elif(sex=="FEMALE" or sex =="F" or sex == "WOMAN" ):
			rval = "hers"
		elif(sex == "PLURAL"):
			rval = "theirs"
		return rval

	def fn_art(self,ctx,terms):
		terms = ctx.evalOneTerm(terms)
		return "an" if terms != None and terms[0] in "AEIOUaeiou" else "a"
		
	# takes up to ten lists of numbers and averages. 
	# lists are space delimited and there is a comma between each list
	def fn_avg(self,ctx,terms):

		rval = 0
		count = 0		
		for l in ctx.evalTerms(terms):
			for term in l.split(' '):
				count += 1
				rval += ctx.numify(term)

		return str(round(rval/count,6))

	def fn_before(self,ctx,terms):
		terms = ctx.evalTerms(terms)
		if (len(terms) != 2):
			return "#-1 Function expects two arguments."
		words = terms[0].split(terms[1],1)
		return words[0] if len(words) > 1 else ""

	def fn_capstr(self,ctx,terms):
		return ctx.evalOneTerm(terms).capitalize()
		
	def fn_cat(self,ctx,terms):
		return " ".join(ctx.evalTerms(terms))

	def fn_ceil(self,ctx,terms):
		return str(math.ceil(ctx.numify(ctx.evalOneTerm(terms))))

	def fn_center(self,ctx,terms):
		terms = ctx.evalTerms(terms)
		if (len(terms) < 2 or len(terms) > 3):
			return "#-1 Function expects 2 or 3 arguments."

		width = ctx.numify(terms[1])
		pad = " " if len(terms) < 3 else terms[2]

		return terms[0].center(width,pad)

	def fn_comp(self,ctx,terms):
		terms = ctx.evalTerms(terms)
		if (len(terms) != 2):
			return "#-1 Function expects 2 arguments."

		val = 0
		if (terms[0] < terms[1]): 
			val = -1
		elif (terms[0] > terms[1]):
			val = 1

		return str(val)

	def fn_clone(self,ctx,terms):

		dbref = ctx.dbrefify(ctx.evalOneTerm(terms))
		if not mush.db.validDbref(dbref):
			return "#-1 No Match"

		o = mush.db[dbref]
		if (o.flags & (ObjectFlags.ROOM | ObjectFlags.PLAYER)):
			mush.msgDbref(enactor,"You can only clone things and exits.")
			return "#-1"
		# BUGBUG This is not implemented yet. Needs to be completed.

	def fn_con(self,ctx,terms):
		dbref = ctx.dbrefify(ctx.evalOneTerm(terms))
		if not mush.db.validDbref(dbref):
			return "#-1 No Match"

		val =  -1 if len(mush.db[dbref].contents) == 0 else mush.db[dbref].contents[0]
		return str(val)

	def fn_convsecs(self,ctx,terms):
		return str(time.asctime(time.localtime(ctx.numify(ctx.evalOneTerm(terms)))))

	def fn_or(self,ctx,terms):
		for t in ctx.evalTerms(terms):
			if (ctx.boolify(t) == True):
				return "1"

		return "0"

	def fn_cos(self,ctx,terms):
		return str(math.cos(ctx.numify(ctx.evalOneTerm(terms))))

	def fn_create(self,ctx,terms):

		terms = ctx.evalTerms(terms)
		if (len(terms)<1 or len(terms)>2):
			return "#-1 Function expects 1 or 2 arguments."

		dbref = mush.db.newObject(mush.db[ctx.enactor])
		mush.db[dbref]["NAME"] = terms[0]
		mush.msgDbref(ctx.enactor,f"Object named {terms[0]} created with ref #{dbref}.")
		mush.log(2,f"{mush.db[ctx.enactor].name}(#{ctx.enactor}) created object named {terms[0]} (#{dbref}).")
		return f"#{dbref}"
	
	def fn_ctime(self,ctx,terms):
		dbref = ctx.dbrefify(ctx.evalOneTerm(terms))
		if not mush.db.validDbref(dbref):
			return "#-1 No Match"

		return time.ctime(mush.db[dbref].creationTime)

	#
	# takes a *string* as argument, and finds the last integer part and subs one from that.
	# so dec(hi3) => hi2, dec(1.2)=>1.1 
	# 
	def fn_dec(self,ctx,terms):

		term = ctx.evalOneTerm(terms)
		m = re.search(r'-?\d+$',term)
		if (m == None):
			return "#-1 Argument does not end in integer."

		return term[0:m.start()]+str(ctx.numify(m.group())-1)

	def fn_default(self,ctx,terms):

		terms = ctx.evalTerms(terms)
		if len(terms) != 2:
			return "#-1 Function exects two arguments."

		(dbref,attr) = ctx.getObjAttr(terms[0])
		return mush.db[dbref][attr] if attr in mush.db[dbref] else terms[1]

	def fn_delete(self,ctx,terms):
		
		terms = ctx.evalTerms(terms)
		if len(terms) != 3:
			return "#-1 Function expects three arguments."

		start 	= ctx.numify(terms[1])
		length 	= ctx.numify(terms[2])

		return terms[0][0:start]+terms[0][start+length:]

	def fn_die(self,ctx,terms):
		
		terms = ctx.evalTerms(terms)
		if len(terms) != 2:
			return "#-1 Function expects two arguments."

		return str(sum([random.randint(1,ctx.numify(terms[1])) for x in range(ctx.numify(terms[0]))]))

	def fn_dig(self,ctx,terms):
		
		eback = None
		eout = None 
		terms = ctx.evalTerms(terms)
		if len(terms) < 1 or len(terms) > 3:
			return "#-1 Function expects one to three arguments."

		if (len(terms) == 3):
			eout = terms[1]
			eback = terms[2]
		if (len(terms)) == 2:
			eout = terms[1]

		return f"#{commands.doDig(mush.db[ctx.enactor],terms[0],eout,eback)}"

	def fn_dist2d(self,ctx,terms):
		
		terms = ctx.evalTerms(terms)
		if len(terms) != 4:
			return "#-1 Function expects four arguments."

		x1 = ctx.numify(terms[0])
		y1 = ctx.numify(terms[1])
		x2 = ctx.numify(terms[2])
		y2 = ctx.numify(terms[3])
		return str(round(math.sqrt((x2 - x1)*(x2 - x1) + (y2 - y1) * (y2 - y1)),6))

	def fn_dist3d(self,ctx,terms):
		
		terms = ctx.evalTerms(terms)
		if len(terms) != 6:
			return "#-1 Function expects six arguments."

		x1 = ctx.numify(terms[0])
		y1 = ctx.numify(terms[1])
		z1 = ctx.numify(terms[2])
		x2 = ctx.numify(terms[3])
		y2 = ctx.numify(terms[4])
		z2 = ctx.numify(terms[5])

		return str(round(math.sqrt((x2 - x1)*(x2 - x1) + (y2 - y1) * (y2 - y1) + (z2 - z1) * (z2 - z1)),6))

	def fn_div(self,ctx,terms):
		
		terms = ctx.evalTerms(terms)
		if len(terms) != 2:
			return "#-1 Function expects two arguments."
		
		return str(ctx.numify(terms[0])//ctx.numify(terms[1]))

	def fn_e(self,ctx,terms):
		if len(terms) != 0:
			return "#-1 Function expects zero arguments."
		return "2.718281"

	def fn_edefault(self,ctx,terms):

		terms = ctx.evalTerms(terms)
		if len(terms) != 2:
			return "#-1 Function exects two arguments." 

		(dbref,attr) = ctx.getObjAttr(terms[0])
		e = EvalEngine(mush.db[dbref][attr] if attr in mush.db[dbref] else terms[1],ctx.enactor,ctx.obj,ctx.listElem,ctx.listPos)
		return e.eval("")

	def fn_edit(self,ctx,terms):
		
		terms = ctx.evalTerms(terms)
		if len(terms) != 3:
			return "#-1 Function expects three arguments."

		if (terms[1] == '$'):
			s = terms[0] + terms[2]
		elif (terms[1] == '^'):
			s = terms[2] + terms[0]
		else:
			s = terms[0].replace(terms[1],terms[2])
		
		return s

	def fn_elem(self,ctx,terms):
		return self.fn_element(ctx,terms)

	def fn_element(self,ctx,terms):
		
		terms = ctx.evalTerms(terms)
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


	def fn_elements(self,ctx,terms):
		
		terms = ctx.evalTerms(terms)
		if (len(terms) < 2 or len(terms) > 3):
			return "#-1 Function expects two or three arguments."

		sep = terms[2][0] if len(terms) == 3 else ' '
		elements = terms[0].split(sep)
		indices = terms[1].split()
		rval = []

		for i in indices:
			rval.append(elements[ctx.numify(i)-1])

		return sep.join(rval)

	def fn_emit(self,ctx,terms):
		mush.msgLocation(mush.db[ctx.obj].location,ctx.evalOneTerm(terms))
		return ""

	def fn_enumerate(self,ctx,terms):
		
		terms = ctx.evalTerms(terms)
		sep = ' ' if len(terms) < 2 else terms[1][0]
		connective = 'and' if len(terms) < 3 else terms[2]
		items = terms[0].split(sep)

		if len(items) < 2:
			return terms[0]

		if len(items) == 2:
			return f"{items[0]} {connective} {items[1]}"

		return ", ".join(items[:-1])+", " + connective + " " + items[-1]

	def fn_eq(self,ctx,terms):

		terms = ctx.evalTerms(terms)	
		if (len(terms) != 2):
			return "#-1 Function expects two arguments"

		if (not ctx.isnum(terms[0] or not ctx.isnum(terms[1]))):
			return "#-1 Arguments must be numbers"

		return "1" if ctx.numify(terms[0]) == ctx.numify(terms[1]) else "0"


	def escaper(self,match):
		return f"\\{match.group(0)}"

	def fn_escape(self,ctx,terms):
		return "\\" + re.sub(r"[%;{}\[\]]",self.escaper,terms)

	def fn_eval(self,ctx,terms):
		
		terms = ctx.evalTerms(terms)	
		if (len(terms) != 2):
			return "#-1 Function expects two arguments"


		dbref = ctx.dbrefify(terms[0])
		attr = terms[1].upper()
		if attr in mush.db[dbref]:
			e = EvalEngine(mush.db[dbref][attr],ctx.enactor,ctx.obj,ctx.listElem,ctx.listPos)
			return e.eval("")

		return ""

	#
	# weird functino. Based on documentation, returns the first exit for object. 
	# does so if its a room. 
	# otherwise, returns the first room in the location chain of the object.
	# for instance -- player in room X carrying object key:
	# th exit(key) -> returns dbref(X)
	#	
	def fn_exit(self,ctx,terms):

		terms = ctx.evalTerms(terms)
		if (len(terms) == 0):
			return "#-1"

		dbref = ctx.dbrefify(terms[0])
		if not mush.db.validDbref(dbref):
			return "#-1 No Match"
		
		if mush.db[dbref].flags & ObjectFlags.ROOM:
			for o in mush.db[dbref].contents:
				if mush.db[o].flags & ObjectFlags.EXIT:
					return str(o)
		else:
			while not mush.db[mush.db[dbref].location].flags & ObjectFlags.ROOM:
				dbref = mush.db[dbref].location
		
		return str(dbref)


	def fn_exp(self,ctx,terms):
		return str(round(math.exp(ctx.numify(ctx.evalOneTerm(terms))),6))

	def fn_extract(self,ctx,terms):
		
		terms = ctx.evalTerms(terms)
		if (len(terms) < 3 or len(terms) > 4):
			return "#-1 Function expects 3 or 4 arguments"

		sep = ' ' if len(terms) < 4 else terms[3][0]
		start = ctx.numify(terms[1]) - 1
		length = ctx.numify(terms[2]) 
		items = terms[0].split(sep)

		return sep.join(items[start:start+length])

	def fn_fdiv(self,ctx,terms):
		terms = ctx.evalTerms(terms)
		if len(terms) != 2:
			return "#-1 Function expects two arguments."

		return str(round(ctx.numify(terms[0])/ctx.numify(terms[1]),6))

	def fn_filter(self,ctx,terms):

		terms = ctx.evalTerms(terms)
		if (len(terms)<2 or len(terms) > 3):
			return "#-1 Function expects two or three arguments."

		(dbref,attr) = ctx.getObjAttr(terms[0])
		#
		# BUGBUG Not complete.
		#
		return ""

	def fn_first(self,ctx,terms):

		terms = ctx.evalTerms(terms)
		if (len(terms) > 2):
			return "#-1 Function expects one or two arguments."

		# and empty set of arguements returns empty.
		if (len(terms) == 0):
			return ""

		sep = ' ' if len(terms) != 2 else terms[1][0]
		return terms[0].split(sep)[0]


	def fn_flip(self,ctx,terms):
		return ctx.evalOneTerm(terms)[::-1]

	def fn_floor(self,ctx,terms):
		return str(math.floor(ctx.numify(ctx.evalOneTerm(terms))))

	def fn_foreach(self,ctx,terms):

		terms = ctx.evalTerms(terms)
		if (len(terms) != 2):
			return "#-1 Function expects two arguments."
		(dbref,attr) = ctx.getObjAttr(terms[0])

		
		rVal = ""
		if attr in mush.db[dbref]:
			for letter in terms[1]:
				e = EvalEngine(mush.db[dbref][attr],ctx.enactor,ctx.obj,ctx.listElem,ctx.listPos)
				e.registers[0] = letter
				rVal += e.eval("")

		return rVal

	def fn_freeattr(self,ctx,terms):
		
		terms = ctx.evalTerms(terms)
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

	def fn_fullname(self,ctx,terms):
		dbref = ctx.dbrefify(ctx.evalOneTerm(terms))
		if not mush.db.validDbref(dbref):
			return "#-1 No Match"
		return mush.db[dbref]["NAME"]

	def fn_functions(self,ctx,terms):
		return ' '.join([x[3:] for x in dir(self) if x[0:3] == "fn_"])

	def fn_get(self,ctx,terms):

		term  = ctx.evalOneTerm(terms)
		if (term == ""):
			return "#-1 Function expects one argument."

		(dbref,attr) = ctx.getObjAttr(term)
		if not mush.db.validDbref(dbref):
			return "#-1 No Match"

		return "" if attr not in mush.db[dbref] else mush.db[dbref][attr]

	def fn_get_eval(self,ctx,terms):
		
		term = ctx.evalOneTerm(terms)
		if (term == ""):
			return "#-1 Function expects two arguments."
		(dbref,attr) = ctx.getObjAttr(term)
		if not mush.db.validDbref(dbref):
			return "#-1 No Match"

		return ctx.evalString(mush.db[dbref][attr]) if attr in mush.db[dbref] else ""
			
	def fn_grab(self,ctx,terms):
		
		terms = ctx.evalTerms(terms)
		if (len(terms) < 2 or len(terms) > 3):
			return "#-1 Function expects two or three arguments."

		sep = terms[2][0] if len(terms) == 3 else ' '
		elements = terms[0].split(sep)
		pattern = terms[1]
		
		for item in elements: 
			if fnmatch.fnmatch(item,pattern):
				return item
			
		return ""

	def fn_graball(self,ctx,terms):

		terms = ctx.evalTerms(terms)
		if (len(terms) < 2 or len(terms) > 3):
			return "#-1 Function expects two or three arguments."
		
		sep = terms[2][0] if len(terms) == 3 else ' '
		elements = terms[0].split(sep)
		pattern = terms[1]
		
		return  sep.join([x for x in elements if fnmatch.fnmatch(x,pattern)])

	def fn_gt(self,ctx,terms):
		
		terms = ctx.evalTerms(terms)
		if (len(terms) != 2):
			return "#-1 Function expects two arguments"

		if (not ctx.isnum(terms[0] or not ctx.isnum(terms[1]))):
			return "#-1 Arguments must be numbers"

		return "1" if ctx.numify(terms[0]) > ctx.numify(terms[1]) else "0"

	def fn_gte(self,ctx,terms):

		terms = ctx.evalTerms(terms)
		if (len(terms) != 2):
			return "#-1 Function expects two arguments"

		if (not ctx.isnum(terms[0] or not ctx.isnum(terms[1]))):
			return "#-1 Arguments must be numbers"

		return "1" if ctx.numify(terms[0]) >= ctx.numify(terms[1]) else "0"

	def fn_hasattr(self,ctx,terms):

		terms = ctx.evalTerms(terms)
		
		if (len(terms) != 2):
			return "#-1 Function expects two arguments"
		dbref = ctx.dbrefify(terms[0])
		return "1" if dbref != None and terms[1].upper() in mush.db[dbref] else "0"

	def fn_hasflag(self,ctx,terms):

		terms = ctx.evalTerms(terms)
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

	def fn_hastype(self,ctx,terms):

		terms = ctx.evalTerms(terms)
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

	def fn_home(self,ctx,terms):

		dbref = ctx.dbrefify(ctx.evalOneTerm(terms))
		if not mush.db.validDbref(dbref):
			return "#-1 No Match"

		return f"#{mush.db[dbref].home}"

	def fn_idle(self,ctx,terms):

		dbref = ctx.dbrefify(ctx.evalTerms(terms)[0])
		if not mush.db.validDbref(dbref) or not mush.db[dbref].flags & ObjectFlags.CONNECTED:
			return "-1"
		return int(mush.server.get_client_idle(mush.dbreftoPid[dbref]))

	def fn_idlesecs(self,ctx,terms):
		return self.fn_idle(ctx,terms)

	def fn_if(self,ctx,terms):

		terms = ctx.evalTerms(terms)
		if (len(terms) != 2 and len(terms) != 3):
			return "#-1 Function expects two or three arguments"

		if (len(terms) == 2):
			terms.append("")

		return terms[1] if ctx.boolify(terms[0]) else terms[2]

	def fn_ifelse(self,ctx,terms):
		return self.fn_if(ctx,terms)

	def fn_inc(self,ctx,terms):

		term = ctx.evalOneTerm(terms)
		m = re.search(r'-?\d+$',term)
		if (m == None):
			return "#-1 Argument does not end in integer."

		return term[0:m.start()]+str(ctx.numify(m.group())+1)




#
# Awful hack here. The parser doesn't like empty arguments like (<term>, ,<term>)
# the ,<space>, above will not be returned as a term even though its valid ehre.
# Probably this should be fixed.
#
	def fn_index(self,ctx,terms):

		terms = ctx.evalTerms(terms)
# HACK HERE
		if (len(terms) < 3):
			return ""
		if (len(terms) < 4):
			terms.insert(1," ")
	
		sep = terms[1]
		start = ctx.numify(terms[2]) - 1
		length = ctx.numify(terms[3]) 
		items = terms[0].split(sep)

		return sep.join(items[start:start+length])

	def fn_inlist(self,ctx,terms):

		terms = ctx.evalTerms(terms)

		# this is for pennmush compat. 
		if (len(terms) == 0 or (len(terms) == 1 and terms[0] =="")):
			return "1"
		if (len(terms) == 1):
			return "0"

		sep = " " if len(terms) < 3 else terms[2]
		return "1" if terms[1] in terms[0].split(sep) else "0"

	def fn_insert(self,ctx,terms):

		terms = ctx.evalTerms(terms)
		if (len(terms) != 3 and len(terms) !=4):
			return "#-1 Function expects three or four arguments."

		sep = " " if len(terms) == 3 else terms[3][0]
		index = ctx.numify(terms[1]) -1
		items = terms[0].split(sep)

		if (index > -1 and index < len(items)):
			items.insert(index,terms[2])

		return sep.join(items)

	def fn_invoke(self,ctx,terms):
		return self.fn_notimplemented(ctx)

	def fn_isdaylight(self,ctx,terms):
		return self.fn_notimplemented(ctx)

	def fn_isdbref(self,ctx,terms):
		term = ctx.evalOneTerm(terms)
		if term[0] != '#':
			return "0"
		if not ctx.isnum(term[1:]):
			return "0"
		return "1" if mush.db.validDbref(ctx.numify(term[1:])) else "0"

	def fn_isnum(self,ctx,terms):
		return "1" if ctx.isInt(ctx.evalOneTerm(terms)) else "0"


	def fn_isword(self,ctx,terms):
		return "1" if ctx.evalOneTerm(terms).isalpha() else "0"

	def fn_items(self,ctx,terms):
		return self.fn_words(ctx,terms)

	def fn_words(self,ctx,terms):
		terms = ctx.evalTerms(terms)
		if len(terms) == 0 or (len(terms) == 1 and terms[0] ==""):
			return "0"
		if len(terms) > 2:
			return "#-1 Function expects two or three arguments."

		sep = " " if len(terms) == 1 else terms[1][0]
		return str(len(terms[0].split(sep)))

	def fn_iter(self,ctx,terms):
		
		terms = ctx.splitTerms(terms)
		if (len(terms) < 2 or len(terms) > 4):
			return "#-1 Function expects between two and four arguments."

		sep = " " if len(terms) < 3 else terms[2][0]
		osep = " " if len(terms) < 4 else terms[3][0]
		items = ctx.evalOneTerm(terms[0]).split(sep)

		rlist = []
		n = 1
		for item in items: 

			e = EvalEngine(terms[1],ctx.enactor,ctx.obj,item,n)
			rlist.append(e.eval(''))
			n+=1

		return osep.join(rlist)


	def fn_lang(self,ctx,terms):
		return self.fn_notimplemented(ctx)

	def fn_last(self,ctx,terms):
		terms = ctx.evalTerms(terms)
		if (len(terms) > 2):
			return "#-1 Function expects one or two arguments."

		# and empty set of arguements returns empty.
		if (len(terms) == 0):
			return ""

		sep = ' ' if len(terms) != 2 else terms[1][0]
		return terms[0].split(sep)[-1]


	def fn_lattr(self,ctx,terms):

		(dbref,pattern) = ctx.getObjAttr(ctx.evalOneTerm(terms))
		if not mush.db.validDbref(dbref):
			return "#-1 No match."

		pattern = "*" if pattern == "" or pattern == None else pattern
		keys = [x for x in mush.db[dbref] if fnmatch.fnmatch(x,pattern)]
		
		if len(keys) == 0:
			return "#-1 No match."
		
		return " ".join(keys)


	def fn_lcon(self,ctx,terms):
		dbref = ctx.dbrefify(ctx.evalOneTerm(terms))
		return "#-1" if not mush.db.validDbref(dbref) else " ".join([f"#{x}" for x in mush.db[dbref].contents])

	def fn_lcstr(self,ctx,terms):
		return ctx.evalOneTerm(terms).lower()

	def fn_loc(self,ctx,terms):
		if (terms==""):
			return "#-1"
		dbref = ctx.dbrefify(ctx.evalOneTerm(terms))
		return "#-1" if not mush.db.validDbref(dbref) else f"#{mush.db[dbref].location}"

	def fn_locate(self,ctx,terms):
		return self.fn_notimplemented(ctx)

	def fn_lock(self,ctx,terms):
		return self.fn_notimplemented(ctx)

	def fn_log(self,ctx,terms):
		terms = ctx.evalOneTerm(terms)
		if not ctx.isnum(terms):
			return "-inf"
		return str(round(math.log(ctx.numify(terms)),6))

	def fn_lparent(self,ctx,terms):
		return self.fn_notimplemented(ctx)

	def fn_lsearch(self,ctx,terms):
		return self.fn_notimplemented(ctx)

	def fn_lsearchr(self,ctx,terms):
		return self.fn_notimplemented(ctx)

	def fn_lstats(self,ctx,terms):
		return self.fn_notimplemented(ctx)

	def fn_lt(self,ctx,terms):

		terms = ctx.evalTerms(terms)
		if (len(terms) != 2):
			return "#-1 Function expects two arguments"

		if (not ctx.isnum(terms[0] or not ctx.isnum(terms[1]))):
			return "#-1 Arguments must be numbers"

		return "1" if ctx.numify(terms[0]) < ctx.numify(terms[1]) else "0"


	def fn_lte(self,ctx,terms):

		terms = ctx.evalTerms(terms)
		if (len(terms) != 2):
			return "#-1 Function expects two arguments"

		if (not ctx.isnum(terms[0] or not ctx.isnum(terms[1]))):
			return "#-1 Arguments must be numbers"

		return "1" if ctx.numify(terms[0]) <= ctx.numify(terms[1]) else "0"


	def fn_lwho(self,ctx,terms):
		#
		# no work done to implement the "see who an object can see mode"
		#
		return " ".join(["#"+str(x) for x in mush.dbrefToPid])


	def fn_map(self,ctx,terms):
		
		terms = ctx.evalTerms(terms)
		if (len(terms) < 2 or len(terms) > 3):
			return "#-1 Function expects two or three arguments."
		
		sep = " " if len(terms) < 3 else terms[2][0]
		items = terms[1].split(sep)

		if terms[0].find('/') != -1:
			(dbref,attr) = ctx.getObjAttr(terms[0])
		else:
			dbref = ctx.enactor
			attr = terms[0].upper()

		if not mush.db.validDbref(dbref) or attr not in mush.db[dbref]:
			return ""

		rlist = []
		for item in items: 
			e = EvalEngine(mush.db[dbref][attr],ctx.enactor,ctx.obj)
			e.registers[0] = item
			rlist.append(e.eval(''))
	
		return sep.join(rlist)


	def fn_match(self,ctx,terms):

		terms = ctx.evalTerms(terms)
		if (len(terms) < 2 or len(terms) > 3):
			return "#-1 Function expects two or three arguments."
		sep = " " if len(terms) == 2 else terms[2][0]

		i = 1
		for item in terms[0].split(sep):
			if fnmatch.fnmatch(item,terms[1]):
				return str(i)
			i += 1

		return "0"


	def fn_member(self,ctx,terms):
		return self.fn_match(ctx,terms)

	def fn_matchall(self,ctx,terms):

		terms = ctx.evalTerms(terms)
		if (len(terms) < 2 or len(terms) > 3):
			return "#-1 Function expects two or three arguments."
		sep = " " if len(terms) == 2 else terms[2][0]

		i = 1
		results = []
		for item in terms[0].split(sep):
			if fnmatch.fnmatch(item,terms[1]):
				results.append(str(i))
			i += 1

		return "" if len(results) == 0 else " ".join(results)

	def fn_max(self,ctx,terms):
		m = 0
		for x in ctx.evalTerms(terms):
			if ctx.isnum(x) and ctx.numify(x) > m:
				m = ctx.numify(x)
		return str(m)

	def fn_merge(self,ctx,terms):
		return self.fn_notimplemented(ctx)


	def fn_mid(self,ctx,terms):
		terms = ctx.evalTerms(terms)
		if len(terms) != 3:
			return "#-1 Function expects three arguments."
		if not ctx.isInt(terms[1] or not ctx.isInt(terms[2])):
			return "#-1 Arguments two and three must be integers."
		start = ctx.numify(terms[1])
		end = start + ctx.numify(terms[2])

		return terms[0][start:end]


	def fn_min(self,ctx,terms):
		m = 999999999
		for x in ctx.evalTerms(terms):
			if ctx.isnum(x) and ctx.numify(x) < m:
				m = ctx.numify(x)
		return str(m)

	def fn_mix(self,ctx,terms):
		
		terms = ctx.evalTerms(terms)
		if (len(terms) < 3 or len(terms) >4):
			return "Function expects 3 or 4 arguments."

		sep = " " if len(terms) < 4 else terms[3][0]
		items1 = terms[1].split(sep)
		items2 = terms[2].split(sep)

		if (len(items1) != len(items2)):
			return "#-1 Lists must be of equal length"

		if terms[0].find('/') != -1:
			(dbref,attr) = ctx.getObjAttr(terms[0])
		else:
			dbref = ctx.enactor
			attr = terms[0].upper()

		if not mush.db.validDbref(dbref) or attr not in mush.db[dbref]:
			return ""

		rlist = []
		for i in range(len(items1)):
			e = EvalEngine(mush.db[dbref][attr],ctx.enactor,ctx.obj)
			e.registers[0] = items1[i]
			e.registers[1] = items2[i]
			rlist.append(e.eval(''))
	
		return sep.join(rlist)


	def fn_mod(self,ctx,terms):
		terms = ctx.evalTerms(terms)

		if (len(terms) !=2):
			return "#-1 Function expects two arguments."
		if (not ctx.isInt(terms[0]) or not ctx.isInt(terms[1])):
			return "#-1 Arguments must be integers."
		return str(ctx.numify(terms[0])%ctx.numify(terms[1]))

	def fn_money(self,ctx,terms):
		return self.fn_notimplemented(ctx)
	def fn_mount(self,ctx,terms):
		return self.fn_notimplemented(ctx)

	def fn_mtime(self,ctx,terms):
		dbref = ctx.dbrefify(ctx.evalOneTerm(terms))
		if not mush.db.validDbref(dbref):
			return "#-1"
		return time.ctime(mush.db[dbref].lastModified)


	def fn_mudname(self,ctx,terms):
		return _MUSHNAME

	def fn_mul(self,ctx,terms):
		val = 1
		for x in ctx.evalTerms(terms):
			val = val * (0 if not ctx.isnum(x) else ctx.numify(x))
		return str(val)

	def fn_munge(self,ctx,terms):
		return self.fn_notimplemented(ctx)


	def fn_mwho(self,ctx,terms):
		return " ".join(["#"+str(x) for x in mush.dbrefToPid if not mush.db[x].flags & ObjectFlags.DARK])

	def fn_name(self,ctx,terms):
		terms = ctx.evalTerms(terms)
		if len(terms) == 0:
			return "#-1"
		if len(terms) > 1:
			return "#-1 Rename not implemented in name() function."
		dbref = ctx.dbrefify(terms[0])
		return "#-1" if not mush.db.validDbref(dbref) else mush.db[dbref].name

	def fn_nearby(self,ctx,terms):
		terms = ctx.evalTerms(terms)
		if len(terms) != 2:
			return "#-1 Function expects two arguments."
		dbref1 = ctx.dbrefify(terms[0])
		dbref2 = ctx.dbrefify(terms[1])
		if not mush.db.validDbref(dbref1) or not mush.db.validDbref(dbref2):
			return "0"
		o1 = mush.db[dbref1]
		o2 = mush.db[dbref2]

		return "1" if o1.location == o2.location or o1 in o2.contents or o2 in o1.contents else "0"

	def fn_neq(self,ctx,terms):

		terms = ctx.evalTerms(terms)	
		if (len(terms) != 2):
			return "#-1 Function expects two arguments"

		if (not ctx.isnum(terms[0] or not ctx.isnum(terms[1]))):
			return "#-1 Arguments must be numbers"

		return "1" if ctx.numify(terms[0]) != ctx.numify(terms[1]) else "0"

	def fn_newthunk(self,ctx,terms):
		return self.fn_notimplemented(ctx)

	def fn_next(self,ctx,terms):
		return self.fn_notimplemented(ctx)

	def fn_not(self,ctx,terms):
		return "0" if ctx.boolify(ctx.evalOneTerm(terms)) else "1"

	def fn_nwho(self,ctx,terms):
		return str(len(["#"+str(x) for x in mush.dbrefToPid if not mush.db[x].flags & ObjectFlags.DARK]))

	def fn_num(self,ctx,terms):
		dbref = ctx.dbrefify(ctx.evalOneTerm(terms))
		return f"#{dbref}" if mush.db.validDbref(dbref) else "#-1"

	def fn_obj(self,ctx,terms):

		rval = "it"
		dbref = ctx.dbrefify(ctx.evalOneTerm(terms))
		if not mush.db.validDbref(dbref):
			return "#-1 No Match"

		sex = evalAttribute(ctx,dbref,"SEX").upper()

		if (sex=="MALE" or sex == "M" or sex == "MAN"):
			rval = "him"
		elif(sex=="FEMALE" or sex =="F" or sex == "WOMAN" ):
			rval = "her"
		elif(sex == "PLURAL"):
			rval = "they"
		return rval

	def fn_objeval(self,ctx,terms):
		return self.fn_notimplemented(ctx)

	def fn_objmem(self,ctx,terms):
		dbref = ctx.dbrefify(ctx.evalOneTerm(terms))
		return str(sys.getsizeof(dbref)) if mush.db.validDbref(dbref) else "#-1"

	def fn_oemit(self,ctx,terms):
		terms = ctx.evalTerms(terms)
		if (len(terms) != 2):
			return "Function expects two terms."
		mush.msgLocation(mush.db[ctx.obj].location,terms[1],ctx.dbrefify(terms[0]))
		return ""

	def fn_open(self,ctx,terms):
		terms = ctx.evalTerms(terms)
		if (len(terms)!=2):
			return "#-1 Function expects two arguments."
		if  self.fn_isdbref(ctx,terms[1]) == "0":
			return "#-1 Room argument must be a dbref."

		target = ctx.dbrefify(terms[1])
		if (not mush.db.validDbref(target) or not mush.db[target].flags & ObjectFlags.ROOM):
			return "#-1 Target must be a room."

		dbref = mush.db.newExit(mush.db[ctx.enactor])
		mush.db[dbref]["NAME"] = terms[0]
		mush.db[dbref].location = mush.db[ctx.enactor].location
		mush.db[dbref].home = ctx.dbrefify(terms[1])
		mush.db[ctx.enactor].contents.append(dbref)
		mush.msgDbref(ctx.enactor,f"Exit named {terms[0]} created with ref #{dbref}.")
		mush.log(2,f"{mush.db[ctx.enactor].name}(#{ctx.enactor}) dug exit named {terms[0]} (#{dbref}).")

		return f"#{dbref}"


	def fn_or(self,ctx,terms):

		for t in ctx.evalTerms(terms):
			if (ctx.boolify(t) == True):
				return "1"
		return "0"

	def fn_orflags(self,ctx,terms):
		return self.fn_notimplemented(ctx)


	def fn_owner(self,ctx,terms):

		#
		# attribute version not implemented.
		#
		dbref = ctx.dbrefify(ctx.evalOneTerm(terms))
		return f"#{mush.db[dbref].owner}" if mush.db.validDbref(dbref) else "#-1"


	def fn_parent(self,ctx,terms):
		return self.fn_notimplemented(ctx)

	def fn_parse(self,ctx,terms):
		return self.fn_iter(ctx,terms)

	def fn_passcheck(self,ctx,terms):
		return self.fn_notimplemented(ctx)

	def fn_pi(self,ctx,terms):
		return "3.141593"

	def fn_pemit(self,ctx,terms):
		# does not handle options. 
		terms = ctx.evalTerms(terms)
		if (len(terms) != 2):
			return "#-1 Function expects two arguments."

		dbref = ctx.dbrefify(terms[0])
		if mush.db.validDbref(dbref):
			mush.msgDbref(dbref,terms[1])
			mush.msgDbref(ctx.enactor,f"You pemit \"{terms[1]}\" to {mush.db[dbref].name}.")
			return ""

		return "I don't see that player here."


	def fn_playermem(self,ctx,terms):
		dbref = ctx.dbrefify(ctx.evalOneTerm(terms))
		
		if not mush.db.validDbref(dbref):
			return "#-1"

		mem = 0
		for o in mush.db:
			if o.owner == dbref:
				mem += sys.getsizeof(o.dbref)

		return str(mem)

	def fn_pmatch(self,ctx,terms):
		return self.fn_notimplemented(ctx)

	def fn_poll(self,ctx,terms):
		return self.fn_notimplemented(ctx)

	def fn_ports(self,ctx,terms):
		return self.fn_notimplemented(ctx)

	def fn_pos(self,ctx,terms):
		terms = ctx.evalTerms(terms)
		if (len(terms) != 2):
			return "#-1 Function expects two arguments."
		i = terms[1].find(terms[0])
		return str(i) if i != -1 else "#-1"


	def fn_poss(self,ctx,terms):

		rval = "its"
		dbref = ctx.dbrefify(ctx.evalOneTerm(terms))
		if not mush.db.validDbref(dbref):
			return "#-1 No Match"

		sex = evalAttribute(ctx,dbref,"SEX").upper()

		if (sex=="MALE" or sex == "M" or sex == "MAN"):
			rval = "his"
		elif(sex=="FEMALE" or sex =="F" or sex == "WOMAN" ):
			rval = "her"
		elif(sex == "PLURAL"):
			rval = "their"
		return rval

	def fn_power(self,ctx,terms):
		terms = ctx.evalTerms(terms)
		if (len(terms) !=2):
			return "#-1 Function expects two arguments."

		if not ctx.isnum(terms[0]) or not ctx.isnum(terms[1]):
			return "#-1 arguments must be numbers."

		if ctx.isInt(terms[0]) and ctx.isInt(terms[0]):
			return str(int(math.pow(ctx.numify(terms[0]),ctx.numify(terms[1]))))
		else:
			return str(round(math.pow(ctx.numify(terms[0]),ctx.numify(terms[1])),6))

	def fn_powers(self,ctx,terms):
		return self.fn_notimplemented(ctx)

	def fn_pushreg(self,ctx,terms):
		return self.fn_notimplemented(ctx)

	def fn_quota(self,ctx,terms):
		return self.fn_notimplemented(ctx)

	def fn_r(self,ctx,terms):
		val = ctx.numify(ctx.evalOneTerm(terms))
		return "#-1 Invalid register index." if (val < 0 or val > 9) else ctx.registers[val]

	# setq returns an empty string. setr returns the string stored.
	def fn_setq(self,ctx,terms):
		self.fn_setr(ctx,terms)
		return ""

	def fn_setr(self,ctx,terms):
		terms = ctx.evalTerms(terms)
		if len(terms) != 2:
			return "#-1 Function expects two arguments."
		val = ctx.numify(terms[0])
		if (val <0 or val > 9):
			return "#-1 Invalid register index."
		ctx.registers[val] = terms[1]
		return terms[1]

	def fn_rand(self,ctx,terms):
		num = ctx.evalOneTerm(terms)
		return "#-1 Argument must be an integer" if not ctx.isnum(num) else str(random.randint(0,ctx.numify(num)))

	def fn_recol(self,ctx,terms):
		return self.fn_notimplemented(ctx)

	def fn_remit(self,ctx,terms):
		terms = ctx.evalTerms(terms)
		if (len(terms) != 2):
			return "#-1 Function expects two arguments."

		dbref = ctx.dbrefify(terms[0])
		if not mush.db.validDbref(dbref):
			return "I can't find that."

		mush.msgLocation(dbref,terms[1])
		return ""

	def fn_remove(self,ctx,terms):
		terms = ctx.evalTerms(terms)
		if len(terms) > 3 or len(terms) < 2:
			return "#-1 Function expects two or three arguments."

		sep = " " if len(terms) < 3 else terms[2][0]
		found = False
		rList = []
		for x in terms[0].split(sep):
			if x != terms[1] or found:
				rList.append(x)
			else:
				found = True 

		return sep.join(rList)

	def fn_repeat(self,ctx,terms):

		terms = ctx.evalTerms(terms)
		if len(terms) != 2:
			return "#-1 Function expects two arguments."
		
		return terms[0]*ctx.numify(terms[1])


	def fn_replace(self,ctx,terms):
		terms = ctx.evalTerms(terms)
		if len(terms) > 4 or len(terms) < 3:
			return "#-1 Function expects three or four arguments."

		sep = " " if len(terms) < 4 else terms[3][0]
		i = ctx.numify(terms[1]) - 1
		words = terms[0].split(sep)

		if (i >= 0) and (len(words) > i):
			words[i] = terms[2]
			
		return sep.join(words)

	def fn_rest(self,ctx,terms):

		terms = ctx.evalTerms(terms)
		if (len(terms) > 2):
			return "#-1 Function expects one or two arguments."

		# and empty set of arguements returns empty.
		if (len(terms) == 0):
			return ""

		sep = ' ' if len(terms) != 2 else terms[1][0]
		return sep.join(terms[0].split(sep)[1:])

	def fn_reverse(self,ctx,terms):
		return self.fn_flip(ctx,terms)

	def fn_revwords(self,ctx,terms):

		terms = ctx.evalTerms(terms)
		if len(terms) < 1 or len(terms) > 2:
			return "#-1 Function expects one or two arguments."
		sep = " " if (len(terms)) != 2 else terms[1][0]
		words = terms[0].split(sep)
		words.reverse()
	
		return sep.join(words)

	def fn_right(self,ctx,terms):

		terms = ctx.evalTerms(terms)
		if len(terms) != 2:
			return "#-1 Function expects two arguments."

		return terms[0][-1*ctx.numify(terms[1]):]


	def fn_rjust(self,ctx,terms):

		terms = ctx.evalTerms(terms)
		if len(terms) < 2 or len(terms) > 3:
			return "#-1 Function expects two or three arguments."
		sep = " " if (len(terms)) != 3 else terms[2][0]		
		return terms[0].rjust(ctx.numify(terms[1]),sep)

	def fn_rloc(self,ctx,terms):
		return self.fn_notimplemented(ctx)

	def fn_rnum(self,ctx,terms):
		return self.fn_notimplemented(ctx)

	def fn_room(self,ctx,terms):
		dbref = ctx.dbrefify(ctx.evalOneTerm(terms))
		if not mush.db.validDbref(dbref):
			return "#-1"

		while not mush.db[dbref].flags & ObjectFlags.ROOM:
			dbref = mush.db[dbref].location
		return f"#{dbref}"

	def fn_round(self,ctx,terms):

		terms = ctx.evalTerms(terms)
		if len(terms) != 2:
			return "#-1 Function expects two arguments."

		r = ctx.numify(terms[1])
		r = 0 if r < 0 else r 
		r = 6 if r > 6 else r 
		val = round(ctx.numify(terms[0]),r)
		val = int(val) if r == 0 else val 

		return str(val)

	def fn_savetime(self,ctx,terms):
		return time.ctime(mush.lastSave)

	def fn_s(self,ctx,terms):
		return self.fn_notimplemented(ctx)

	def fn_scramble(self,ctx,terms):
		term = list(ctx.evalOneTerm(terms))
		random.shuffle(term)
		return ''.join(term)

	def fn_search(self,ctx,terms):
		return self.fn_notimplemented(ctx)

	def fn_secs(self,ctx,terms):
		return self.fn_notimplemented(ctx)

	def fn_secure(self,ctx,terms):
		return self.fn_notimplemented(ctx)

	def fn_sensenotify(self,ctx,terms):
		return self.fn_notimplemented(ctx)

	def fn_set(self,ctx,terms):
		return self.fn_notimplemented(ctx)

	def fn_setdiff(self,ctx,terms):

		terms = ctx.evalTerms(terms)
		if len(terms) < 2 or len(terms) > 3:
			return "#-1 Function expects two or three arguments."
		sep = " " if (len(terms)) != 3 else terms[2][0]	
		terms[0] = terms[0].split(sep)
		terms[1] = terms[1].split(sep)
		rlist = [x for x in terms[0] if x not in terms[1]]
		rlist.sort()
		return sep.join(rlist)

	def fn_setinter(self,ctx,terms):

		terms = ctx.evalTerms(terms)
		if len(terms) < 2 or len(terms) > 3:
			return "#-1 Function expects two or three arguments."
		sep = " " if (len(terms)) != 3 else terms[2][0]	
		terms[0] = terms[0].split(sep)
		terms[1] = terms[1].split(sep)
		rlist = [x for x in terms[0] if x in terms[1]]
		rlist.sort()
		return sep.join(rlist)

	def fn_setmount(self,ctx,terms):
		return self.fn_notimplemented(ctx)
		
	def fn_setunion(self,ctx,terms):

		terms = ctx.evalTerms(terms)
		if len(terms) < 2 or len(terms) > 3:
			return "#-1 Function expects two or three arguments."
		sep = " " if (len(terms)) != 3 else terms[2][0]	
		terms[0] = terms[0].split(sep)
		terms[1] = terms[1].split(sep)
		rlist = terms[0] + [x for x in terms[1] if x not in terms[0]]
		rlist.sort()
		return sep.join(rlist)


	def fn_shizzle(self,ctx,terms):
		return self.fn_notimplemented(ctx)


	def fn_shl(self,ctx,terms):

		terms = ctx.evalTerms(terms)
		if len(terms) != 2:
			return "#-1 Function expects two arguments."

		return str(ctx.numify(terms[0]) << ctx.numify(terms[1]))


	def fn_shr(self,ctx,terms):

		terms = ctx.evalTerms(terms)
		if len(terms) != 2:
			return "#-1 Function expects two arguments."

		return str(ctx.numify(terms[0]) >> ctx.numify(terms[1]))

	def fn_shuffle(self,ctx,terms):

		terms = ctx.evalTerms(terms)
		if len(terms) < 1 or len(terms) > 2:
			return "#-1 Function expects one or two arguments."
		sep = " " if (len(terms)) != 3 else terms[1][0]	
		terms[0] = terms[0].split(sep)
		random.shuffle(terms[0])
		return sep.join(terms[0])

	def fn_sign(self,ctx,terms):
		num = ctx.numify(ctx.evalOneTerm(terms))
		return "0" if num==0 else ("1" if num>0 else"-1")

	def fn_sin(self,ctx,terms):
		return str(math.sin(ctx.numify(ctx.evalOneTerm(terms))))

	def fn_sort(self,ctx,terms):
		terms = ctx.evalTerms(terms)
		if len(terms) < 1 or len(terms) > 3:
			return "#-1 Function expects one to three arguments."
		sep = " " if (len(terms)) != 3 else terms[2][0]
		items = terms[0].split(sep)
		
		allnums = True
		for x in items:
			if not ctx.isnum(x):
				allnums = False
		if allnums:
			li = [ctx.numify(x) for x in items]
			li.sort()
			items = [str(x) for x in li]
			return sep.join(items)

		alldbrefs = True
		for x in items:
			if not x[0] == "#":
				alldbrefs = False

		if alldbrefs:
			li = [ctx.numify(x[1:]) for x in items]
			li.sort()
			items = [f"#{x}" for x in li]
			return sep.join(items)

		items.sort()
		return sep.join(items)

	def fn_sortby(self,ctx,terms):

		terms = ctx.evalTerms(terms)
		if len(terms) < 2 or len(terms) > 3:
			return "#-1 Function expects two or three arguments."

		sep = " " if (len(terms)) != 3 else terms[2][0]
		items = terms[1].split(sep)

		if terms[0].find('/') != -1:
			(dbref,attr) = ctx.getObjAttr(terms[0])
		else:
			dbref = ctx.enactor
			attr = terms[0].upper()

		if not mush.db.validDbref(dbref) or attr not in mush.db[dbref]:
			return ""

		rlist = []
		for item in items:
			if (len(rlist) == 0):
				rlist.append(item)
				continue

			inserted = False 
			li = rlist[:]
			for x in rlist:
				e = EvalEngine(mush.db[dbref][attr],ctx.enactor,ctx.obj)
				e.registers[0] = item
				e.registers[1] = x
				if (ctx.numify(e.eval('')) < 0):
					li.insert(rlist.index(x),item)
					inserted = True
					break
			
			if not inserted:
				li.append(item)
			rlist = li[:]
	
		return sep.join(rlist)

	def fn_soudnex(self,ctx,terms):
		return self.fn_notimplemented(ctx)

	def fn_soundlike(self,ctx,terms):
		return self.fn_notimplemented(ctx)

	def fn_soundslike(self,ctx,terms):
		return self.fn_notimplemented(ctx)

	def fn_space(self,ctx,terms):
		return " "*ctx.numify(ctx.evalOneTerm(terms))

	def fn_speakfunc(self,ctx,terms):
		return self.fn_notimplemented(ctx)

	def fn_splice(self,ctx,terms):
		terms = ctx.evalTerms(terms)
		if len(terms) < 3 or len(terms) > 4:
			return "#-1 Function expects three or four arguments."

		sep = " " if (len(terms)) != 4 else terms[3][0]
		terms[0] = terms[0].split(sep)
		terms[1] = terms[1].split(sep)
		if (len(terms[0]) != len(terms[1])):
			return "#-1 lists must be the same length."

		return sep.join([x if x != terms[2] else terms[1][terms[0].index(x)] for x in terms[0]])


	def fn_sqr(self,ctx,terms):
		val = ctx.numify(ctx.evalOneTerm(terms))
		return str(val*val)


	def fn_sqrt(self,ctx,terms):
		val = ctx.numify(ctx.evalOneTerm(terms))
		if (val < 0):
			return "#-1 Number cannot be negative."
		return str(math.sqrt(val)) if not ctx.isInt(val) else str(int(math.sqrt(val)))
	
	def fn_squish(self,ctx,terms):
		terms = ctx.evalTerms(terms)
		if len(terms) < 1 or len(terms) > 2:
			return "#-1 Function expects one or two arguments."

		sep = " " if (len(terms)) != 2 else terms[1][0]
		terms[0] = terms[0].split(sep)
		words = [x for x in terms[0] if x != ""]
		return sep.join(words)
	
	def fn_starttime(self,ctx,terms):
		return time.ctime(mush.startTime)

	def fn_stats(self,ctx,terms):
		return self.fn_lstats(ctx,terms)

	def fn_strcat(self,ctx,terms):
		terms = ctx.evalTerms(terms)
		if len(terms) != 2:
			return "#-1 Function expects two arguments."

		return terms[0]+terms[1]

	def fn_stripansi(self,ctx,terms):
		return self.fn_notimplemented(ctx)
	
	def fn_stripthunks(self,ctx,terms):
		return self.fn_notimplemented(ctx)

	def fn_strlen(self,ctx,terms):
		return str(len(ctx.evalOneTerm(terms)))

	def fn_strmatch(self,ctx,terms):
		terms = ctx.evalTerms(terms)
		if len(terms) != 2:
			return "#-1 Function expects two arguments."

		return "1" if fnmatch.fnmatch(terms[0].lower(),terms[1].lower()) else "0"

	def fn_sub(self,ctx,terms):
		terms = ctx.evalTerms(terms)
		if len(terms) != 2:
			return "#-1 Function expects two arguments."
		return str(ctx.numify(terms[0])-ctx.numify(terms[1]))

	def fn_subj(self,ctx,terms):

		dbref = ctx.dbrefify(ctx.evalOneTerm(terms))
		if not mush.db.validDbref(dbref):
			return "#-1 No Match"

		sex = evalAttribute(ctx,dbref,"SEX").upper()
		rval = "it"

		if (sex=="MALE" or sex == "M" or sex == "MAN"):
			rval = "he"
		elif(sex=="FEMALE" or sex =="F" or sex == "WOMAN" ):
			rval = "she"
		elif(sex == "PLURAL"):
			rval = "they"
		return rval

	def fn_switch(self,ctx,terms):
		return self.fn_notimplemented(ctx)

	
	







#
# The MushFunctions class is simply a container so we can have a safe place to do hasattr/getattr from text strings in the mush.
# 
gMushFunctions = MushFunctions()
