import numpy as np
import matplotlib.pyplot as plt # Needed?
import abc
import re

def bootstrap_error(vals,reduction=np.mean,nsamp=1000):
    means=[]
    for _ in range(nsamp): means.append(reduction(np.random.choice(vals,len(vals),replace=True)))
    return np.mean(means),np.std(means)

def estimateMC(fx,nsamp=2500,reduction=np.mean,return_error=True):
    vals=[fx() for _ in range(nsamp)]
    if not return_error: return np.mean(vals)
    return bootstrap_error(vals,reduction=reduction)


class FormulaComponent(metaclass=abc.ABCMeta):
    def __init__(self,name=None):
        self.name=name
        self.is_primitive=False

    @abc.abstractmethod
    def roll(self): pass

    @abc.abstractmethod
    def mean(self): pass

    @abc.abstractmethod
    def max(self): pass

    @abc.abstractmethod
    def min(self): pass

    @abc.abstractmethod
    def constant_part(self): return 0.0

    def mean_error(self): return 0.0

    def __str__(self): return self.name

class SignFlipped(FormulaComponent):
    def __init__(self,comp):
        super().__init__()
        self.comp=comp
        self.name="-[rep]"+str(self.comp)
        self.is_constant=self.comp.is_constant
    
    def roll(self): return -self.comp.roll()
    def mean(self): return -self.comp.mean()
    def min(self): return -self.comp.max()
    def max(self): return -self.comp.min()

    def constant_part(self): return -self.comp.constant_part()

class Advantage(FormulaComponent):
    def __init__(self,comp,n_reroll=2):
        super().__init__()
        self.comp=comp
        self.n=n_reroll
        bn=str(self.comp) if self.comp.is_primitive else "("+str(self.comp)+")"
        self.name=str(self.n)+bn+"k1"
        self.MC_mean=None
        self.MC_std=None
    
    def roll(self):
        rolls=[self.comp.roll() for _ in range(self.n)]
        return np.max(rolls)
    def max(self): return self.comp.max()
    def min(self): return self.comp.min()
    def mean(self):
        if self.MC_mean is None: self.MC_mean,self.MC_std=estimateMC(self.roll,reduction=np.mean)
        return self.MC_mean
    def mean_error(self): return self.MC_std

    def constant_part(self): return self.comp.constant_part()

class Disadvantage(FormulaComponent):
    def __init__(self,comp,n_reroll=2):
        super().__init__()
        self.comp=comp
        self.n=n_reroll
        bn=str(self.comp) if self.comp.is_primitive else "("+str(self.comp)+")"
        self.name=str(self.n)+bn+"l1"
        self.MC_mean=None
        self.MC_std=None
    
    def roll(self):
        rolls=[self.comp.roll() for _ in range(self.n)]
        return np.min(rolls)
    def max(self): return self.comp.max()
    def min(self): return self.comp.min()
    def mean(self):
        if self.MC_mean is None: self.MC_mean,self.MC_std=estimateMC(self.roll,reduction=np.mean)
        return self.MC_mean
    def mean_error(self): return self.MC_std
    def constant_part(self): return self.comp.constant_part()

class dN(FormulaComponent):
    def __init__(self,N):
        super().__init__()
        self.N=N
        self.name="d"+str(N)
        self.is_constant=False
        self.is_primitive=True
    
    def roll(self): return int(np.random.uniform(0,1)*self.N)+1
    def mean(self): return (self.N//2)+0.5
    def min(self): return 1
    def max(self): return self.N
    def constant_part(self): return 0.0

class Constant(FormulaComponent):
    def __init__(self,C):
        super().__init__()
        self.C=C
        self.name=str(np.round(C,3))
        self.is_constant=True
        self.is_primitive=True
    
    def roll(self): return self.C
    def mean(self): return self.C
    def min(self): return self.C
    def max(self): return self.C
    def constant_part(self): return self.C

class Formula(FormulaComponent):
    def __init__(self,components=[]):
        super().__init__()
        self.comp=[]
        if components is not None: self.comp=list(components)
        self._constructName()
        self.is_constant=np.all([o.is_constant for o in self.comp])
    
    def roll(self):
        if not len(self.comp): raise ValueError("No components in formula!")
        return np.sum([c.roll() for c in self.comp])
    def mean(self):
        if not len(self.comp): raise ValueError("No components in formula!")
        return np.sum([c.mean() for c in self.comp])
    def min(self):
        if not len(self.comp): raise ValueError("No components in formula!")
        return np.sum([c.min() for c in self.comp])
    def max(self):
        if not len(self.comp): raise ValueError("No components in formula!")
        return np.sum([c.max() for c in self.comp])
    def mean_error(self): return np.sum([o.mean_error() for o in self.comp])
    def constant_part(self): return np.sum([o.constant_part() for o  in self.comp])
    
    def _constructName(self):
        odict=dict()
        for o in self.comp:
            oname=o.name
            oconst=o.is_constant
            if oconst:
                if "const" in odict: odict["const"]+=o.mean()
                else: odict["const"]=o.mean()
                continue
            else:
                if oname in odict:  odict[oname]+=1
                else: odict[oname]=1
        ret=""
        const_term=None
        for k in odict:
            if k=="const": const_term=str(np.round(odict[k],3))
            else:
                if len(ret.strip()):
                    if "rep" not in k: ret+=" + "
                    else: ret+=" "
                if odict[k]!=1:
                    if "[rep]" in k: ret+=k.replace("[rep]"," "+str(odict[k]))
                    else:
                        ret+=str(odict[k])+str(k)
                else:
                    ret+=str(k.replace("[rep]"," "))
        if const_term is not None:
            ret+=" + "+str(const_term)
        self.name=ret.strip()

def parse_dice(dice_str):
    dice_str=dice_str.replace(" ","").replace("+-","-")
    sections=dice_str.replace("-","+").split("+")
    objs=[]
    for sec in sections:
        try:
            oint=float(eval(sec.strip()))
            objs.append(Constant(oint))
            continue
        except:
            pass
        if 'd' in sec:
            ss=sec.split("d")
            try:
                n_dice=int(ss[0].strip())
                die_size=int(ss[1].strip())
                all_dice=[]
                for _ in range(n_dice):
                    all_dice.append(dN(die_size))
                objs.append(Formula(all_dice))
            except:
                raise ValueError("Can't interpret dice string subsection: "+str(sec))
            continue
    return Formula(objs)