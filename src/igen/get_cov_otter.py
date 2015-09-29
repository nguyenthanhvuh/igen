from time import time
import random
import os.path
import vu_common as CM

import config as CF

logger = CM.VLog('otter')
logger.level = CF.logger.level

db = {"vsftpd":None,"ngircd":None}
from igen_settings import otter_dir


def prepare(prog):
    dir_ = CM.getpath(os.path.join(otter_dir,prog))
    dom_file = os.path.join(dir_,'possibleValues.txt')
    pathconds_d_file = os.path.join(dir_,'{}.tvn'.format('pathconds_d'))
    assert os.path.isfile(dom_file),dom_file
    assert os.path.isfile(pathconds_d_file),pathconds_d_file
    
    dom,_ = CF.Dom.get_dom(dom_file)
    logger.info("dom_file '{}': {}".format(dom_file,dom))
    
    st = time()
    pathconds_d = CM.vload(pathconds_d_file)
    logger.info("'{}': {} path conds ({}s)"
                .format(pathconds_d_file,len(pathconds_d),time()-st))

    args={'pathconds_d':pathconds_d}
    get_cov_f = lambda config: get_cov(config,args)
    return dom,get_cov_f,pathconds_d

def get_cov(config,args):
    if CM.__vdebug__:
        assert isinstance(config,CF.Config),config
        assert isinstance(args,dict) and 'pathconds_d' in args, args
        
    sids = set()        
    for cov,configs in args['pathconds_d'].itervalues():
        if any(config.hcontent.issuperset(c) for c in configs):
            for sid in cov:
                sids.add(sid)
    outps = []
    return sids,outps

def do_full(dom,pathconds_d,tmpdir,n=None):
    """
    Obtain interactions using Otter's pathconds
    """
    if CM.__vdebug__:
        assert n is None or 0 <= n <= len(pathconds_d), n
        assert isinstance(tmpdir,str) and os.path.isdir(tmpdir), tmpdir
        
        logger.warn("DEBUG MODE ON. Can be slow !")

    seed=0
    logger.info("seed: {} default, tmpdir: {}".format(seed,tmpdir))

    CF.DTrace.save_pre(seed,dom,tmpdir)
    if n:
        logger.info('select {} rand'.format(n))
        rs = random.sample(pathconds_d.values(),n)
    else:
        rs = pathconds_d.itervalues()

    cconfigs_d = CF.Configs_d()
    for covs,configs in rs:
        for c in configs:
            c = CF.Config(c)
            if c not in cconfigs_d:
                cconfigs_d[c]=set(covs)
            else:
                covs_ = cconfigs_d[c]
                for sid in covs:
                    covs_.add(sid)
            
    logger.info("use {} configs".format(len(cconfigs_d)))
    st = time()
    cores_d,configs_d,covs_d = CF.Cores_d(),CF.Configs_d(),CF.Covs_d()
    new_covs,new_cores = CF.Infer.infer_covs(
        cores_d,cconfigs_d,configs_d,covs_d,dom)
    pp_cores_d = cores_d.analyze(dom,covs_d)
    mcores_d = pp_cores_d.merge(show_detail=True)    
    itime_total = time() - st
    assert len(pp_cores_d) == len(covs_d), (len(pp_cores_d),len(covs_d))
    
    logger.info(DTrace.str_of_summary(
        0,1,itime_total,0,len(configs_d),len(pp_cores_d),tmpdir))

    dtrace = CF.DTrace(1,itime_total,0,
                       len(configs_d),len(covs_d),len(cores_d),
                       cconfigs_d,
                       new_covs,new_cores,
                       CF.SCore.mk_default(), #sel_core
                       cores_d)
    CF.DTrace.save_iter(1,dtrace,tmpdir)
    CF.DTrace.save_post(pp_cores_d,itime_total,tmpdir)
    
    return pp_cores_d,cores_d,configs_d,covs_d,dom