import config as CF

def prepare(prog):

    #dir_ = getpath('~/Src/Devel/iTree_stuff/expData/{}'.format(prog))
    dir_ = getpath('~/Dropbox/git/config/otter_exps/{}'.format(prog))
    dom_file = os.path.join(dir_,'possibleValues.txt')
    pathconds_d_file = os.path.join(dir_,'{}.tvn'.format('pathconds_d'))
    assert os.path.isfile(dom_file),dom_file
    assert os.path.isfile(pathconds_d_file),pathconds_d_file
    
    dom,_ = Dom.get_dom(dom_file)
    logger.info("dom_file '{}': {}".format(dom_file,dom))
    
    st = time()
    pathconds_d = CM.vload(pathconds_d_file)
    logger.info("'{}': {} path conds ({}s)"
                .format(pathconds_d_file,len(pathconds_d),time()-st))

    args={'pathconds_d':pathconds_d}
    get_cov = lambda config: get_cov_otter(config,args)
    return dom,get_cov,pathconds_d

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

def do_full(dom,pathconds_d,n=None):
    """
    Obtain interactions using Otter's pathconds
    """
    if CM.__vdebug__:
        assert n is None or 0 <= n <= len(pathconds_d), n
        logger.warn("DEBUG MODE ON. Can be slow !")

    if n:
        logger.info('select {} rand'.format(n))
        rs = random.sample(pathconds_d.values(),n)
    else:
        rs = pathconds_d.itervalues()

    cconfigs_d = Configs_d()
    for covs,configs in rs:
        for c in configs:
            c = Config(c)
            if c not in cconfigs_d:
                cconfigs_d[c]=set(covs)
            else:
                covs_ = cconfigs_d[c]
                for sid in covs:
                    covs_.add(sid)
            
    logger.info("infer interactions using {} configs"
                .format(len(cconfigs_d)))
    st = time()
    cores_d,configs_d,covs_d = Cores_d(),Configs_d(),Covs_d()
    _ = Inferrence.infer_covs(cores_d,cconfigs_d,configs_d,covs_d,dom)
    pp_cores_d = cores_d.analyze(covs_d,dom)
    pp_cores_d.show_analysis(dom)

    logger.info(Analysis.str_of_summary(
        0,0,time()-st,0,len(configs_d),len(pp_cores_d),'no tmpdir'))

    return pp_cores_d,cores_d,configs_d,covs_d,dom


otter_d = {"vsftpd":None,
           "ngircd":None}
