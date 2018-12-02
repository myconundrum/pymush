
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

		self.termsMatch 	= re.compile("[\[\]\(\),]")

	def nextTok(self):
		if self.line != None:
			self.line = self.line[1:]

	def getTerms(self):
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

	def _get_fn_terms(self):

		plevel 	= 1
		blevel 	= 0
		i 		= 1
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


		term = self.line[1:i-1] if i < len(self.line) else self.line[1:]
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
	def stringEval(self,s,stops="",escaping=False):
		return EvalEngine(s,self.enactor,self.obj,self.listElem,self.listPos).eval(stops,escaping)

	def evalTerms(self,terms):
		results = []
		for term in self.splitTerms(terms):
			results.append(self.stringEval(term))

		return results

	def evalOneTerm(self,term):

		return self.stringEval(term)



	def eval(self,stops,escaping=False):
		
		rStr = ""

		# ignore empty lines.
		if (self.line == None):
			return ""
			
		# first part of a line is always in fn evaluation mode.
		rStr += self._eval_fn()

		# Now loop through the rest of the string until we reach our stopchars or a special char.
		specialchars = "\[%#]" if self.listPos != -1 else "\[%]"
		pattern = re.compile(f"[{stops}{specialchars}") if not escaping else re.compile(f"[{stops}]")

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

	def fn_and(self,ctx):

		terms = ctx.getTerms()
		for t in terms:
			if (ctx.boolify(t) == False):
				return "0"
		return "1"

	def fn_alphamax(self,ctx):

		words = ctx.getTerms()
		words.sort(reverse=True)
		return words[0]

	def fn_alphamin(self,ctx):
		words = ctx.getTerms()
		words.sort()
		return words[0]

	def fn_abs(self,ctx,terms):
	
		return str(abs(ctx.numify(ctx.evalOneTerm(terms))))


	def fn_after(self,ctx):
		terms = ctx.getTerms()
		words = terms[0].split(terms[1],1)
		return words[1] if len(words) > 1 else ""
		
	def fn_acos(self,ctx):
		term = ctx.getOneTerm()
		return str(math.acos(ctx.numify(term)))
		
	def fn_andflags(self,ctx):
		return self.fn_notimplemented(ctx)

	def fn_ansi(self,ctx):
		return self.fn_notimplemented(ctx)

	def fn_ansiif(self,ctx):
		return self.fn_notimplemented(ctx)

	def fn_atrlock(self,ctx):
		return self.fn_notimplemented(ctx)

	def fn_beep(self,ctx):
		return self.fn_notimplemented(ctx)

	def fn_can_see(self,ctx):
		return self.fn_notimplemented(ctx)

	def fn_change(self,ctx):
		return self.fn_notimplemented(ctx)

	def fn_clone(self,ctx):
		return self.fn_notimplemented(ctx)

	def fn_cmds(self,ctx):
		return self.fn_notimplemented(ctx)

	def fn_conn(self,ctx):
		return self.fn_notimplemented(ctx)

	def fn_convfirston(self,ctx):
		return self.fn_notimplemented(ctx)

	def fn_controls(self,ctx):
		return self.fn_notimplemented(ctx)

	def fn_convtime(self,ctx):
		return self.fn_notimplemented(ctx)

	def fn_cstats(self,ctx):
		return self.fn_notimplemented(ctx)

	def fn_decrypt(self,ctx):
		return self.fn_notimplemented(ctx)

	def fn_descfun(self,ctx):
		return self.fn_notimplemented(ctx)

	def fn_doing(self,ctx):
		return self.fn_notimplemented(ctx)

	def fn_elock(self,ctx):
		return self.fn_notimplemented(ctx)

	def fn_encrypt(self,ctx):
		return self.fn_notimplemented(ctx)

	def fn_entrances(self,ctx):
		return self.fn_notimplemented(ctx)

	def fn_evalthunks(self,ctx):
		return self.fn_notimplemented(ctx)

	def fn_findable(self,ctx):
		return self.fn_notimplemented(ctx)

	def fn_flags(self,ctx):
		return self.fn_notimplemented(ctx)

	def fn_fold(self,ctx):
		return self.fn_notimplemented(ctx)

	def fn_force(self,ctx):
		return self.fn_notimplemented(ctx)

	def fn_grep(self,ctx):
		return self.fn_notimplemented(ctx)

	def fn_grepi(self,ctx):
		return self.fn_notimplemented(ctx)

	def fn_hasattrp(self,ctx):
		return self.fn_notimplemented(ctx)

	def fn_hasattrpval(self,ctx):
		return self.fn_notimplemented(ctx)

	def fn_haspower(self,ctx):
		return self.fn_notimplemented(ctx)

	def fn_hasthunk(self,ctx):
		return self.fn_notimplemented(ctx)

	def fn_hidden(self,ctx):
		return self.fn_notimplemented(ctx)

	def fn_hilite(self,ctx):
		return self.fn_notimplemented(ctx)

	def fn_htmlescape(self,ctx):
		return self.fn_notimplemented(ctx)

	def fn_htmlok(self,ctx):
		return self.fn_notimplemented(ctx)

	def fn_asin(self,ctx):
		term = ctx.getOneTerm()
		return str(math.asin(ctx.numify(term)))

	def fn_atan(self,ctx):
		term = ctx.getOneTerm()
		return str(math.atan(ctx.numify(term)))

	def fn_notimplemented(self,ctx):
		ctx.getTerms()
		return "#-1 Function Not Implemented"

	def fn_aposs(self,ctx):

		rval = "its"
		sex = evalAttribute(ctx,ctx.dbrefify(ctx.getOneTerm()),"SEX").upper()

		if (sex=="MALE" or sex == "M" or sex == "MAN"):
			rval = "his"
		elif(sex=="FEMALE" or sex =="F" or sex == "WOMAN" ):
			rval = "hers"
		elif(sex == "PLURAL"):
			rval = "theirs"

		return rval

	def fn_art(self,ctx):
		term = ctx.getOneTerm()
		return "an" if term != None and term[0] in "AEIOUaeiou" else "a"
		
	# takes up to ten lists of numbers and averages. 
	# lists are space delimited and there is a comma between each list
	def fn_avg(self,ctx):

		rval = 0
		count = 0
		lists = ctx.getTerms()
		
		for l in lists:
			for term in l.split(' '):
				count += 1
				rval += ctx.numify(term)

		return str(round(rval/count,6))

	def fn_before(self,ctx):
		terms = ctx.getTerms()
		words = terms[0].split(terms[1],1)
		return words[0] if len(words) > 1 else ""

	def fn_capstr(self,ctx):
		cap = ctx.getOneTerm()
		return cap.capitalize() if cap != None else ""
		
	def fn_cat(self,ctx):
		return " ".join(ctx.getTerms())

	def fn_ceil(self,ctx):
		return str(math.ceil(ctx.numify(ctx.getOneTerm())))

	def fn_center(self,ctx):
		terms = ctx.getTerms()
		if (len(terms) < 2 or len(terms) > 3):
			return "#-1 Function expects 2 or 3 arguments."

		width = ctx.numify(terms[1])
		pad = " " if len(terms) < 3 else terms[2]

		return terms[0].center(width,pad)

	def fn_comp(self,ctx):
		terms = ctx.getTerms()
		if (len(terms) != 2):
			return "#-1 Function expects 2 arguments."

		val = 0
		if (terms[0] < terms[1]): 
			val = -1
		elif (terms[0] > terms[1]):
			val = 1

		return str(val)

	def fn_clone(self,ctx):

		dbref = ctx.dbrefify(ctx.getOneTerm())
		o = mush.db[dbref]
		if (o.flags & (ObjectFlags.ROOM | ObjectFlags.PLAYER)):
			mush.msgDbref(enactor,"You can only clone things and exits.")
			return "#-1"
		# BUGBUG This is not implemented yet. Needs to be completed.

	def fn_con(self,ctx):
		dbref = ctx.dbrefify(ctx.getOneTerm())
		val =  -1 if len(mush.db[dbref].contents) == 0 else mush.db[dbref].contents[0]
		return str(val)

	def fn_convsecs(self,ctx):
		return str(time.asctime(time.localtime(ctx.numify(ctx.getOneTerm()))))

	def fn_or(self,ctx):
		for t in ctx.getTerms():
			if (ctx.boolify(t) == True):
				return "1"

		return "0"

	def fn_cos(self,ctx):
		return str(math.cos(ctx.numify(ctx.getOneTerm)))

	def fn_create(self,ctx):

		terms = ctx.getTerms()
		if (len(terms)<1 or len(terms)>2):
			return "#-1 Function expects 1 or 2 arguments."

		dbref = mush.db.newObject(mush.db[ctx.enactor])
		mush.db[dbref]["NAME"] = terms[0]
		mush.msgDbref(ctx.enactor,f"Object named {terms[0]} created with ref #{dbref}.")
		mush.log(2,f"{mush.db[ctx.enactor].name}(#{ctx.enactor}) created object named {terms[0]} (#{dbref}).")
		return str(dbref)
	
	def fn_ctime(self,ctx):
		return time.ctime(mush.db[ctx.dbrefify(ctx.getOneTerm())].creationTime)

	#
	# takes a *string* as argument, and finds the last integer part and subs one from that.
	# so dec(hi3) => hi2, dec(1.2)=>1.1 
	# 
	def fn_dec(self,ctx):

		term = ctx.getOneTerm()
		m = re.search(r'-?\d+$',term)
		if (m == None):
			return "#-1 Argument does not end in integer."

		return term[0:m.start()]+str(ctx.numify(m.group())-1)

	def fn_default(self,ctx):

		terms = ctx.getTerms()
		if len(terms) != 2:
			return "#-1 Function exects two arguments."

		(dbref,attr) = ctx.getObjAttr(terms[0])
		return mush.db[dbref][attr] if attr in mush.db[dbref] else terms[1]

	def fn_delete(self,ctx):
		
		terms = ctx.getTerms()
		if len(terms) != 3:
			return "#-1 Function expects three arguments."

		start 	= ctx.numify(terms[1])
		length 	= ctx.numify(terms[2])

		return terms[0][0:start]+terms[0][start+length:]

	def fn_die(self,ctx):
		
		terms = ctx.getTerms()
		if len(terms) != 2:
			return "#-1 Function expects two arguments."

		return str(sum([random.randint(1,ctx.numify(terms[1])) for x in range(ctx.numify(terms[0]))]))

	def fn_dig(self,ctx):
		
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

	def fn_dist2d(self,ctx):
		
		terms = ctx.getTerms()
		if len(terms) != 4:
			return "#-1 Function expects four arguments."

		x1 = ctx.numify(terms[0])
		y1 = ctx.numify(terms[1])
		x2 = ctx.numify(terms[2])
		y2 = ctx.numify(terms[3])
		return str(round(math.sqrt((x2 - x1)*(x2 - x1) + (y2 - y1) * (y2 - y1)),6))

	def fn_dist3d(self,ctx):
		
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

	def fn_div(self,ctx):
		
		terms = ctx.getTerms()
		if len(terms) != 2:
			return "#-1 Function expects two arguments."
		
		return str(ctx.numify(terms[0])//ctx.numify(terms[1]))

	def fn_e(self,ctx):
		
		terms = ctx.getTerms()
		if len(terms) != 0:
			return "#-1 Function expects zero arguments."
		return "2.718281"

	def fn_edefault(self,ctx):

		terms = ctx.getTerms()
		if len(terms) != 2:
			return "#-1 Function exects two arguments." 

		(dbref,attr) = ctx.getObjAttr(terms[0])
		e = EvalEngine(mush.db[dbref][attr] if attr in mush.db[dbref] else terms[1],ctx.enactor,ctx.obj,ctx.listElem,ctx.listPos)
		return e.eval("")

	def fn_edit(self,ctx):
		
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

	def fn_elem(self,ctx):
		return self.fn_element(ctx)

	def fn_element(self,ctx):
		
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


	def fn_elements(self,ctx):
		
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

	def fn_emit(self,ctx):
		mush.msgLocation(mush.db[ctx.obj].location,ctx.getOneTerm())
		return ""

	def fn_enumerate(self,ctx):
		
		terms = ctx.getTerms()

		sep = ' ' if len(terms) < 2 else terms[1][0]
		connective = 'and' if len(terms) < 3 else terms[2]
		items = terms[0].split(sep)

		if len(items) < 2:
			return terms[0]

		if len(items) == 2:
			return f"{items[0]} {connective} {items[1]}"

		return ", ".join(items[:-1])+", " + connective + " " + items[-1]

	def fn_eq(self,ctx):

		terms = ctx.getTerms()	
		if (len(terms) != 2):
			return "#-1 Function expects two arguments"

		if (not ctx.isnum(terms[0] or not ctx.isnum(terms[1]))):
			return "#-1 Arguments must be numbers"

		return "1" if ctx.numify(terms[0]) == ctx.numify(terms[1]) else "0"


	def escaper(self,match):
		return f"\\{match.group(0)}"

	def fn_escape(self,ctx):
		# call eval in special "escaping" mode
		term = ctx.eval(")",True)
		ctx.nextTok()
		return "\\" + re.sub(r"[%;{}\[\]]",self.escaper,term)

	def fn_eval(self,ctx):
		
		terms = ctx.getTerms()	
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
	def fn_exit(self,ctx):

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


	def fn_exp(self,ctx):
		return str(round(math.exp(ctx.numify(ctx.getOneTerm())),6))

	def fn_extract(self,ctx):
		
		terms = ctx.getTerms()
		if (len(terms) < 3 or len(terms) > 4):
			return "#-1 Function expects 3 or 4 arguments"

		sep = ' ' if len(terms) < 4 else terms[3][0]
		start = ctx.numify(terms[1]) - 1
		length = ctx.numify(terms[2]) 
		items = terms[0].split(sep)

		return sep.join(items[start:start+length])

	def fn_fdiv(self,ctx):
		terms = ctx.getTerms()
		if len(terms) != 2:
			return "#-1 Function expects two arguments."

		return str(round(ctx.numify(terms[0])/ctx.numify(terms[1]),6))

	def fn_filter(self,ctx):

		terms = ctx.getTerms()
		if (len(terms)<2 or len(terms) > 3):
			return "#-1 Function expects two or three arguments."

		(dbref,attr) = ctx.getObjAttr(terms[0])
		#
		# BUGBUG Not complete.
		#
		return ""

	def fn_first(self,ctx):

		terms = ctx.getTerms()
		if (len(terms) > 2):
			return "#-1 Function expects one or two arguments."

		# and empty set of arguements returns empty.
		if (len(terms) == 0):
			return ""

		sep = ' ' if len(terms) != 2 else terms[1][0]
		return terms[0].split(sep)[0]


	def fn_flip(self,ctx):
		return ctx.getOneTerm()[::-1]

	def fn_floor(self,ctx):
		return str(math.floor(ctx.numify(ctx.getOneTerm())))

	def fn_foreach(self,ctx):

		terms = ctx.getTerms()
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

	def fn_freeattr(self,ctx):
		
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

	def fn_fullname(self,ctx):
		return mush.db[ctx.dbrefify(ctx.getOneTerm())]["NAME"]

	def fn_functions(self,ctx):
		ctx.getOneTerm()
		return ' '.join(fnList.keys())

	def fn_get(self,ctx):

		term  = ctx.getOneTerm()
		if (term == ""):
			return "#-1 Function expects one argument."

		(dbref,attr) = ctx.getObjAttr(term)

		return "" if attr not in mush.db[dbref] else mush.db[dbref][attr]

	def fn_get_eval(self,ctx):
		
		term = ctx.getOneTerm()
		if (term == ""):
			return "#-1 Function expects two arguments."
		(dbref,attr) = ctx.getObjAttr(term)
		
		if attr in mush.db[dbref]:
			e = EvalEngine(mush.db[dbref][attr],ctx.enactor,ctx.obj,ctx.listElem,ctx.listPos)
			return e.eval("")
			
		return ""

	def fn_grab(self,ctx):
		
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

	def fn_graball(self,ctx):

		terms = ctx.getTerms()
		if (len(terms) < 2 or len(terms) > 3):
			return "#-1 Function expects two or three arguments."
		
		sep = terms[2][0] if len(terms) == 3 else ' '
		elements = terms[0].split(sep)
		pattern = terms[1]
		
		return  sep.join([x for x in elements if fnmatch.fnmatch(x,pattern)])

	def fn_gt(self,ctx):
		
		terms = ctx.getTerms()
		if (len(terms) != 2):
			return "#-1 Function expects two arguments"

		if (not ctx.isnum(terms[0] or not ctx.isnum(terms[1]))):
			return "#-1 Arguments must be numbers"

		return "1" if ctx.numify(terms[0]) > ctx.numify(terms[1]) else "0"

	def fn_gte(self,ctx):

		terms = ctx.getTerms()
		if (len(terms) != 2):
			return "#-1 Function expects two arguments"

		if (not ctx.isnum(terms[0] or not ctx.isnum(terms[1]))):
			return "#-1 Arguments must be numbers"

		return "1" if ctx.numify(terms[0]) >= ctx.numify(terms[1]) else "0"

	def fn_hasattr(self,ctx):

		terms = ctx.getTerms()
		
		if (len(terms) != 2):
			return "#-1 Function expects two arguments"
		dbref = ctx.dbrefify(terms[0])
		return "1" if dbref != None and terms[1].upper() in mush.db[dbref] else "0"

	def fn_hasflag(self,ctx):

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

	def fn_hastype(self,ctx):

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

	def fn_home(self,ctx):

		term = ctx.getOneTerm()
		if (term == ""):
			return "#-1 Function expects one argument."

		return f"#{mush.db[ctx.dbrefify(term)].home}"


	def fn_idle(self,ctx):

		dbref = ctx.dbrefify(ctx.getTerms()[0])
		if not mush.db.validDbref(dbref) or not mush.db[dbref].flags & ObjectFlags.CONNECTED:
			return "-1"
		return int(mush.server.get_client_idle(mush.dbreftoPid[dbref]))

	def fn_idlesecs(self,ctx):
		return self.fn_idle(ctx)

	def fn_if(self,ctx):

		terms = ctx.getTerms()
		if (len(terms) != 2 and len(terms) != 3):
			return "#-1 Function expects two or three arguments"

		if (len(terms) == 2):
			terms.append("")

		return terms[1] if ctx.boolify(terms[0]) else terms[2]

	def fn_ifelse(self,ctx):
		return self.fn_if(ctx)

	def fn_inc(self,ctx):

		term = ctx.getOneTerm()
		m = re.search(r'-?\d+$',term)
		if (m == None):
			return "#-1 Argument does not end in integer."

		return term[0:m.start()]+str(ctx.numify(m.group())+1)


#
# Awful hack here. The parser doesn't like empty arguments like (<term>, ,<term>)
# the ,<space>, above will not be returned as a term even though its valid ehre.
# Probably this should be fixed.
#
	def fn_index(self,ctx):

		terms = ctx.getTerms()
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


	def fn_inlist(self,ctx):

		terms = ctx.getTerms()

		# this is for pennmush compat. 
		if (len(terms) == 0):
			return "1"
		if (len(terms) == 1):
			return "0"

		sep = " " if len(terms) < 3 else terms[2]
		return "1" if terms[1] in terms[0].split(sep) else "0"


	def fn_insert(self,ctx):

		terms = ctx.getTerms()
		if (len(terms) != 3 and len(terms) !=4):
			return "#-1 Function expects three or four arguments."

		sep = " " if len(terms) == 3 else terms[3][0]
		index = ctx.numify(terms[1]) -1
		items = terms[0].split(sep)

		if (index > -1 and index < len(items)):
			items.insert(index,terms[2])

		return sep.join(items)

	def fn_invoke(self,ctx):
		return self.fn_notimplemented()

	def fn_isdaylight(self,ctx):
		return self.fn_notimplemented()

	def fn_isdbref(self,ctx):
		term = ctx.getOneTerm()
		if term[0] != '#':
			return "0"
		if not ctx.isnum(term[1:]):
			return "0"
		return "1" if mush.db.validDbref(ctx.numify(term[1:])) else "0"

	def fn_isnum(self,ctx):
		return "1" if ctx.isInt(ctx.getOneTerm()) else "0"


	def fn_isword(self,ctx):
		return "1" if ctx.getOneTerm().isalpha() else "0"

	def fn_items(self,ctx):
		return self.fn_words(ctx)

	def fn_words(self,ctx):
		terms = ctx.getTerms()
		if len(terms) == 0:
			return "0"
		if len(terms) > 2:
			return "#-1 Function expects two or three arguments."

		sep = " " if len(terms) == 1 else terms[1][0]
		return str(len(terms[0].split(sep)))


	def fn_iter(self,ctx,terms):
		
		print(terms)
		print(ctx.splitTerms(terms))
		#terms = ctx.termify(terms)
		if (len(terms) < 2 or len(terms) > 4):
			return "#-1 Function expects between two and four arguments."

		sep = " " if len(terms) < 3 else terms[2][0]
		osep = " " if len(terms) < 4 else terms[3][0]
		items = terms[0].split(sep)

		rlist = []
		n = 1
		for item in items: 
			e = EvalEngine(terms[1],ctx.enactor,ctx.obj,item,n)
			print(terms[1])
			rlist.append(e.eval(''))
			n+=1

		return osep.join(rlist)




#
# The MushFunctions class is simply a container so we can have a safe place to do hasattr/getattr from text strings in the mush.
# 
gMushFunctions = MushFunctions()

def testParse():

	tests= {
		"     abc def ghi":"abc def ghi",
		"add(1,2,3)dog house":"6dog house",
		"abs(add(-1,-5,-6))candy":"12candy",
		"add(-1,-5,-6))candy":"-12)candy",		
		"dog was here[add(1,2)]":"dog was here3",
		"[dog was here[add(1,2)]]":"dog was here3",
		"add(dog,1,2,3,4":"10",
		"add(1,2":"3",
		}
	otests={	"after(as the world turns,world)":" turns",
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
		"if(dog,true,false)":"true",
		"if(#-12,true,false)":"false",
		"if(-12,true,false)":"true",
		"inc(dog2)":"dog3",
		"inc(dog-1":"dog0",
		"index(a|b|c|d,|,2,2)":"b|c",
		"index(a dog in the house went bark, ,2,4)":"dog in the house",
		"index(a dog, ,4,5)":"",
		"inlist()":"1",
		"inlist(dog)":"0",
		"inlist(a dog was here,not":"0",
		"[inlist(a|dog|was,was,|)]":"1",
		"[insert(This is a string,4,test)]":"This is a test string",
		"[insert(one|three|four|five,2,two,|)]":"one|two|three|four|five",
		"isdbref(#-12)":"0",
		"isdbref(#1)":"1",
		"isnum(dog)":"0",
		"isnum(1)":"1",
		"isnum(-1)":"1",
		"isword(dog)":"1",
		"isword(dog3)":"0",
		"words(a b c d e f)":"6",
		"words(a|b|c|d|e|f,|)":"6",
		"words()":"0",
		#"iter(a b c d e f,##)":"a b c d e f",
		#"iter(a b c d e f,###@)":"a1 b2 c3 d4 e5 f6",
		"[iter(1|2|3|4|5,add2(##,add2(##,1)),|)]Hello World!":"3 5 7 9 11Hello World!",

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
			mush.log(1,f"Test passed! \'{s}\'\n\texpected: \'{tests[s]}\'\n\tactual: \'{val}\'")
