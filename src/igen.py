import argparse
import tempfile
import os.path
from time import time
import vu_common as CM
import config_common as CC

def get_sids(inp):
    """
    Parse statements from the inp string, 
    e.g., "f1.c:5 f2.c:15" or "path/to/file" that contains statements
    """
    assert inp is None or isinstance(inp, str), inpt
    
    if not inp:
        return None
    
    inp = inp.strip()
    sids = frozenset(inp.split())
    if len(sids) == 1:
        sid_file = list(sids)[0]
        if os.path.isfile(sid_file):
            #parse sids from file
            lines = CM.iread_strip(sid_file)
            sids = []
            for l in lines:
                sids_ = [s.strip() for s in l.split(',')]
                sids.extend(sids_)
            sids = frozenset(sids)

    return sids if sids else None

def check_range(v, min_n=None, max_n=None):
    v = int(v)
    if min_n and v < min_n:
        raise argparse.ArgumentTypeError(
            "must be >= {} (inp: {})".format(min_n, v))
    if max_n and v > max_n:
        raise argparse.ArgumentTypeError(
            "must be <= {} (inpt: {})".format(max_n, v))
    return v

def detect_file(file1, file2, ext):
    """
    detect file2 based on file1
    """
    if file2:
        return CM.getpath(file2)
    else:
        #file1.orig_ext => file1.ext
        file1 = CM.getpath(file1)
        dir_ = os.path.dirname(file1)
        name_ = CM.file_basename(file1)
        file2 = os.path.join(dir_, name_ + ext)
    return file2
    
def get_run_f(prog, args, logger):
    """
    Ret f that takes inputs seed, tmpdir 
    and call appropriate iGen function on those inputs
    """
    sids = get_sids(args.sids)
    
    import igen_alg as IA    
    import get_cov_otter as Otter
    if prog in Otter.db:
        dom, get_cov_f, pathconds_d = Otter.prepare(prog, IA.Dom.get_dom)
        igen = IA.IGen(dom, get_cov_f, sids=sids)

        if args.cmp_rand:
            #TODO: test this 
            _f = lambda seed,tdir,rand_n: igen.go_rand(
                rand_n=rand_n, seed=seed, tmpdir=tdir)
        elif args.do_full:
            if args.rand_n:
                _f = lambda _,tdir: Otter.do_full(
                    dom, pathconds_d, tmpdir=tdir, n=args.rand_n)
            else:
                _f = lambda _,tdir: Otter.do_full(
                    dom, pathconds_d, tmpdir=tdir, n=None)
                
        elif args.rand_n is None:
            _f = lambda seed,tdir: igen.go(seed=seed, tmpdir=tdir)
        else:
            _f = lambda seed,tdir: igen.go_rand(
                rand_n=args.rand_n, seed=seed, tmpdir=tdir)
    else:        
        if args.dom_file:
            #general way to run prog using dom_file/runscript
            dom_file = CM.getpath(args.dom_file)
            dom, default_configs = IA.Dom.get_dom(dom_file)
            run_script = detect_file(dom_file, args.run_script, ".run")
            import get_cov
            get_cov_f = lambda config: get_cov.runscript_get_cov(
                config, run_script)
        else:
            import igen_settings
            import get_cov_coreutils as Coreutils            
            dom, default_configs, get_cov_f = Coreutils.prepare(
                prog,
                IA.Dom.get_dom,
                igen_settings.coreutils_main_dir,
                igen_settings.coreutils_doms_dir,
                do_perl=args.do_perl)

        if default_configs:
            econfigs = [(c, None) for c in default_configs]
        else:
            econfigs = []
            
        igen = IA.IGen(dom, get_cov_f, sids=sids)            
        if sids:
            ext = ".c.011t.cfg.preds"
            if args.dom_file:
                cfg_file = detect_file(args.dom_file, args.cfg, ext)
            else:
                #coreutils
                cfg_file = CM.getpath(os.path.join(
                    igen_settings.coreutils_main_dir,
                    'coreutils','obj-gcov', 'src', prog + ext))
            if args.no_ga:
                _f =  lambda seed, tdir: igen.go(seed=seed, tmpdir=tdir)
            else:
                import cfg as CFG
                from ec_alg import EC
                cfg = CFG.CFG.mk_from_lines(CM.iread_strip(cfg_file))
                ec = EC(dom, cfg, get_cov_f)
                def _f(seed, tdir):
                    is_success, _, configs_d = ec.go(
                        seed=seed, sids=sids, econfigs=default_configs,
                        tmpdir=tdir)
                    econfigs.extend(configs_d.items())
                    if not args.only_ga and is_success:
                        return igen.go(
                            seed=seed,econfigs=econfigs, tmpdir=tdir)
                    else:
                        return None
            
        elif args.cmp_rand:
            _f = lambda seed, tdir, rand_n: igen.go_rand(
                rand_n=rand_n, seed=seed, econfigs=econfigs, tmpdir=tdir)
        elif args.do_full:
            _f = lambda _,tdir: igen.go_full(tmpdir=tdir)
        elif args.rand_n is None:
            _f = lambda seed, tdir: igen.go(seed=seed, econfigs=econfigs, tmpdir=tdir)
        else:
            _f = lambda seed, tdir: igen.go_rand(
                rand_n=args.rand_n, seed=seed, econfigs=econfigs, tmpdir=tdir)

    logger.debug("dom:\n{}".format(dom))
    return _f, get_cov_f


if __name__ == "__main__":

    igen_file = CM.getpath(__file__)
    igen_name = os.path.basename(igen_file)
    igen_dir = os.path.dirname(igen_file)
        
    aparser = argparse.ArgumentParser("iGen (dynamic interaction generator)")
    aparser.add_argument("inp", help="inp", nargs='?') 
    
    #0 Error #1 Warn #2 Info #3 Debug #4 Detail
    aparser.add_argument("--logger_level", "-logger_level",
                         help="set logger info",
                         type=int, 
                         choices=range(5),
                         default = 4)    

    aparser.add_argument("--seed", "-seed",
                         type=float,
                         help="use this seed")

    aparser.add_argument("--rand_n", "-rand_n", 
                         type=lambda v:check_range(v, min_n=1),
                         help="rand_n is an integer")

    aparser.add_argument("--do_full", "-do_full",
                         help="use all possible configs",
                         action="store_true")

    aparser.add_argument("--noshow_cov", "-noshow_cov",
                         help="show coverage info",
                         action="store_true")

    aparser.add_argument("--analyze_outps", "-analyze_outps",
                         help="analyze outputs instead of coverage",
                         action="store_true")

    aparser.add_argument("--allows_known_errors", "-allows_known_errors",
                         help="allows for potentially no coverage exec",
                         action="store_true")
    
    aparser.add_argument("--benchmark", "-benchmark",
                         type=lambda v: check_range(v, min_n=1),
                         default=1,
                         help="run benchmark program n times")

    aparser.add_argument("--dom_file", "-dom_file",
                         help="file containing config domains",
                         action="store")

    aparser.add_argument("--run_script", "-run_script",
                         help="a script to obtain the program's coverage",
                         action="store")
    
    aparser.add_argument("--do_perl", "-do_perl",
                         help="do coretutils written in Perl",
                         action="store_true")

    aparser.add_argument("--sids", "-sids",
                         help="find interactions for sids",
                         action="store")
    
    aparser.add_argument("--cfg", "-cfg",
                         help="file containing predecessors from cfg",
                         action="store")

    aparser.add_argument("--only_ga", "-only_ga",
                         help="don't find interactions",
                         default=False,
                         action="store_true")

    aparser.add_argument("--no_ga", "-no_ga",
                         help="don't find interactions",
                         default=False,
                         action="store_true")
    
    #replay options
    aparser.add_argument("--show_iters", "-show_iters",
                         help="for use with analysis, show stats of all iters",
                         action="store_true")

    aparser.add_argument("--do_min_configs", "-do_min_configs",
                         help=("for use with analysis, "
                               "compute a set of min configs"),
                         action="store",
                         nargs='?',
                         const='use_existing',
                         default=None,
                         type=str)

    aparser.add_argument("--cmp_rand", "-cmp_rand",
                         help=("for use with analysis, "
                               "cmp results against rand configs"),
                         action="store",
                         default=None,
                         type=str)
    
    aparser.add_argument("--cmp_gt", "-cmp_gt",
                         help=("for use with analysis, "
                               "cmp results against ground truth"),
                         action="store",
                         default=None,
                         type=str)

    args = aparser.parse_args()
    CC.logger_level = args.logger_level
    logger = CM.VLog(igen_name)
    logger.level = CC.logger_level
    if __debug__:
        logger.warn("DEBUG MODE ON. Can be slow !")    
    
    if args.allows_known_errors:
        CC.allows_known_errors = True
    if args.noshow_cov:
        CC.show_cov = False
    if args.analyze_outps:
        CC.analyze_outps = True
    seed = round(time(), 2) if args.seed is None else float(args.seed)
    
    from igen_settings import tmp_dir
        
    # two main modes: 1. run iGen to find interactions and
    # 2. run Analysis to analyze iGen's generated files    
    analysis_f = None
    if args.inp and os.path.isdir(args.inp):
        from igen_analysis import Analysis
        is_run_dir = Analysis.is_run_dir(args.inp)
        if is_run_dir is not None:
            if is_run_dir:
                analysis_f = Analysis.replay
            else:
                analysis_f = Analysis.replay_dirs

    if analysis_f is None: #run iGen
        prog = args.inp
        _f, get_cov_f = get_run_f(prog, args, logger)

        prog_name = prog if prog else 'noname'
        prefix = "igen_{}_{}_{}_".format(
            args.benchmark,
            'full' if args.do_full else 'normal',
            prog_name)
        tdir = tempfile.mkdtemp(dir=tmp_dir, prefix=prefix)

        logger.debug("* benchmark '{}', {} runs, seed {}, results '{}'"
                     .format(prog_name, args.benchmark, seed, tdir))
        st = time()
        for i in range(args.benchmark):        
            st_ = time()
            seed_ = seed + i
            tdir_ = tempfile.mkdtemp(dir=tdir, prefix="run{}_".format(i))
            logger.debug("*run {}/{}".format(i+1, args.benchmark))
            _ = _f(seed_, tdir_)
            logger.debug("*run {}, seed {}, time {}s, '{}'".format(
                i + 1, seed_, time() - st_, tdir_))

        logger.info("** done {} runs, seed {}, time {}, results '{}'"
                    .format(args.benchmark, seed, time() - st, tdir))
                            
    else: #run analysis
        do_min_configs = args.do_min_configs  
        if do_min_configs and (do_min_configs != 'use_existing' or args.dom_file):
            _,get_cov_f = get_run_f(do_min_configs, args, logger)
            do_min_configs = get_cov_f

        cmp_rand = args.cmp_rand
        if cmp_rand:
            _f, _ = get_run_f(cmp_rand, args, logger)
            tdir = tempfile.mkdtemp(dir=tmp_dir,
                                    prefix=cmp_rand + "igen_cmp_rand")
            cmp_rand = lambda rand_n: _f(seed, tdir, rand_n)

        analysis_f(args.inp,
                   show_iters=args.show_iters,
                   do_min_configs=do_min_configs,
                   cmp_gt=args.cmp_gt,
                   cmp_rand=cmp_rand)
