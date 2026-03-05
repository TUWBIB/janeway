from __future__ import annotations

from typing import List, Tuple, Dict
import re
import datetime
import logging

class RequestData():
    def __init__(self) -> None:
        self.ts = None
        self.requestid = None
        self.mmmsid = None
        self.title = None
        self.request_type_desc = None
        self.request_active = None
        self.request_date = None
        self.request_status_latest_step = None
        self.last_loan_date = None
        self.itemid = None
        self.owning_library_code = None
        self.owning_location_code = None
        self.pickup_location = None
        self.request_completion_date = None
        self.current_process = None
        self.cancellation_reason = None
        self.ac = None
        self.volume_issue = None

    def key(self) -> str:
        key = ''
        key += str(self.requestid) + ';'
        key += str(self.request_active) + ';'
        key += str(self.mmsid) + ';'
        key += str(self.volume_issue) + ';'
        key += str(self.request_status_latest_step) + ';'
        return key

class CoverageResultAggregated:
    length_contained: int
    length_containing: int
    s_containing: set[int]
    s_contained: set[int]
    percentage: float

    def __init__(self,s_contained:set[int],s_containing:set[int]):
        self.s_containing = s_containing
        self.length_containing = len(s_containing)
        self.s_contained = s_contained
        self.length_contained = len(s_contained)

        x = self.s_contained.intersection(self.s_containing)
        l = len(x)
        if self.length_containing == 0:
            self.percentage = 0.0
        else:
            self.percentage = l / self.length_contained

        if self.percentage > 1.0:
            self.percentage = 1.0

    def __repr__(self) -> str:
        return self.__str__()

    def __str__(self) -> str:
        s = str(self.length_contained)
        s += ' // '
        s += str(self.length_containing)
        s += ' // '
        s += "{:.2f}".format(round(self.percentage * 100,2)) + '%'

        return s
    
    def percentageStr(self) -> str:
        return "{:.2f}".format(round(self.percentage * 100,2)) + '%'        

    @classmethod
    def mergeYears(cls,l:List[int]) -> List[Tuple[int,int]]:

        def merge(a:Tuple[int,int],b:Tuple[int,int]) -> Tuple[int,int]:
            merged = None
#            print ("a",a)
#            print ("b",b)

            if a[0] <= b[0] and a[1] >= b[1]:
#                print ("cp1")
                merged = a
            elif b[0] <= a[0] and b[1] >= a[1]:
#                print ("cp2")
                merged = b
            elif (a[1] + 1) == b[0]:
#                print ("cp3")
                merged = (a[0],b[1])
            
            return merged

        l.sort()
        l = [(x,x) for x in l]
        i:int = 0
        while len(l)>=2 and i<len(l)-1:
            merged = merge(l[i],l[i+1])
#            print ("merged",merged)
            if merged:
                l[i] = merged
                del l[i+1]
            else:
                i += 1

        return l

    def containingYearsStr(self) -> str:
#        a = min(self.s_containing) if len(self.s_containing) > 0 else None
#        b = max(self.s_containing) if len(self.s_containing) > 0 else None
#        s = (str(a) + ' - ' +str(b)) if a else ''
#        return s

        l = sorted(self.s_containing)
        l = CoverageResultAggregated.mergeYears(l)

        m = []
        for x in l:
            if x[0] < x[1]:
                m.append(str(x[0]) + '-' +  str(x[1]))
            else:
                m.append(str(x[0]))
        s = '; '.join(m)

        return s


    def containedYearsStr(self) -> str:
#        a = min(self.s_contained)
#        b = max(self.s_contained)
#        s = str(a) + ' - ' +str(b)
#        return s

        l = self.s_contained.intersection(self.s_containing)
        l = sorted(l)
        l = CoverageResultAggregated.mergeYears(l)

        m = []
        for x in l:
            if x[0] < x[1]:
                m.append(str(x[0]) + '-' +  str(x[1]))
            else:
                m.append(str(x[0]))
        s = '; '.join(m)

        return s

class CoverageResult:
    val: int
    percentage: float
    coverage: Coverage

    def __init__(self,val:int, coverage:Coverage, percentage: float):
        self.val = val
        self.coverage = coverage
        self.percentage = percentage

    def __repr__(self) -> str:
        return RESULT_DESCRIPTION[self.val]
    
    def __str__(self) -> str:
        s = RESULT_DESCRIPTION[self.val]
        s += ': '

        if self.val == RESULT_FULLY_COVERED or self.val == RESULT_PARTIALLY_COVERED:
            s += self.coverage.getCoverageString()
        else:
            s += '---'

        s += ' // '
        if self.coverage:
            s += str(self.coverage.getLength())
        else:
            s += '---'

        s += ' // ' +  "{:.2f}".format(round(self.percentage * 100,2)) + '%'

        return s
    
    def percentageStr(self) -> str:
        return "{:.2f}".format(round(self.percentage * 100,2)) + '%'        


RESULT_FULLY_COVERED = 0b10
RESULT_PARTIALLY_COVERED = 0b01
RESULT_NOT_COVERED = 0b00
RESULT_INVALID = -1

RESULT_DESCRIPTION = {
    RESULT_FULLY_COVERED: 'fully covered',
    RESULT_PARTIALLY_COVERED: 'partially covered',
    RESULT_NOT_COVERED: 'not covered',
    RESULT_INVALID: 'invalid'
}

class CoveragePart:
    coverage_type: int
    year: str
    volume: str
    issue: str
    moving_wall: str
    params_original: List[str | None]

    COVERAGE_TYPE_START = 1
    COVERAGE_TYPE_END = 2

    def __init__(self, coverage_type:int, / , year:str = None,volume:str = None,issue:str = None, moving_wall:str = None):
        self.params_original = []
        self.params_original.append(str(year) if year else '-')
        self.params_original.append(str(volume) if volume else '-')
        self.params_original.append(str(issue) if issue else '-')
        self.params_original.append(str(moving_wall) if moving_wall else '-')


        if coverage_type == CoveragePart.COVERAGE_TYPE_END and moving_wall and year:
            raise ValueError("both end year and moving wall given: *{}*, *{}*".format(year,moving_wall))

        self.coverage_type = coverage_type
        self.year = None if not year else str(year)
        self.volume = None if not volume else str(volume)
        self.issue = None if not issue else str(issue)
        self.moving_wall = None if not moving_wall else str(moving_wall)

        if self.moving_wall:
            if match := re.search('^([-+])(\d+)([YM])$',self.moving_wall):
                mw_sign,mw_val,mw_unit = match.groups()
            else:
                raise ValueError("moving wall parameter invalid: *{}*".format(self.moving_wall))

            mw_val = int(mw_val)
            if mw_unit == 'M':
                # only calc in years
                mw_val = mw_val / 12

            if not self.year and mw_sign=='-':
                if self.coverage_type == CoveragePart.COVERAGE_TYPE_END:
                    year_current = int(datetime.datetime.now().strftime('%Y'))
                    self.year = str(year_current - int(mw_val))
                # fake start year
                if self.coverage_type == CoveragePart.COVERAGE_TYPE_START:
                    self.year = str(1000)

            if not self.year and mw_sign=='+':
                if self.coverage_type == CoveragePart.COVERAGE_TYPE_START:
                    year_current = int(datetime.datetime.now().strftime('%Y'))
                    self.year = str(year_current - int(mw_val) + 1)

                if self.coverage_type == CoveragePart.COVERAGE_TYPE_END:
                    year_current = int(datetime.datetime.now().strftime('%Y'))
                    self.year = str(year_current)

        if self.coverage_type== CoveragePart.COVERAGE_TYPE_END and not self.year:
            year_current = int(datetime.datetime.now().strftime('%Y'))
            self.year = str(year_current)


        if not self.year: 
            raise ValueError(("no year given or not calculated via moving wall parameter"))

        if self.year and len(self.year) != 4:
            raise ValueError("length of year invalid")
            
        self.volume = self.volume.rjust(5,'0') if self.volume else self.volume
        self.issue = self.issue.rjust(5,'0') if self.issue else self.issue

    def getCoverageString(self) -> str:
        s = self.year if self.year else '?'
        s += '-'
        s += self.volume if self.volume else '?'
        s += '-'
        s += self.issue if self.issue else '?'
        return s

    def __str__(self) -> str:
        return self.getCoverageString()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, CoveragePart):
            return NotImplemented        

        eq: bool = True
        eq = eq and (self.year == other.year)
        eq = eq and (self.volume == other.volume)
        eq = eq and (self.issue == other.issue)

        return eq

    def __lt__(self, other:object) -> bool:
        if not isinstance(other, CoveragePart):
            return NotImplemented      

        if self.year and other.year and self.year < other.year: return True
        if self.year and other.year and self.year > other.year: return False
        if self.year and not other.year and other.coverage_type == CoveragePart.COVERAGE_TYPE_END: return True
        if self.volume and other.volume and self.volume < other.volume: return True
        if self.volume and other.volume and self.volume > other.volume: return False
        if self.issue and other.issue and self.issue < other.issue: return True

        return False

    def __le__(self, other:object) -> bool:
        if not isinstance(other, CoveragePart):
            return NotImplemented        

        return self == other or self < other

    def __gt__(self, other:object) -> bool:
        if not isinstance(other, CoveragePart):
            return NotImplemented        

        return not self <= other
    
    def __ge__(self, other:object) -> bool:
        if not isinstance(other, CoveragePart):
            return NotImplemented        

        return self == other or self > other

    def predecesDirectly(self, other:CoveragePart) -> bool:
        if self.coverage_type != CoveragePart.COVERAGE_TYPE_END or other.coverage_type!=CoveragePart.COVERAGE_TYPE_START:
            return False

        if (self.issue and other.issue and int(self.issue) + 1  == int(other.issue)) or \
            (self.volume and other.volume and int(self.volume) + 1  == int(other.volume)) or \
            (self.year and other.year and int(self.year) + 1  == int(other.year)):
            return True
        else:
            return False

class Coverage:
    id: str
    start: CoveragePart
    end: CoveragePart
    errs: List[str]
    coverageresult: CoverageResult
    type: int
    coverage_detail_start: int
    coverage_detail_end: int
    moving_wall: str

    # error
    COVERAGE_DETAIL_ERROR: int = -1
    # nothing given
    COVERAGE_DETAIL_UNDEFINED: int = 0
    # only year
    COVERAGE_DETAIL_YEAR: int = 1
    # year and yolume
    COVERAGE_DETAIL_VOLUME: int = 2
    # year and volume and issue
    COVERAGE_DETAIL_ISSUE: int = 3

    def __init__(self,id:str,/,year_start:str = None,volume_start:str = None,issue_start:str = None,
                 year_end:str = None,volume_end:str = None, issue_end:str = None,moving_wall:str = None):

        self.errs = []
        self.id = str(id)
        self.start = self.end = None
        self.coverage_detail_start = self.coverage_detail_end = Coverage.COVERAGE_DETAIL_ERROR

        try:
            self.start = CoveragePart(
                        CoveragePart.COVERAGE_TYPE_START,
                        year=year_start,
                        volume=volume_start,
                        issue=issue_start,
                        moving_wall=moving_wall
                        )
            
            self.end = CoveragePart(
                        CoveragePart.COVERAGE_TYPE_END,
                        year=year_end,
                        volume=volume_end,
                        issue=issue_end,
                        moving_wall=moving_wall,
                        )
        except ValueError as e:
            self.errs.append(str(e))
            raise e
        
        if not self.errs:
            if self.start:
                if self.start.year is not None and self.start.volume is not None and self.start.issue is not None:
                    self.coverage_detail_start = Coverage.COVERAGE_DETAIL_ISSUE
                elif self.start.year is not None and self.start.volume is not None:
                    self.coverage_detail_start = Coverage.COVERAGE_DETAIL_VOLUME
                elif self.start.year is not None:
                    self.coverage_detail_start = Coverage.COVERAGE_DETAIL_YEAR
                elif self.start.year is None and self.start.volume is None and self.start.issue is None:
                    self.coverage_detail_start = Coverage.COVERAGE_DETAIL_UNDEFINED
                else:
                    self.errs.append("invalid start type")

        if not self.errs:
            if self.end:
                if self.end.year is not None and self.end.volume and self.end.issue is not None:
                    self.coverage_detail_end = Coverage.COVERAGE_DETAIL_ISSUE
                elif self.end.year is not None and self.end.volume is not None:
                    self.coverage_detail_end = Coverage.COVERAGE_DETAIL_VOLUME
                elif self.end.year is not None:
                    self.coverage_detail_end = Coverage.COVERAGE_DETAIL_YEAR
                elif self.end.year is None and self.end.volume is None and self.end.issue is None:
                    self.coverage_detail_end = Coverage.COVERAGE_DETAIL_UNDEFINED
                else:
                    self.errs.append("invalid end type")

        if self.errs:
            raise ValueError("something wrong with coverage params")

        self.type = min(self.coverage_detail_start,self.coverage_detail_end)
        self.coverageresult = None

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return self.getCoverageString()

    def __lt__(self,other:Coverage):
        type = min(self.coverage_detail_start,other.coverage_detail_start)

        if type == Coverage.COVERAGE_DETAIL_ISSUE:
            if self.start.year < other.start.year:
                return True
            elif self.start.year == other.start.year and self.start.volume < other.start.volume:
                return True
            elif self.start.year == other.start.year and self.start.volume == other.start.volume and self.start.issue < other.start.issue:
                return True
            else:
                return False
        elif type == Coverage.COVERAGE_DETAIL_VOLUME:
            if self.start.year < other.start.year:
                return True
            elif self.start.year == other.start.year and self.start.volume < other.start.volume:
                return True
            else:
                return False
        elif type == Coverage.COVERAGE_DETAIL_YEAR:
            if self.start.year < other.start.year:
                return True
            else:
                return False
        elif type == Coverage.COVERAGE_DETAIL_UNDEFINED:
            if self.start.year and not other.start.year:
                return True
            else:
                return False

    def getCoverageString(self) -> str:
        return self.getCoverageStringStart() + " - " + self.getCoverageStringEnd()

    def getCoverageStringStart(self) -> str:
        if self.coverage_detail_start == self.COVERAGE_DETAIL_ISSUE:
            return self.start.year + "-" + self.start.volume + "-" +self.start.issue
        elif self.coverage_detail_start == self.COVERAGE_DETAIL_VOLUME:
            return self.start.year + "-" + self.start.volume
        elif self.coverage_detail_start == self.COVERAGE_DETAIL_YEAR:
            return self.start.year
        else:
            return '???'

    def getCoverageStringEnd(self) -> str:
        if self.coverage_detail_end == self.COVERAGE_DETAIL_ISSUE:
            return self.end.year + "-" + self.end.volume + "-" +self.end.issue
        elif self.coverage_detail_end == self.COVERAGE_DETAIL_VOLUME:
            return self.end.year + "-" + self.end.volume
        elif self.coverage_detail_end == self.COVERAGE_DETAIL_YEAR:
            return self.end.year
        else:
            return '???'
    
    def getStartParams(self) -> Tuple[str]:
        return  (self.start.year,self.start.volume,self.start.issue)

    def getEndParams(self) -> Tuple[str]:
        return  (self.end.year,self.end.volume,self.end.issue)
    
    def getLength(self,year_population = None) -> int:
        start_year:int = int(self.start.year) if self.start.year else None
        end_year:int = int(self.end.year) if self.end.year else None

#        if year_population is not None:
#            print ("self",self.start,self.end)
#            print ("end_year",end_year)
#
        if not end_year:
            end_year = int(datetime.datetime.now().strftime('%Y'))

#        if year_population is not None:
#            print ("end_year_x",end_year)

        length = (end_year - start_year) + 1

        if year_population is not None:
            for i in range(start_year,end_year+1):
                year_population[i] = 1

        return length

    # checks if Coverage "self" contains Coverage "other"
    # returns CoverageResult
    # val:
    # - not covered if either self.start > other.end or self.end < other.start
    # - fully coverred if self.start <= other.start and self.end >= other end
    # - partially covered otherwise
    # coverage: 
    # - intersect of self and other
    # percentage: 
    #  - percentage of coverage comparing the computed intersect to other
    def contains(self,other:Coverage) -> CoverageResult:
        result:CoverageResult = None
        cov: Coverage = None
        percentage: float = 0.0
        val:int = 0

        if self.end < other.start:
            val = RESULT_NOT_COVERED
        elif self.start > other.end:
            val = RESULT_NOT_COVERED
        elif self.start <= other.start and self.end >= other.end:
            val = RESULT_FULLY_COVERED
            cov = Coverage(0,
                            year_start=other.start.year,
                            volume_start=other.start.volume,
                            issue_start=other.start.issue,
                            year_end=other.end.year,
                            volume_end=other.end.volume,
                            issue_end=other.end.issue)
            percentage = 1.0
        elif self.start <= other.start and self.end <= other.end:
            val = RESULT_PARTIALLY_COVERED
            cov = Coverage(0,
                            year_start=other.start.year,
                            volume_start=other.start.volume,
                            issue_start=other.start.issue,
                            year_end=self.end.year,
                            volume_end=self.end.volume,
                            issue_end=self.end.issue)
            percentage = cov.getLength() / other.getLength()
        elif self.start >= other.start and self.end >= other.end:
            val = RESULT_PARTIALLY_COVERED
            cov = Coverage(0,
                            year_start=self.start.year,
                            volume_start=self.start.volume,
                            issue_start=self.start.issue,
                            year_end=other.end.year,
                            volume_end=other.end.volume,
                            issue_end=other.end.issue)
            percentage = cov.getLength() / other.getLength()

        elif self.start >= other.start and self.end <= other.end:
            val = RESULT_PARTIALLY_COVERED
            cov = Coverage(0,
                            year_start=self.start.year,
                            volume_start=self.start.volume,
                            issue_start=self.start.issue,
                            year_end=self.end.year,
                            volume_end=self.end.volume,
                            issue_end=self.end.issue)
            percentage = cov.getLength() / other.getLength()
        else:
            print("weird case")
            print("start",self.start,self.end)
            print("other",other.start,other.end)
        
        return CoverageResult(val,cov,percentage)
    
    @classmethod
    def multiContains(self,l_containing:List[Coverage],contained:Coverage) -> int:
        val:int = 0

        if not contained.errs:
            for x in l_containing:
                if not x.errs:
                    val = max(val,x.contains(contained).val)

        return val
    
    @classmethod
    def crossProductContained(self,l_containing:List[Coverage], l_contained:List[Coverage]) -> CoverageResultAggregated:
        result: CoverageResultAggregated = None
        l_containing: List[Coverage] = Coverage.mergeMultiple(l_containing)
#        l_contained: List[Coverage] = Coverage.mergeMultiple(l_contained)
        year_population_containing: Dict[int,int] = {}
        year_population_contained: Dict[int,int] = {}

        for containing in l_containing:
            for contained in l_contained:
                _ = contained.getLength(year_population=year_population_contained)
                _ = containing.getLength(year_population=year_population_containing)

        s_containing = set(year_population_containing.keys())
        s_contained = set(year_population_contained.keys())

        if len(s_contained) > 0 or len(s_containing) > 0:
            result = CoverageResultAggregated(
                s_contained=s_contained,
                s_containing=s_containing)
            return result
        else:
            return None

    @classmethod
    def mergeMultiple(self,l:List[Coverage]) -> List[Coverage]:
        try:
            l = [x for x in l if not x.errs]
            l.sort()
            i:int = 0
            merged:Coverage
            while len(l)>=2 and i<len(l)-1:
                merged = l[i].merge(l[i+1])
                if merged:
                    l[i]=merged
                    del l[i+1]
                else:
                    i += 1
        except Exception as e:
            raise e

        return l
    
    # merges coverages
    def merge(self,other:Coverage) -> Coverage:
        merged: Coverage = None
        try:
            if self.start <= other.start and self.end >= other.end:
                merged = self
            elif other.start <= self.start and other.end >= self.end:
                merged = other
            # needed for annalen der physik, possibly others
            elif self.end < other.start and not self.end.predecesDirectly(other.start):
                pass
            else:
                id = str(self.id) + '+' + str(other.id)          
                # case coverage directly precedes next coverage
                if self.end.predecesDirectly(other.start):
                    merged = Coverage(id,
                        year_start=self.start.year,
                        volume_start=self.start.volume,
                        issue_start=self.start.issue,
                        year_end=other.end.year,
                        volume_end=other.end.volume,
                        issue_end=other.end.issue)
                # 1996-00001 - 2012-00017, 1997-00002 - 
                elif self.start <= other.start and self.end <= other.end:
                    merged = Coverage(id,
                        year_start=self.start.year,
                        volume_start=self.start.volume,
                        issue_start=self.start.issue,
                        year_end=other.end.year,
                        volume_end=other.end.volume,
                        issue_end=other.end.issue)
                    
                # 1995-00125 - , 2013-00338 - 2014-00361
                elif self.start <= other.start and self.end >= other.end:
                    merged = Coverage(id,
                        year_start=self.start.year,
                        volume_start=self.start.volume,
                        issue_start=self.start.issue,
                        year_end=self.end.year,
                        volume_end=self.end.volume,
                        issue_end=self.end.issue)
                # self 1990-00001-? 2007-00018-?
                # other 1990-?-? 2007-?-?
                elif self.start.year and other.start.year and self.start.year == other.start.year and \
                    self.end.year and other.end.year and self.end.year == other.end.year and \
                    self.start.volume and not other.start.volume  and self.end.volume and not other.end.volume:
                    merged = Coverage(id,
                        year_start=self.start.year,
                        volume_start=self.start.volume,
                        issue_start=self.start.issue,
                        year_end=self.end.year,
                        volume_end=self.end.volume,
                        issue_end=self.end.issue)
                else:
                    pass
                    # todo 
                    # other case
                    # self 1992-?-? 2019-?-?
                    # other 1992-00001-? ?-?-?

#                    print ("other case")
#                    print ("self", self.start, self.end)
#                    print ("other", other.start, other.end)

        except Exception as e:
            print (e)
            print('merge error')
            print(self.id + ': ' + str(self))
            print(other.id + ': ' + str(other))
            raise e 

        return merged

class EZB():
    id:str
    p_issn: str
    e_issn: str
    fronturl: str
    trafficlight: str
    subs: List[EZBSub]

    def __init__(self):
        self.id = None
        self.p_issn = None
        self.e_issn = None
        self.fronturl = None
        self.trafficlight = None
        self.subs = []
        self.coverages = []

    def __eq__(self, other) -> bool:
        if isinstance(other, type(self)):
            return self.id == other.id
        return False

    def __hash__(self) -> int:
        return hash(self.id) ^ hash(self.id)
    
    def __repr__(self) -> str:
        return self.__str__()
    
    def __str__(self) -> str:
        return str(self.id) + ';' + self.p_issn + ';' + str(self.trafficlight)
    
    def getSubsForType(self,licence_type:str) -> List[EZBSub]:
         if not licence_type or licence_type == EZB_LICENCE_TYPE_ALL:
            return self.subs
         elif licence_type == EZB_LICENCE_TYPE_BF_SUB:
            return [x for x in self.subs if x.licence_type == EZB_LICENCE_TYPE_BACKFILE or x.licence_type == EZB_LICENCE_TYPE_SUBSCRIPTION]
         else:
            return [x for x in self.subs if x.licence_type == licence_type]

    def getSubsCoveragesForType(self,licence_type:str) -> List[Coverage]:
         if not licence_type or licence_type == EZB_LICENCE_TYPE_ALL:
            return [x.coverage for x in self.subs]
         elif licence_type == EZB_LICENCE_TYPE_BF_SUB:
            return [x.coverage for x in self.subs if x.licence_type == EZB_LICENCE_TYPE_BACKFILE or x.licence_type == EZB_LICENCE_TYPE_SUBSCRIPTION]
         else:
            return [x.coverage for x in self.subs if x.licence_type == licence_type]


EZB_LICENCE_TYPE_BACKFILE = 'bf'
EZB_LICENCE_TYPE_SUBSCRIPTION ='sub'
EZB_LICENCE_TYPE_BF_SUB ='bf+sub'
EZB_LICENCE_TYPE_FREE = 'free'
EZB_LICENCE_TYPE_ALL = 'all'

EZB_LICENCE_TYPES = [ EZB_LICENCE_TYPE_ALL, EZB_LICENCE_TYPE_BF_SUB, EZB_LICENCE_TYPE_BACKFILE, EZB_LICENCE_TYPE_SUBSCRIPTION, EZB_LICENCE_TYPE_FREE ]

class EZBSub():
    coverage: Coverage
    anchor: str
    collection: str
    moving_wall: str
    pricing: str
    licence_type: str
    publisher: str

    def __init__(self):
        self.coverage = None
        self.anchor = None
        self.collection = None
        self.moving_wall = None
        self.pricing = None
        self.licence_type = None
        self.publisher = None

    def __str__(self) -> str:
        return self.__repr__()
    
    def __repr__(self) -> str:
        l: List[str] = []
        l.append(self.anchor if self.anchor else '---')
        l.append(self.collection if self.collection else '---')
        l.append(self.moving_wall if self.moving_wall else '---')
        l.append('[' + self.licence_type + ']' if self.licence_type else  '[---]')
        l.append(str(self.coverage))
        l.append(str(self.publisher))
        return '; '.join(l)

    def setType(self):
        if self.pricing and self.pricing == 'kostenpflichtig':
            if self.anchor and ('_bf' in self.anchor or '_ar' in self.anchor):
                self.licence_type = EZB_LICENCE_TYPE_BACKFILE
            else:
                self.licence_type = EZB_LICENCE_TYPE_SUBSCRIPTION
        else:
            self.licence_type = EZB_LICENCE_TYPE_FREE

class HolEZBComparisonResult:
    hol_coverage: Coverage
    ezb_coverage: Coverage
    comparison_type: int
    comparison_result: CoverageResult

    def __init__(self,hol_coverage:Coverage, ezb_coverage:Coverage, comparison_type:int, comparison_result:CoverageResult):
        self.hol_coverage = hol_coverage
        self.ezb_coverage = ezb_coverage
        self.comparison_type = comparison_type
        self.comparison_result = comparison_result

#if __name__ == '__main__':
#    s_contained = set([1,2,4,7])
#    s_containing = set([1,2,3,8])
#
#    result = CoverageResultAggregated(s_contained=s_contained,s_containing=s_containing)
#
#    print (result.containedYearsStr())
#    print (result.containingYearsStr())