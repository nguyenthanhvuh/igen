import abc 
from time import time
import os.path
import random
from collections import OrderedDict

import z3
import z3util
from vu_common import HDict

import vu_common as CM
import config_common as CC
from config_common import Configs_d #need this to read in existing exp results

logger = CM.VLog('config')
logger.level = CM.VLog.DEBUG
CM.VLog.PRINT_TIME = True
CM.__vdebug__ = True  #IMPORTANT: TURN OFF WHEN DO REAL RUN!!


allows_known_errors = False
analyze_outps = False

#Data Structures
class Dom(CC.Dom):
    """
    >>> dom = Dom([('x',frozenset(['1','2'])),\
    ('y',frozenset(['1'])),\
    ('z',frozenset(['0','1','2'])),\
    ('w',frozenset(['a','b','c']))\
    ])
    >>> assert dom.siz == len(dom.gen_configs_full()) == 18
    >>> random.seed(0)
    >>> configs = dom.gen_configs_tcover1()
    >>> print "\\n".join(map(str,configs))
    x=2 y=1 z=0 w=a
    x=1 y=1 z=2 w=c
    x=1 y=1 z=1 w=b
    
    >>> random.seed(0)
    >>> configs = dom.gen_configs_rand_smt(5)
    >>> print "\\n".join(map(str,configs))
    x=2 y=1 z=0 w=a
    x=1 y=1 z=0 w=b
    x=2 y=1 z=1 w=a
    x=2 y=1 z=2 w=a
    x=1 y=1 z=0 w=a

    >>> configs = dom.gen_configs_rand_smt(dom.siz)
    >>> assert len(configs) == dom.siz
    
    """
    def gen_configs_tcover1(self):
        """
        Return a set of tcover array of stren 1
        """
        dom_used = dict((k,set(self[k])) for k in self)

        def mk():
            config = []
            for k in self:
                if k in dom_used:
                    v = random.choice(list(dom_used[k]))
                    dom_used[k].remove(v)
                    if not dom_used[k]:
                        dom_used.pop(k)
                else:
                    v = random.choice(list(self[k]))

                config.append((k,v))
            return Config(config)

        configs = []
        while dom_used: configs.append(mk())
        return configs

    """
    Create configs using an SMT solver
    """
    
    def config_of_model(self,model):
        """
        Ret a config from a model
        """
        if CM.__vdebug__:
            assert isinstance(model,dict),model

        _f = lambda k: (model[k] if k in model
                        else random.choice(list(self[k])))
        config = Config((k,_f(k)) for k in self)
        return config
    
    def gen_configs_expr(self,expr,k):
        if CM.__vdebug__:
            assert z3.is_expr(expr),expr
            assert k>0,k

        def _f(m):
            m = dict((str(v),str(m[v])) for v in m)
            return None if not m else self.config_of_model(m)
        
        models = z3util.get_models(expr,k)
        assert models is not None, models  #z3 cannot solve this
        if not models:  #not satisfy
            return []
        else:
            assert len(models)>=1,models            
            configs = [_f(m) for m in models]
            return configs
        
    def gen_configs_exprs(self,yexprs,nexprs,k):
        """
        Return a config satisfying core and not already in existing_configs

        >>> dom = Dom([('a', frozenset(['1', '0'])), \
        ('b', frozenset(['1', '0'])), ('c', frozenset(['1', '0', '2']))])
        >>> z3db = dom.z3db

        >>> c1 = Config([('a', '0'), ('b', '0'), ('c', '0')])
        >>> c2 = Config([('a', '0'), ('b', '0'), ('c', '1')])
        >>> c3 = Config([('a', '0'), ('b', '0'), ('c', '2')])

        >>> c4 = Config([('a', '0'), ('b', '1'), ('c', '0')])
        >>> c5 = Config([('a', '0'), ('b', '1'), ('c', '1')])
        >>> c6 = Config([('a', '0'), ('b', '1'), ('c', '2')])

        >>> c7 = Config([('a', '1'), ('b', '0'), ('c', '0')])
        >>> c8 = Config([('a', '1'), ('b', '0'), ('c', '1')])
        >>> c9 = Config([('a', '1'), ('b', '0'), ('c', '2')])

        >>> c10 = Config([('a', '1'), ('b', '1'), ('c', '0')])
        >>> c11 = Config([('a', '1'), ('b', '1'), ('c', '1')])
        >>> c12 = Config([('a', '1'), ('b', '1'), ('c', '2')])

        >>> configs = [c1,c2,c3,c4,c5,c6,c7,c8,c9,c10,c11]
        >>> nexpr = z3util.myOr([c.z3expr(z3db) for c in configs])
        >>> assert dom.gen_configs_exprs([None],[nexpr],k=1)[0] == c12

        >>> core = Core([('a',frozenset(['1']))])
        >>> core_expr = core.z3expr(z3db,z3util.myAnd)
        >>> assert dom.gen_configs_exprs([None],[nexpr],k=1)[0] == c12

        >>> core = Core([('a',frozenset(['0']))])
        >>> core_expr = core.z3expr(z3db,z3util.myAnd)
        >>> assert not dom.gen_configs_exprs([core_expr],[nexpr],k=1)

        >>> core = Core([('c',frozenset(['0','1']))])
        >>> core_expr = core.z3expr(z3db,z3util.myAnd)
        >>> assert not dom.gen_configs_exprs([core_expr],[nexpr],k=1)

        >>> core = Core([('c',frozenset(['0','2']))])
        >>> core_expr = core.z3expr(z3db,z3util.myAnd)
        >>> config = dom.gen_configs_exprs([core_expr],[nexpr],k=1)[0]
        >>> print config
        a=1 b=1 c=2

        """
        if CM.__vdebug__:
            assert all(e is None or z3.is_expr(e)
                       for e in yexprs),exprs
            assert all(e is None or z3.is_expr(e)
                       for e in nexprs),exprs
            assert k > 0, k

        yexprs = [e for e in yexprs if e]
        nexprs = [z3.Not(e) for e in nexprs if e]
        exprs = yexprs + nexprs
        assert exprs, 'empty exprs'
        expr = exprs[0] if len(exprs)==1 else z3util.myAnd(exprs)
        return self.gen_configs_expr(expr,k)
        
    def gen_configs_cex(self,sel_core,existing_configs,z3db):
        """
        sel_core = (c_core,s_core)
        create counterexample configs by changing settings in c_core,
        but these configs must satisfy s_core
        x=0,y=1  =>  [x=0,y=0,z=rand;x=0,y=2,z=rand;x=1,y=1;z=rand]
        """
        
        if CM.__vdebug__:
            assert isinstance(sel_core,SCore),sel_core 
        
        configs = []            
        c_core,s_core = sel_core

        #keep
        changes = []        
        if sel_core.keep and (len(self) - len(c_core)):
            changes.append(c_core)

        #change
        _new = lambda : Core((k,c_core[k]) for k in c_core)
        for k in c_core:
            vs = self[k] - c_core[k]
            for v in vs:
                new_core = _new()
                new_core[k] = frozenset([v])
                if s_core:
                    for sk,sv in s_core.iteritems():
                        assert sk not in new_core, sk
                        new_core[sk] = sv
                changes.append(new_core)

        e_configs = [c.z3expr(z3db) for c in existing_configs]
        for changed_core in changes:
            yexpr = changed_core.z3expr(z3db,z3util.myAnd)
            nexpr = z3util.myOr(e_configs)
            configs_ = self.gen_configs_exprs([yexpr],[nexpr],k=1)
            if not configs_:
                continue
            config=configs_[0]
            if CM.__vdebug__:
                assert config.c_implies(changed_core)
                assert config not in existing_configs, \
                    ("ERR: gen existing config {}".format(config))
                     
            configs.append(config)
            e_configs.append(config.z3expr(z3db))

        return configs

    def gen_configs_rand_smt(self,rand_n):
        """
        Create rand_n configs
        """
        if CM.__vdebug__:
            assert 0 < rand_n <= self.siz, (rand_n,self.siz)
            
        z3db = self.z3db
        configs = self.gen_configs_rand(1,config_cls=Config)
        assert len(configs) == 1, configs
        config = configs[0]
        e_configs = []

        for _ in range(rand_n-1):
            e_configs.append(config.z3expr(z3db))
            nexpr = z3util.myOr(e_configs)
            configs_ = self.gen_configs_exprs([],[nexpr],1)
            assert len(configs_) == 1, configs_
            config = configs_[0]            
            configs.append(config)
            
        return configs    

class Config(CC.Config):
    """
    >>> c = Config([('a', '1'), ('b', '0'), ('c', '1')])
    >>> print c
    a=1 b=0 c=1

    >>> assert c.c_implies(Core()) and c.d_implies(Core())
    
    >>> core1 = Core([('a', frozenset(['0','1'])), ('b', frozenset(['0','1']))])    
    >>> assert c.c_implies(core1)
    >>> assert c.d_implies(core1)

    >>> core2 = Core([('a', frozenset(['0','1'])), ('x', frozenset(['0','1']))])    
    >>> assert not c.c_implies(core2)
    >>> assert c.d_implies(core2)

    >>> dom = Dom([('a',frozenset(['1','2'])),\
    ('b',frozenset(['0','1'])),\
    ('c',frozenset(['0','1','2']))])
    >>> c.z3expr(dom.z3db)
    And(a == 1, b == 0, c == 1)
    """

    def c_implies(self,core):
        """
        self => conj core
        x=0&y=1 => x=0,y=1
        not(x=0&z=1 => x=0,y=1)
        """
        if CM.__vdebug__:
            assert isinstance(core,Core),(core)

        return (not core or
                all(k in self and self[k] in core[k] for k in core))

    def d_implies(self,core):
        """
        self => disj core
        """
        if CM.__vdebug__:
            assert isinstance(core,Core),core

        return (not core or
                any(k in self and self[k] in core[k] for k in core))

class Core(HDict):
    """
    >>> print Core()
    true

    >>> c = Core([('x',frozenset(['2'])),('y',frozenset(['1'])),('z',frozenset(['0','1']))])
    >>> print c
    x=2 y=1 z=0,1

    >>> print ', '.join(map(CC.str_of_setting,c.settings))
    x=2, y=1, z=1, z=0

    >>> dom = Dom([('x',frozenset(['1','2'])),\
    ('y',frozenset(['1'])),\
    ('z',frozenset(['0','1','2'])),\
    ('w',frozenset(['a','b','c']))\
    ])

    >>> print c.neg(dom)
    x=1 z=2

    >>> c = Core([('x',frozenset(['2'])),('z',frozenset(['0','1'])),('w',frozenset(['a']))])
    >>> print c.neg(dom)
    x=1 z=2 w=b,c

    """
    def __init__(self,core=HDict()):
        HDict.__init__(self,core)
        
        if CM.__vdebug__:
            assert all(CC.is_csetting(s)
                       for s in self.iteritems()), self

    def __str__(self,delim=' '):
        if self:
            return delim.join(map(CC.str_of_csetting,self.iteritems()))
        else:
            return 'true'

    @property
    def settings(self):
        return [(k,v) for k,vs in self.iteritems() for v in vs]
        
    def neg(self,dom):
        try:
            return self._neg
        except AttributeError:
            if CM.__vdebug__:
                assert isinstance(dom,Dom),dom
            ncore = ((k,dom[k]-self[k]) for k in self)
            self._neg = Core([(k,vs) for k,vs in ncore if vs])
            return self._neg
        
    def z3expr(self,z3db,myf):
        f = []
        for vn,vs in self.iteritems():
            vn_,vs_ = z3db[vn]
            f.append(z3util.myOr([vn_ == vs_[v] for v in vs]))

        return myf(f)
    
    @staticmethod
    def is_maybe_core(c): return c is None or isinstance(c,Core)

    
class MCore(tuple):
    """
    Multiple (tuples) cores
    """
    def __init__(self,cores):
        tuple.__init__(self,cores)

        if CM.__vdebug__:
            assert len(self) == 2 or len(self) == 4, self
            assert all(Core.is_maybe_core(c) for c in self), self

    @property
    def settings(self):
        core = (c for c in self if c)
        return set(s for c in core for s in c.iteritems())

    @property
    def values(self):
        core = (c for c in self if c)
        return set(s for c in core for s in c.itervalues())

    @property
    def sstren(self): return len(self.settings)
    
    @property
    def vstren(self): return sum(map(len,self.values))


class SCore(MCore):
    def __init__(self,(mc,sc)):
        """
        mc: main core that will generate cex's
        sc (if not None): sat core that is satisfied by all generated cex'
        """
        super(SCore,self).__init__((mc,sc))
        #additional assertion
        if CM.__vdebug__:
            assert mc is None or isinstance(mc,Core) and mc, mc
            #sc is not None => ...
            assert not sc or all(k not in mc for k in sc), sc
        self.keep = False

    def set_keep(self):
        """
        keep: if true then generated cex's with diff settings than mc 
        and also those that have the settings of mc
        """
        self.keep = True
    
    @property
    def mc(self): return self[0]

    @property
    def sc(self): return self[1]

    def __str__(self):
        ss = []
        if self.mc:
            s = ""
            try:  #to support old format that doesn't have keep
                if self.keep:
                    s = "(keep)" 
            except AttributeError:
                logger.warn("Old format, has no 'keep' in SCore")
                pass

            ss.append("mc{}: {}".format(s,self.mc))
                                            
                      
        if self.sc:
            ss.append("sc: {}".format(self.sc))
        return '; '.join(ss)        
        
    @staticmethod
    def mk_default(): return SCore((None,None))
        
class PNCore(MCore):
    """
    >>> pc = Core([('x',frozenset(['0','1'])),('y',frozenset(['1']))])
    >>> pd = None
    >>> nc = Core([('z',frozenset(['1']))])
    >>> nd = None
    >>> pncore = PNCore((pc,pd,nc,nd))
    >>> print pncore
    pc: x=0,1 y=1; nc: z=1

    >>> dom = Dom([('x',frozenset(['0','1','2'])),\
    ('y',frozenset(['0','1'])),\
    ('z',frozenset(['0','1'])),\
    ('w',frozenset(['0','1']))\
    ])
    >>> z3db = dom.z3db

    >>> print PNCore._get_str(pc,pd,dom,is_and=True)
    (x=0,1 & y=1)
    >>> print PNCore._get_expr(pc,pd,dom,z3db,is_and=True)
    And(Or(x == 1, x == 0), y == 1)

    >>> print PNCore._get_str(nd,nc,dom,is_and=False)
    z=0
    >>> print PNCore._get_expr(nd,nc,dom,z3db,is_and=False)
    z == 0
    >>> print pncore.z3expr(z3db,dom)
    And(And(Or(x == 1, x == 0), y == 1), z == 0)

    >>> pc = Core([])
    >>> pd = None
    >>> nc = None
    >>> nd = None
    >>> pncore = PNCore((pc,pd,nc,nd))

    >>> assert PNCore._get_str(pc,pd,dom,is_and=True) == 'true'
    >>> assert PNCore._get_str(nd,nc,dom,is_and=False) == 'true'
    >>> assert PNCore._get_expr(pc,pd,dom,z3db,is_and=True) is None
    >>> assert PNCore._get_expr(nd,nc,dom,z3db,is_and=True) is None
    >>> assert pncore.z3expr(z3db,dom) is None

    """

    def __init__(self,(pc,pd,nc,nd)):
        super(PNCore,self).__init__((pc,pd,nc,nd))

    @property
    def pc(self): return self[0]
    @property
    def pd(self): return self[1]
    @property
    def nc(self): return self[2]
    @property
    def nd(self): return self[3]

    @property
    def vtyp(self): return self._vtyp
    @vtyp.setter
    def vtyp(self,vt):
        if CM.__vdebug__:
            assert isinstance(vt,str) and \
                vt in 'conj disj mix'.split(), vt
        self._vtyp = vt
    
    @property
    def vstr(self): return self._vstr
    
    @vstr.setter
    def vstr(self,vs):
        if CM.__vdebug__:
            assert isinstance(vs,str) and vs, vs
        self._vstr = vs

    @staticmethod
    def mk_default(): return PNCore((None,None,None,None))

    def __str__(self):
        try:
            return "{} ({})".format(self.vstr,self.vtyp)
        except AttributeError:
            ss = ("{}: {}".format(s,c) for s,c in
                  zip('pc pd nc nd'.split(),self) if c is not None)
            return '; '.join(ss)

    def verify(self,configs,dom):
        if CM.__vdebug__:
            assert self.pc is not None, self.pc #this never happens
            #nc is None => pd is None
            assert self.nc is not None or self.pd is None, (self.nc,self.nd)
            assert all(isinstance(c,Config) for c in configs) and configs, configs
            assert isinstance(dom,Dom),dom

        pc,pd,nc,nd = self

        #traces => pc & neg(pd)
        if CM.__vdebug__:
            if pc:
                assert all(c.c_implies(pc) for c in configs), pc

        if pd:
            pd_n = pd.neg(dom)
            if not all(c.d_implies(pd_n) for c in configs):
                logger.debug('pd {} invalid'.format(pd))
                pd = None

        #neg traces => nc & neg(nd)
        #pos traces => neg(nc & neg(nd))
        #pos traces => nd | neg(nc) 
        if nc and not nd:
            nc_n = nc.neg(dom)
            if not all(c.d_implies(nc_n) for c in configs):
                logger.debug('nc {} invalid'.format(nc))
                nc = None
        elif not nc and nd:
            if not all(c.c_implies(nd) for c in configs):
                logger.debug('nd {} invalid'.format(nd))
                nd = None
        elif nc and nd:
            nc_n = nc.neg(dom)        
            if not all(c.c_implies(nd) or
                       c.d_implies(nc_n) for c in configs):
                logger.debug('nc {} & nd {} invalid').format(nc,nd)
                nc = None
                nd = None

        return PNCore((pc,pd,nc,nd))
    
    @staticmethod
    def _get_expr(cc,cd,dom,z3db,is_and):
        fs = []
        if cc:
            f = cc.z3expr(z3db,myf=z3util.myAnd)
            fs.append(f)
        if cd:
            cd_n = cd.neg(dom)
            f = cd_n.z3expr(z3db,myf=z3util.myOr)
            fs.append(f)

        myf = z3util.myAnd if is_and else z3util.myOr
        return myf(fs)

    @staticmethod
    def _get_str(cc,cd,dom,is_and):
        and_delim = ' & '
        or_delim = ' | '

        def _str(core,delim):
            s = core.__str__(delim)
            if len(core) > 1:
                s = '({})'.format(s)
            return s
        
        ss = []
        if cc:
            s = _str(cc,and_delim)
            ss.append(s)
        if cd:
            cd_n = cd.neg(dom)
            s = _str(cd_n,or_delim)
            ss.append(s)

        delim = and_delim if is_and else or_delim
        return delim.join(sorted(ss)) if ss else 'true'
        
    @staticmethod
    def _get_expr_str(cc,cd,dom,z3db,is_and):
        expr = PNCore._get_expr(cc,cd,dom,z3db,is_and)
        vstr = PNCore._get_str(cc,cd,dom,is_and)
        return expr,vstr

    
    def simplify(self,dom,do_firsttime=True):
        """
        Compare between (pc,pd) and (nc,nd) and return the stronger one.
        This will set either (pc,pd) or (nc,nd) to (None,None)

        if do_firstime is False then don't do any checking,
        essentialy this option is used for compatibility purpose

        Assumption: all 4 cores are verified

        inv1 = pc & not(pd)
        inv2 = not(nc & not(nd)) = nd | not(nc)
        """
        if CM.__vdebug__:
            assert isinstance(dom,Dom),dom

            if do_firsttime:
                assert self.pc is not None, self.pc #this never could happen
                #nc is None => pd is None
                assert self.nc is not None or self.pd is None, (self.nc,self.nd)

        #pf = pc & neg(pd)
        #nf = neg(nc & neg(nd)) = nd | neg(nc)
        pc,pd,nc,nd = self

        #remove empty ones
        if not pc: pc = None
        if not pd: pd = None
        if not nc: nc = None
        if not nd: nd = None

        z3db = dom.z3db
        if pc is None and pd is None:
            expr,vstr = PNCore._get_expr_str(nd,nc,dom,z3db,is_and=False)
        elif nc is None and nd is None:
            expr,vstr = PNCore._get_expr_str(pc,pd,dom,z3db,is_and=True)
        else:
            pexpr,pvstr = PNCore._get_expr_str(pc,pd,dom,z3db,is_and=True)
            nexpr,nvstr = PNCore._get_expr_str(nd,nc,dom,z3db,is_and=False)
            
            if CM.__vdebug__:
                assert pexpr is not None
                assert nexpr is not None

            if z3util.is_tautology(z3.Implies(pexpr,nexpr)):
                nc = None
                nd = None
                expr = pexpr
                vstr = pvstr
            elif z3util.is_tautology(z3.Implies(nexpr,pexpr)):
                pc = None
                pd = None
                expr = nexpr
                vstr = nvstr
            else:  #could occur when using incomplete traces
                logger.warn("inconsistent ? {}\npf: {} ?? nf: {}"
                            .format(PNCore((pc,pd,nc,nd)),pexpr,nexpr))

                expr = z3util.myAnd([pexpr,nexpr])
                vstr = ','.join([pvstr,nvstr]) + '***'

        def _typ(s):
            #hackish way to get type
            if ' & ' in s and ' | ' in s:
                return 'mix'
            elif ' | ' in s:
                return 'disj'
            else:
                return 'conj'         
        
        core = PNCore((pc,pd,nc,nd))
        core.vstr = vstr
        core.vtyp = _typ(vstr)
        
        return core,expr

    def is_simplified(self):
        return ((self.pc is None and self.pd is None) or
                (self.nc is None and self.nd is None))

    def z3expr(self,z3db,dom):
        """
        Note: z3 expr "true" is represented (and returned) as None
        """
        pc,pd,nc,nd = self
        if pc is None and pd is None:
            expr = PNCore._get_expr(nd,nc,dom,z3db,is_and=False)
        elif nc is None and nd is None:
            expr = PNCore._get_expr(pc,pd,dom,z3db,is_and=True)
        else:
            pexpr = PNCore._get_expr(pc,pd,dom,z3db,is_and=True)
            nexpr = PNCore._get_expr(nd,nc,dom,z3db,is_and=False)
            expr = z3util.myAnd([pexpr,nexpr])
        return expr

    @staticmethod
    def is_expr(expr):
        #not None => z3expr
        return expr is None or z3.is_expr(expr)
    
class Cores_d(CC.CustDict):
    """
    rare case when diff c1 and c2 became equiv after simplification

    c1 = a & b
    >>> pc = Core([('a',frozenset('1'))])
    >>> pd = Core([('b',frozenset('0'))])
    >>> nc = Core()
    >>> nd = Core()
    >>> c1 = PNCore((pc,pd,nc,nd))

    c2 = b & a 
    >>> pc = Core([('b',frozenset('1'))])
    >>> pd = Core([('a',frozenset('0'))])
    >>> nc = Core()
    >>> nd = Core()
    >>> c2 = PNCore((pc,pd,nc,nd))

    >>> cores_d = Cores_d()
    >>> cores_d['L1'] = c1
    >>> cores_d['L2'] = c2
    >>> print cores_d
    1. L1: pc: a=1; pd: b=0; nc: true; nd: true
    2. L2: pc: b=1; pd: a=0; nc: true; nd: true

    >>> print cores_d.merge()
    1. (2) pc: a=1; pd: b=0; nc: true; nd: true: (1) L1
    2. (2) pc: b=1; pd: a=0; nc: true; nd: true: (1) L2

    >>> dom = Dom([('a',frozenset(['0','1'])),('b',frozenset(['0','1']))])
    >>> covs_d = CC.Covs_d()
    >>> config = Config([('a', '1'), ('b', '1')])
    >>> covs_d.add('L1',config)
    >>> covs_d.add('L2',config)

    >>> logger.level = CM.VLog.WARN
    >>> cores_d = cores_d.analyze(dom,covs_d)
    >>> print cores_d.merge(show_detail=False)
    1. (2) a=1 & b=1 (conj): (2) L1,L2

    >>> cores_d = cores_d.analyze(dom,covs_d=None)
    >>> print cores_d.merge(show_detail=False)
    1. (2) a=1 & b=1 (conj): (2) L1,L2

    """
    def __setitem__(self,sid,pncore):
        if CM.__vdebug__:
            assert isinstance(sid,str),sid
            assert isinstance(pncore,PNCore),pncore
        self.__dict__[sid]=pncore

    def __str__(self):
        return '\n'.join("{}. {}: {}"
                         .format(i+1,sid,self[sid])
                         for i,sid in enumerate(sorted(self)))

    def merge(self,show_detail=False):
        mcores_d = Mcores_d()
        cache = {}
        for sid,core in self.iteritems():
            try:
                key = core.vstr 
            except AttributeError:
                key = core
                
            if key not in cache:
                core_ = core
                cache[key] = core_
            else:
                core_ = cache[key]
            mcores_d.add(core_,sid)

        if show_detail:
            logger.debug("mcores_d has {} items\n{}"
                         .format(len(mcores_d),mcores_d))
            logger.info("mcores_d strens (stren, nresults, nsids): {}".format(mcores_d.strens_str))
            
        return mcores_d

    def analyze(self,dom,covs_d):
        """
        Simplify cores. If covs_d then also check that cores are valid invs
        """
        if CM.__vdebug__:
            if covs_d is not None:
                assert isinstance(covs_d,CC.Covs_d) and covs_d, covs_d
                assert len(self) == len(covs_d), (len(self),len(covs_d))
            assert isinstance(dom,Dom), dom

        def show_compare(sid,old_c,new_c):
            if old_c != new_c:
                logger.debug("sid {}: {} ~~> {}".
                             format(sid,old_c,new_c))

        cores_d = Cores_d()                
        logger.info("analyze results for {} sids".format(len(self)))

        if covs_d:
            logger.debug("verify ...")
            cache = {}
            for sid,core in self.iteritems():
                configs = frozenset(covs_d[sid])
                key = (core,configs)
                if key not in cache:
                    core_ = core.verify(configs,dom)
                    cache[key]=core_
                    show_compare(sid,core,core_)
                else:
                    core_ = cache[key]

                cores_d[sid]=core
        else:
            cores_d = self

        logger.debug("simplify ...")
        cache = {}
        for sid in cores_d:
            core = cores_d[sid]
            if core not in cache:
                core_,expr = core.simplify(dom,do_firsttime=(covs_d is not None))
                cache[core]=core_
                show_compare(sid,core,core_)
            else:
                core_ = cache[core]
            cores_d[sid]=core_

        return cores_d
    
class Mcores_d(CC.CustDict):
    """
    A mapping from core -> {sids}
    """
    def add(self,core,sid):
        if CM.__vdebug__:
            assert isinstance(core,PNCore),core
            assert isinstance(sid,str),str
        super(Mcores_d,self).add_set(core,sid)

    def __str__(self):
        mc = sorted(self.iteritems(),
                    key=lambda (core,cov): (core.sstren,core.vstren,len(cov)))
        ss = ("{}. ({}) {}: {}"
              .format(i+1,core.sstren,core,CC.str_of_cov(cov))
              for i,(core,cov) in enumerate(mc))
        return '\n'.join(ss)

    @property
    def vtyps(self):
        d = {'conj':0,'disj':0,'mix':0}
        for core in self:
            vtyp = core.vtyp
            d[vtyp] = d[vtyp] + 1

        return (d['conj'],d['disj'],d['mix'])
    
    @property
    def strens(self):
        """
        (strength,cores,sids)
        """
        strens = set(core.sstren for core in self)

        rs = []
        for stren in sorted(strens):
            cores = [c for c in self if c.sstren == stren]
            cov = set(sid for core in cores for sid in self[core])
            rs.append((stren,len(cores),len(cov)))
        return rs

    @property
    def strens_str(self): return self.str_of_strens(self.strens)

    @staticmethod
    def str_of_strens(strens):
        return ', '.join("({}, {}, {})".format(siz,ncores,ncov)
                         for siz,ncores,ncov in strens)

#Inference algorithm
class Infer(object):
    @staticmethod
    def infer(configs,core,dom):
        """
        Approximation in *conjunctive* form
        """
        if CM.__vdebug__:
            assert (all(isinstance(c,Config) for c in configs)
                    and configs), configs
            assert Core.is_maybe_core(core),core
            assert isinstance(dom,Dom),dom

        if core is None:  #not yet set
            core = min(configs,key=lambda c:len(c))
            core = Core((k,frozenset([v])) for k,v in core.iteritems())

        def f(k,s,ldx):
            s_ = set(s)
            for config in configs:
                if k in config:
                    s_.add(config[k])
                    if len(s_) == ldx:
                        return None
                else:
                    return None
            return s_

        vss = [f(k,vs,len(dom[k])) for k,vs in core.iteritems()]
        core = Core((k,frozenset(vs)) for k,vs in zip(core,vss) if vs)
        return core  

    @staticmethod
    def infer_cache(core,configs,dom,cache):
        if CM.__vdebug__:
            assert core is None or isinstance(core,Core),core
            assert (configs and
                    all(isinstance(c,Config) for c in configs)), configs
            assert isinstance(dom,Dom),dom
            assert isinstance(cache,dict),cache

        configs = frozenset(configs)
        key = (core,configs)
        if key not in cache:
            cache[key] = Infer.infer(configs,core,dom)
        return cache[key]

    @staticmethod
    def infer_sid(sid,core,cconfigs_d,configs_d,covs_d,dom,cache):
        if CM.__vdebug__:
            assert isinstance(sid,str),sid
            assert isinstance(core,PNCore),core
            assert (cconfigs_d and
                    isinstance(cconfigs_d,CC.Configs_d)),cconfigs_d
            assert isinstance(configs_d,CC.Configs_d),configs_d
            assert isinstance(covs_d,CC.Covs_d),covs_d
            assert isinstance(dom,Dom),dom        
            assert isinstance(cache,dict),cache

        def _f(configs,cc,cd,_b):
            new_cc,new_cd = cc,cd
            if configs:
                new_cc = Infer.infer_cache(cc,configs,dom,cache)

            #TODO: this might be a bug, if new_cc is empty,
            #then new_cd won't be updated
            if new_cc:
                configs_ = [c for c in _b() if c.c_implies(new_cc)]
                if configs_:
                    new_cd = Infer.infer_cache(cd,configs_,dom,cache)
                    if new_cd:
                        new_cd = Core((k,v) for (k,v) in new_cd.iteritems()
                                      if k not in new_cc)

            return new_cc,new_cd

        pc,pd,nc,nd = core
        
        pconfigs = [c for c in cconfigs_d if sid in cconfigs_d[c]]
 
        if nc is None:
            #never done nc, so has to consider all traces
            nconfigs = [c for c in configs_d if sid not in configs_d[c]]
        else:
            #done nc, so can do incremental traces
            nconfigs = [c for c in cconfigs_d if sid not in cconfigs_d[c]]
            
        _b = lambda: [c for c in configs_d if sid not in configs_d[c]]
        pc_,pd_ = _f(pconfigs,pc,pd,_b)
        
        _b = lambda: covs_d[sid]
        nc_,nd_ = _f(nconfigs,nc,nd,_b)
        return PNCore((pc_,pd_,nc_,nd_))

    @staticmethod
    def infer_covs(cores_d,cconfigs_d,configs_d,covs_d,dom):
        if CM.__vdebug__:
            assert isinstance(cores_d,Cores_d),cores_d
            assert isinstance(cconfigs_d,CC.Configs_d) and cconfigs_d,cconfigs_d
            assert isinstance(configs_d,CC.Configs_d),configs_d        
            assert all(c not in configs_d for c in cconfigs_d),cconfigs_d
            assert isinstance(covs_d,CC.Covs_d),covs_d
            assert isinstance(dom,Dom),dom

        sids = set(cores_d.keys())
        #update configs_d and covs_d
        for config in cconfigs_d:
            for sid in cconfigs_d[config]:
                sids.add(sid)
                covs_d.add(sid,config)

            assert config not in configs_d, config
            configs_d[config]=cconfigs_d[config]

        cache = {}
        new_covs,new_cores = set(),set()  #updated stuff    
        for i,sid in enumerate(sorted(sids)):
            if sid in cores_d:
                core = cores_d[sid]
            else:
                core = PNCore.mk_default()
                new_covs.add(sid)

            core_ = Infer.infer_sid(sid,core,cconfigs_d,
                                    configs_d,covs_d,dom,cache)
            if not core_ == core: #progress
                new_cores.add(sid)
                cores_d[sid] = core_

        return new_covs,new_cores


class IGen(object):
    """
    Main algorithm
    """
    def __init__(self,dom,get_cov,config_default=None):
        if CM.__vdebug__:
            assert isinstance(dom,Dom),dom
            assert callable(get_cov),get_cov
            assert (config_default is None or
                    isinstance(config_default,Config)), config_default
            
        self.dom = dom
        self.z3db = self.dom.z3db
        self.get_cov = get_cov
        self.config_default = config_default

    def go(self,seed=None,rand_n=None,existing_results=None,tmpdir=None):
        """
        rand_n = None: use default interative mode
        rand_n = 0  : use init configs
        rand_n > 0  : use rand_n configs
        rand_n < 0  : use all possible configs
        """
        if CM.__vdebug__:
            assert isinstance(tmpdir,str) and os.path.isdir(tmpdir), tmpdir
            assert seed is None or isinstance(seed,float)

        random.seed(seed)
        logger.info("seed: {}, tmpdir: {}".format(seed,tmpdir))

        DTrace.save_pre(seed,self.dom,tmpdir)

        #some settings
        cur_iter = 1
        min_stren = 1
        cur_min_stren = min_stren
        cur_stuck = 0
        max_stuck = 3
        do_perturb = True #set this to True will not do any perturbing
        cores_d,configs_d,covs_d = Cores_d(),CC.Configs_d(),CC.Covs_d()
        sel_core = SCore.mk_default()
        ignore_sel_cores = set()

        #begin
        st = time()
        ct = st
        xtime_total = 0.0
        
        configs = self.gen_configs_init(rand_n,seed)
        if self.config_default:
            logger.debug("add default config")
            configs.append(self.config_default)
            
        cconfigs_d,xtime = self.eval_configs(configs)
        xtime_total += xtime
        new_covs,new_cores = Infer.infer_covs(cores_d,cconfigs_d,
                                              configs_d,covs_d,self.dom)
        while True:
            ct_ = time();itime = ct_ - ct;ct = ct_
            dtrace = DTrace(
                cur_iter,itime,xtime,
                len(configs_d),len(covs_d),len(cores_d),
                cconfigs_d,
                new_covs,new_cores,
                sel_core,
                cores_d)
            dtrace.show()
            DTrace.save_iter(cur_iter,dtrace,tmpdir)

            if rand_n is not None:
                break

            cur_iter += 1
            sel_core,configs = self.gen_configs_iter(
                set(cores_d.values()),ignore_sel_cores,
                cur_min_stren,configs_d)

            stop = False
            if sel_core is None:
                if do_perturb: #if already perturb
                    stop = True
                else:
                    do_perturb = True
                    logger.debug("perturb !")
                    sel_core,configs = self.gen_configs_iter(
                        set(cores_d.values()),set(),cur_min_stren,configs_d)
                    if sel_core is None:
                        stop = True
                        
                if stop:
                    cur_iter -= 1
                    logger.info('done after iter {}'.format(cur_iter))
                    break

            assert configs,configs
            cconfigs_d,xtime = self.eval_configs(configs)
            xtime_total += xtime
            new_covs,new_cores = Infer.infer_covs(
                cores_d,cconfigs_d,configs_d,covs_d,self.dom)

            if new_covs or new_cores: #progress
                cur_stuck = 0
                cur_min_stren = min_stren
            else: #no progress
                cur_stuck += 1
                if cur_stuck > max_stuck:
                    cur_stuck = 0
                    cur_min_stren += 1
                    print('cur_min_stren is now {}'.format(cur_min_stren))

        #postprocess
        pp_cores_d = cores_d.analyze(self.dom,covs_d)
        mcores_d = pp_cores_d.merge(show_detail=True)
        itime_total = time() - st
        
        logger.info(DTrace.str_of_summary(
            seed,cur_iter,itime_total,xtime_total,
            len(configs_d),len(covs_d),tmpdir))
        logger.info("Done (seed {}, test {})"
                    .format(seed,random.randrange(100)))
        DTrace.save_post(pp_cores_d,itime_total,tmpdir)
        
        return pp_cores_d,cores_d,configs_d,covs_d,self.dom

    #Shortcuts
    def go_full(self,tmpdir=None):
        return self.go(seed=None,rand_n=-1,
                       existing_results=None,tmpdir=tmpdir)

    def go_rand(self,rand_n,seed=None,tmpdir=None):
        return self.go(seed=seed,rand_n=rand_n,
                       existing_results=None,tmpdir=tmpdir)

    def go_minconfigs(self,seed,existing_results,tmpdir=None):
        return self.go(seed=seed,rand_n=None,
                       existing_results=existing_results,tmpdir=tmpdir)

    #Helper functions
    def eval_configs(self,configs):
        if CM.__vdebug__:
            assert (isinstance(configs,list) and
                    all(isinstance(c,Config) for c in configs)
                    and configs), configs
        st = time()
        cconfigs_d = CC.Configs_d()
        for c in configs:
            if c in cconfigs_d: #skip
                continue

            sids,outps = self.get_cov(c)
            if analyze_outps:
                cconfigs_d[c]=outps
            else:
                cconfigs_d[c]=sids
        return cconfigs_d,time() - st

    def gen_configs_init(self,rand_n,seed):
        if not rand_n: #None or 0
            configs = self.dom.gen_configs_tcover1()
            logger.info("gen {} configs using tcover 1".format(len(configs)))
        elif rand_n > 0 and rand_n < self.dom.siz:        
            configs = self.dom.gen_configs_rand_smt(rand_n)
            logger.info("gen {} rand configs".format(len(configs)))
        else:
            configs = self.dom.gen_configs_full(config_cls=Config)
            logger.info("gen all {} configs".format(len(configs)))

        configs = list(set(configs))
        assert configs, 'no initial configs created'
        return configs
        
    def gen_configs_iter(self,cores,ignore_sel_cores,min_stren,configs_d):
        if CM.__vdebug__:
            assert (isinstance(cores,set) and 
                    all(isinstance(c,PNCore) for c in cores)), cores
            assert (isinstance(ignore_sel_cores,set) and 
                    all(isinstance(c,SCore) for c in ignore_sel_cores)),\
                    ignore_sel_cores
            assert isinstance(configs_d,CC.Configs_d),configs_d

        configs = []
        while True:
            sel_core = self.select_core(cores,ignore_sel_cores,min_stren)
            if sel_core is None:
                break

            configs = self.dom.gen_configs_cex(                
                sel_core,configs_d,self.z3db)
            configs = list(set(configs)) 
            if configs:
                break
            else:
                logger.debug("no cex's created for sel_core {}, try new core"
                             .format(sel_core))

        #self_core -> configs
        if CM.__vdebug__:
            assert not sel_core or configs, (sel_core,configs)
            assert all(c not in configs_d for c in configs), configs

        return sel_core, configs

    @staticmethod
    def select_core(pncores,ignore_sel_cores,min_stren):
        """
        Returns either None or SCore
        """
        if CM.__vdebug__:
            assert all(isinstance(c,PNCore) for c in pncores) and pncores,pncores
            assert (isinstance(ignore_sel_cores,set) and
                    all(isinstance(c,SCore) for c in ignore_sel_cores)),\
                    ignore_sel_cores

        sel_cores = []
        for (pc,pd,nc,nd) in pncores:
            #if can add pc then don't cosider pd (i.e., refine pc first)
            if pc and (pc,None) not in ignore_sel_cores:
                sc = SCore((pc,None))
                if pd is None: sc.set_keep()
                sel_cores.append(sc)
                    
            elif pd and (pd,pc) not in ignore_sel_cores:
                sc = SCore((pd,pc))
                sel_cores.append(sc)

            if nc and (nc,None) not in ignore_sel_cores:
                sc = SCore((nc,None))
                if nd is None: sc.set_keep()
                sel_cores.append(sc)

            elif nd and (nd,nc) not in ignore_sel_cores:
                sc = SCore((nd,nc))
                sel_cores.append(sc)
                
        sel_cores = [c for c in sel_cores if c.sstren >= min_stren]

        if sel_cores:
            sel_core = max(sel_cores,key=lambda c: (c.sstren,c.vstren))
            ignore_sel_cores.add(sel_core)
        else:
            sel_core = None

        return sel_core

class DTrace(object):
    """
    Object for saving information (for later analysis)
    """
    def __init__(self,citer,itime,xtime,
                 nconfigs,ncovs,ncores,
                 cconfigs_d,new_covs,new_cores,
                 sel_core,cores_d):

        self.citer = citer
        self.itime = itime
        self.xtime = xtime
        self.nconfigs = nconfigs
        self.ncovs = ncovs
        self.ncores = ncores
        self.cconfigs_d = cconfigs_d
        self.new_covs = new_covs
        self.new_cores = new_cores
        self.sel_core = sel_core
        self.cores_d = cores_d
        
    def show(self):
        logger.info("ITER {}, ".format(self.citer) +
                    "{}s, ".format(self.itime) +
                    "{}s eval, ".format(self.xtime) +
                    "total: {} configs, {} covs, {} cores, "
                    .format(self.nconfigs,self.ncovs,self.ncores) +
                    "new: {} configs, {} covs, {} updated cores, "
                    .format(len(self.cconfigs_d),
                            len(self.new_covs),len(self.new_cores)) +
                    "{}".format("** progress **"
                                if self.new_covs or self.new_cores else ""))

        logger.debug('select core: ({}) {}'.format(self.sel_core.sstren,
                                                   self.sel_core))
        logger.debug('create {} configs'.format(len(self.cconfigs_d)))
        logger.detail("\n"+str(self.cconfigs_d))
        mcores_d = self.cores_d.merge()
        logger.debug("infer {} interactions".format(len(mcores_d)))
        logger.detail('\n{}'.format(mcores_d))
        logger.info("strens: {}".format(mcores_d.strens_str))

    @staticmethod
    def save_pre(seed,dom,tmpdir):
        CM.vsave(os.path.join(tmpdir,'pre'),(seed,dom))

    @staticmethod
    def save_post(pp_cores_d,itime_total,tmpdir):
        CM.vsave(os.path.join(tmpdir,'post'),(pp_cores_d,itime_total))

    @staticmethod
    def save_iter(cur_iter,dtrace,tmpdir):
        CM.vsave(os.path.join(tmpdir,'{}.tvn'.format(cur_iter)),dtrace)


    @staticmethod
    def load_pre(dir_):
        seed,dom = CM.vload(os.path.join(dir_,'pre'))
        return seed,dom
    @staticmethod
    def load_post(dir_):
        pp_cores_d,itime_total = CM.vload(os.path.join(dir_,'post'))
        return pp_cores_d,itime_total
    @staticmethod
    def load_iter(dir_,f):
        dtrace =CM.vload(os.path.join(dir_,f))
        return dtrace

    @staticmethod
    def str_of_summary(seed,iters,itime,xtime,nconfigs,ncovs,tmpdir):
        ss = ["Seed {}".format(seed),
              "Iters {}".format(iters),
              "Time ({}s, {}s)".format(itime,xtime),
              "Configs {}".format(nconfigs),
              "Covs {}".format(ncovs),
              "Tmpdir {}".format(tmpdir)]
        return "Summary: " + ', '.join(ss)    

    @staticmethod
    def load_dir(dir_):
        seed,dom = DTrace.load_pre(dir_)
        dts = [DTrace.load_iter(dir_,f)
               for f in os.listdir(dir_) if f.endswith('.tvn')]
        try:
            pp_cores_d,itime_total = DTrace.load_post(dir_)
        except IOError:
            logger.error("post info not avail")
            pp_cores_d,itime_total = None,None
        return seed,dom,dts,pp_cores_d,itime_total
    
if __name__ == "__main__":
    import doctest
    doctest.testmod()