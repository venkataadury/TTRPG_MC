import numpy as np
from dice import *
import re
import tqdm

def chance(p):
    return np.random.uniform(0,1)<p

class Tactic:
    def __init__(self,aroll,dc,succ_form,fail_form=None,extra_crit_damage=None):
        self.rollstr=aroll
        #self.aroll=parse_dice(aroll)
        self.dc=dc
        self.succform=succ_form
        if fail_form is not None: self.failform=fail_form
        else: self.failform="0"
        self.extra_crit_damage=extra_crit_damage
    
    def hit_roll(self,charsheet=None,p_adv=0,p_disadv=0,n_dice=2,crit_range=20):
        if charsheet is None:
            rollstr=self.rollstr
        else:
            rollstr=charsheet.parse_string(self.rollstr)
        
        self.aroll=parse_dice(rollstr)

        if p_adv>0:
            #print("ADV")
            if np.random.uniform(0,1)<p_adv:
                rl=Advantage(self.aroll,n_dice)
            else:
                rl=self.aroll
        elif p_disadv>0:
            #print("DADV")
            if np.random.uniform(0,1)<p_adv:
                rl=Disadvantage(self.aroll,n_dice)
            else:
                rl=self.aroll
        else:
            rl=self.aroll
        die_roll=rl.roll()
        # Check if the roll is a crit
        if die_roll-rl.constant_part()>=crit_range:
            return (True,True) # (Success, Critical)
        else:
            return (die_roll>=self.dc,False)

    def damage(self,charsheet,succ,crit=False):
        if crit:
            self.succ=parse_dice(charsheet.parse_string(self.succform))
            r1=self.succ.roll()-self.succ.constant_part()
            r2=self.succ.roll()#-self.succ.constant_part()
            if self.extra_crit_damage is not None:
                r3=parse_dice(charsheet.parse_string(self.extra_crit_damage)).roll()
                return r1+r2+r3 # Extra Crit damage
            else:
                return r1+r2
        else:
            if succ:
                self.succ=parse_dice(charsheet.parse_string(self.succform))
                return self.succ.roll()
            else:
                self.fail=parse_dice(charsheet.parse_string(self.failform))
                return self.fail.roll()
    
    def get_round_damage(self,charsheet,p_adv=0,p_disadv=0,n_dice=2,crit_range=20):
        hit,crit=self.hit_roll(charsheet,p_adv=p_adv,p_disadv=p_disadv,n_dice=n_dice,crit_range=crit_range)
        return self.damage(charsheet,hit,crit),hit,crit

class CharacterData:
    def __init__(self,datafile,silent=False):
        self.file=datafile
        self.attributes=dict()
        self.globals=dict()
        self.tactics=dict()
        self.variables=dict()
        self.aliases=dict()
        self.round_script=[]
        self.specific_round_scripts=dict()
        self.shortrest_script=[]
        self._loadData(silent=silent)
        self._memorize()
    
    def _memorize(self):
        self.mem_variables=dict()
        for v in self.variables:
            self.mem_variables[v]=self.variables[v]
    def reset(self):
        for v in self.mem_variables:
            self.variables[v]=self.mem_variables[v]

    def _loadData(self,silent=False):
        self._loadDataFrom(self.file,silent=silent)

    def _loadDataFrom(self,filename,silent=False,start_mode=None):
        fl=open(filename,"r")
        mode=start_mode
        mode_param=None
        for l in fl:
            l=l.strip()
            l=l.split(';')[0].strip()

            if mode not in ["Tactics","Round","ShortRest","Alias"] and len(l):
                for att in self.attributes:
                    l=l.replace("$"+att,str(self.attributes[att]))
                for v in self.variables:
                    l=l.replace("$"+v,str(self.variables[v]))
            for att in self.attributes:
                l=l.replace("%"+att,str(self.attributes[att]))
            for v in self.variables:
                l=l.replace("%"+v,str(self.variables[v]))
            if not len(l): continue

            if l[0]=='@':
                l=l[1:].strip()
                l=l.split(":")
                if len(l)>1:
                    mode=l[0].strip()
                    mode_param=l[1].strip()
                else:
                    mode=l[0].strip()
                    mode_param=None
                if not silent:
                    print("Found section:",mode,"with parameter:",mode_param)
                continue
            
            if l[0]==">": # Import from an external file
                l=l[1:].strip()
                if not silent:
                    print("Importing from file:",l)
                base_dir=filename.split("/")
                base_dir="/".join(base_dir[:-1])+"/"
                if not silent: print("Importing from:",base_dir+l)
                self._loadDataFrom(base_dir+l,silent=silent,start_mode=mode)
                continue

            if mode is None: continue
            if mode=="Attributes":
                l=l.split("=")
                atval=float(l[1].strip())
                atname=l[0].strip()
                self.attributes[atname]=atval
                if not silent: print("\tAttribute:",atname+"="+str(atval))
            elif mode=="Variables":
                l=l.split("=")
                atval=str(l[1]).strip()
                atname=l[0].strip()
                self.variables[atname]=atval
                if not silent: print("\tVariable:",atname+"="+str(atval))
            elif mode=="Globals":
                l=l.split("=")
                atval=str(l[1]).strip()
                atname=l[0].strip()
                self.globals[atname]=atval
                if not silent: print("\tGlobal:",atname+"="+str(atval))
            elif mode=="Tactics":
                l=l.split(",")
                tname=l[0].strip()
                aroll=l[1].strip()
                if aroll=="None":
                    self.tactics[tname]=Tactic("1d20",1,"0","0") # Random tactic
                    if not silent: print("\tBlank tactic:",tname)
                    continue
                dc=int(eval(l[2].strip()))
                tsucc=l[3].strip()
                
                if len(l)>4: tfail=l[4].strip()
                else: tfail=None
                if len(l)>5: extra_crit_damage=l[5].strip()
                else: extra_crit_damage=None

                if tname in self.tactics:
                    if not silent: print("Replacing tactic:",tname)
                self.tactics[tname]=Tactic(aroll,dc,tsucc,tfail,extra_crit_damage=extra_crit_damage)
                if not silent: print("\tFound tactic:",tname," -\t",tsucc," (or",tfail if tfail is not None else 0,"on failure)")
            elif mode=="Alias":
                if mode_param is None:
                    raise ValueError("Alias name not present!")
                l=l.strip()
                if "<" in l:
                    l=l.split("<")
                    var=l[0].strip()
                    cmd=l[1].strip()
                else:
                    var="_"
                    cmd=l.strip()
                if mode_param in self.aliases:
                    self.aliases[mode_param].append((var,Command(cmd)))
                else:
                    self.aliases[mode_param]=[(var,Command(cmd))]
            elif mode=="Round":
                l=l.strip()
                #print("Round script:",l)
                if "<" in l:
                    l=l.split("<")
                    var=l[0].strip()
                    cmd=l[1].strip()
                else:
                    var="_"
                    cmd=l.strip()
                
                if mode_param is not None:
                    if int(mode_param) in self.specific_round_scripts:
                        self.specific_round_scripts[int(mode_param)].append((var,Command(cmd)))
                    else:
                        self.specific_round_scripts[int(mode_param)]=[(var,Command(cmd))]
                    if not silent: print("\tRegistered round script for round",mode_param,"with command:",cmd,"for variable:",var)
                else:
                    self.round_script.append((var,Command(cmd)))
            elif mode=="ShortRest":
                l=l.strip()
                if "<" in l:
                    l=l.split("<")
                    var=l[0].strip()
                    cmd=l[1].strip()
                else:
                    var="_"
                    cmd=l.strip()
                self.shortrest_script.append((var,Command(cmd)))
            else:
                print("Unknown mode:",mode)
                raise ValueError("Unknown mode in character data file")
    def run_line(self,var,cmdobj):
        damage,self.variables[var],crit=cmdobj.execute(self)
        self.variables[var+".crit_"]=crit
        label=cmdobj.cmd_name
        if label[0]=="~": label=label[1:]
        if crit:
            label+=" (Critical)"
        return label,damage,crit
    def run_round(self,rid=None):
        if rid is not None:
            if rid in self.specific_round_scripts:
                rscript=self.specific_round_scripts[rid]
            else:
                rscript=self.round_script
            self.variables["round"]=rid
        else:
            rscript=self.round_script
            self.variables["round"]=0
        #print("Running round",self.variables["_round_"])
        DPR=0
        paired_damage=[]
        for r in rscript:
            dlabel,damage,_=self.run_line(r[0],r[1])
            paired_damage.append((dlabel,damage))
            DPR+=damage
        return DPR,paired_damage
        
    def parse_string(self,string):
        for att in self.attributes:
            if "." in att: string=string.replace("$"+att,str(self.attributes[att]))
        for v in self.variables:
            if "." in v: string=string.replace("$"+v,str(self.variables[v]))
                
        for att in self.attributes:
            string=string.replace("$"+att,str(self.attributes[att]))
        for v in self.variables:
            string=string.replace("$"+v,str(self.variables[v]))
        string=string.strip()

        try:
            return str(eval(string))
        except:
            return string
    
    def gather_round_statistics(self,n_iter=1000,n_rounds=4):
        dpr_list=[]
        itemwise_damage=dict()
        for i in range(n_iter):
            self.reset()
            for r in range(1,n_rounds+1,1):
                dpr,dmg=self.run_round(r)
                round_itemwise=dict()
                for d in dmg:
                    if d[0] in round_itemwise:
                        round_itemwise[d[0]].append(d[1])
                    else:
                        round_itemwise[d[0]]=[d[1]]
                dpr_list.append(dpr)
                for i in round_itemwise:
                    round_itemwise[i]=np.sum(round_itemwise[i])
                    if i in itemwise_damage:
                        itemwise_damage[i].append(round_itemwise[i])
                    else:
                        itemwise_damage[i]=[round_itemwise[i]]
        
        # Average out item-wise damage for each item
        for i in itemwise_damage:
            mean,error=bootstrap_error(itemwise_damage[i])
            itemwise_damage[i]=(mean,np.std(itemwise_damage[i]),error)
        
        total_mean,total_error=bootstrap_error(dpr_list)
        return total_mean,np.std(dpr_list),total_error,itemwise_damage
    
    def estimate_adventuring_day(self,n_iter=1000,n_combats=4,short_rests=[2],n_rounds=4):
        dpr_list=[]
        itemwise_damage=dict()
        for i in tqdm.tqdm(range(n_iter),desc="Estimating adventuring day",ncols=100):
            self.reset()
            for c in range(n_combats):
                for r in range(1,n_rounds+1,1):
                    dpr,dmg=self.run_round(r)
                    round_itemwise=dict()
                    dmg_chk=0
                    for d in dmg:
                        if d[0] in round_itemwise:
                            round_itemwise[d[0]].append(d[1])
                        else:
                            round_itemwise[d[0]]=[d[1]]
                        if d[0] not in itemwise_damage:
                            itemwise_damage[d[0]]=[]
                        dmg_chk+=float(d[1])
                    dpr_list.append(dpr)
                    assert np.abs(dmg_chk-dpr)<1e-6

                    for i in itemwise_damage:
                        if i in round_itemwise:
                            round_itemwise[i]=np.sum(round_itemwise[i])
                            itemwise_damage[i].append(round_itemwise[i])
                        else:
                            itemwise_damage[i].append(0)
                if c in short_rests: self.short_rest()
        
        # Average out item-wise damage for each item
        for i in itemwise_damage:
            mean,error=bootstrap_error(itemwise_damage[i])
            itemwise_damage[i]=(mean,np.std(itemwise_damage[i]),error)
        
        total_mean,total_error=bootstrap_error(dpr_list)
        return total_mean,np.std(dpr_list),total_error,itemwise_damage
    
    def short_rest(self):
        for r in self.shortrest_script:
            self.run_line(r[0],r[1])
        return 0,[]

class Command:
    def __init__(self,cmdstr):
        self.cmd=cmdstr
        self.is_alias=False
        self._parseCommand()
    
    def _parseCommand(self):
        cmd_blocks=self.cmd.split(",")
        self.cmd_name=cmd_blocks[0].strip()
        if self.cmd_name[0]=="~":
            self.is_alias=True
        self.cmd_params=[]
        for c in cmd_blocks[1:]:
            c=c.strip()
            self.cmd_params.append(c)
    
    def execute(self,chardata):
        try:
            if self.is_alias:
                pass
            else:
                sel_tactic=chardata.tactics[self.cmd_name]
        except:
            #print(chardata.variables)
            ecomm=str(chardata.parse_string(self.cmd))
            #print("Evaluated command:",ecomm,)
            ret=eval(ecomm)
            return 0,ret,False
        p_adv=0
        p_disadv=0
        n_dice=2
        crit_range=20

        for p in self.cmd_params:
            p=p.split("=")
            if len(p)<2:
                pact=chardata.parse_string(p[0].strip())
                pact=float(eval(pact))
                if np.random.uniform(0,1)>pact: return 0,False,False
            else:
                pn=p[0].strip()
                pv=chardata.parse_string(p[1].strip())
                try:
                    pv=eval(pv)
                except:
                    pass

                if "adv" in pn: p_adv=float(pv)
                elif "disadv" in pn: p_disadv=float(pv)
                elif "n_dice" in pn: n_dice=int(pv)
                elif "crit" in pn: crit_range=int(pv)
                elif "consume" in pn: 
                    it=pv.split(" ")
                    c_var=it[1].strip()
                    c_amt=int(it[0].strip())
                    if c_var in chardata.variables:
                        if float(chardata.variables[c_var])<c_amt:
                            return 0,False,False
                        chardata.variables[c_var]=float(chardata.variables[c_var])-c_amt
                    else:
                        raise ValueError("Variable not found in character data! "+c_var)
        #print(chardata.variables)
        if self.is_alias:
            total_damage=0
            crit=False
            for a in chardata.aliases[self.cmd_name[1:]]:
                label,damage,crit=chardata.run_line(a[0],a[1])
                total_damage+=damage
            return total_damage,True,crit
        else:
            ret=sel_tactic.get_round_damage(chardata,p_adv=p_adv,p_disadv=p_disadv,n_dice=n_dice,crit_range=crit_range)
            return ret

def summarize_round_statistics(stats,breakdown=True):
    # Pretty print a banner
    print("\nRound Statistics")
    print("-"*20)
    print("Total Mean DPR:",round(stats[0],3),"+/-",round(stats[2],3))
    print("Observed DPR variation:",stats[1])
    if breakdown:
        print("Item-wise damage:")
        # Create list of all items sorted by name
        items=sorted(stats[3].keys())
        for i in items:
            #Ignore stats with mean 0
            if stats[3][i][0]<1e-6: continue
            print("\t",i,":",round(stats[3][i][0],3),"+/-",round(stats[3][i][2],3),"(Variation:",round(stats[3][i][1],3),")")