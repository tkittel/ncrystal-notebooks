"""Running a set of notebooks (shared by the test and site modes)."""

import pathlib
import shutil
import tempfile


def add_batch_args( parser ):
    from .envsetup import add_env_args
    add_env_args( parser )
    parser.add_argument( '--skip-slow', action = 'store_true',
                         help = """Skip notebooks marked as slow in their
                         settings cells (unless given explicitly), e.g. while
                         debugging.""" )
    parser.add_argument( '-j', type = int, default = 1, metavar = 'N',
                         help = 'Number of notebooks to run in parallel.' )
    parser.add_argument( '--time-limit', type = int, metavar = 'SECONDS',
                         help = """Override the time limit for each notebook
                         (default: from notebook_settings.toml), e.g. for
                         debugging.""" )
    parser.add_argument( '--workdir', metavar = 'DIR',
                         help = """Directory for run directories and logs
                         (default: a new temporary directory, removed when
                         done unless there were failures).""" )
    parser.add_argument( '--keep', action = 'store_true',
                         help = 'Keep the work directory.' )

def quick_checks( cfg ):
    from .checks import check_all, report
    from .nbsettings import find_notebooks
    notebooks = find_notebooks()
    print('Running quick checks of all notebooks', flush = True)
    if not report( check_all( notebooks, cfg ) ):
        raise SystemExit('ERROR: Quick checks failed (see above)')
    return notebooks

def make_workdir( args ):
    if args.workdir:
        workdir = pathlib.Path(args.workdir).absolute()
        workdir.mkdir( parents = True, exist_ok = True )
    else:
        workdir = pathlib.Path(tempfile.mkdtemp(prefix='ncnotebookdevtool_'))
    print(f'Work directory: {workdir}', flush = True)
    return workdir

def cleanup_workdir( args, workdir, failed ):
    if failed or args.keep or args.workdir:
        print(f'\nWork directory kept: {workdir}')
    else:
        shutil.rmtree( workdir, ignore_errors = True )

def normal_time_limit( cfg, target ):
    """The time limit for notebooks not marked as slow (more on Windows, where
    e.g. compilation is slower)."""
    import sys
    normal = cfg.max_test_time if is_test(target) else cfg.max_full_time
    if sys.platform == 'win32':
        #(Whole seconds, as the notebooks are run with a time limit in whole
        #seconds, see _nbexec.py.)
        import math
        normal = math.ceil( normal * cfg.windows_time_factor )
    return normal

def is_test( target ):
    """Whether the target runs notebooks with their test parameters."""
    return target in ('test','colabtest')

def install_time( cfg, target ):
    """Extra time for notebooks installing their requirements themselves."""
    return cfg.colab_install_time if target == 'colabtest' else 0

def time_limits( args, cfg, target, slow ):
    """The maximum and minimum (or None) time for running a notebook."""
    if args.time_limit:
        return args.time_limit, None
    extra = install_time( cfg, target )
    normal = normal_time_limit( cfg, target ) + extra
    if not slow:
        return normal, None
    #Slow notebooks get more time, but full runs must also really be slow (not
    #checked in tests, where test-parameters can make them faster):
    if is_test(target):
        return cfg.max_test_time_slow + extra, None
    return cfg.max_full_time_slow, cfg.min_full_time_slow

def limits_description( args, cfg, target ):
    if args.time_limit:
        return f'{args.time_limit} s'
    t = is_test(target)
    extra = install_time( cfg, target )
    normal = f'{normal_time_limit( cfg, target ) + extra:g}'
    slow = ( cfg.max_test_time_slow if t else cfg.max_full_time_slow ) + extra
    if t:
        note = ( f' (including {extra} s for installation)' if extra else '' )
        return f'{normal} s, or {slow} s for slow notebooks{note}'
    return ( f'{normal} s, or {cfg.min_full_time_slow}-{slow} s for slow'
             ' notebooks' )

WARMUP_CODE = '''
for m in ('NCrystal','numpy','matplotlib.pyplot','ipykernel'):
    try:
        __import__(m)
    except ImportError:
        pass
'''

def run_batch( jobs, args, cfg, workdir, target ):
    """Run the notebooks in jobs (list of (notebook,envkind)), expanded for the
    target, and return a list of (notebook,RunResult)."""
    from concurrent.futures import ThreadPoolExecutor

    from .envsetup import EnvSetup
    from .expand import colab_restart_cell, expand
    from .runner import prepare_rundir, run_notebook
    setup = EnvSetup( args, cfg, workdir )
    prepared = []
    for nb, kind in jobs:
        env = setup.env_for( nb, kind )
        expanded = expand( nb, cfg, target )
        nbfile = prepare_rundir( workdir / nb.shortkey, nb.path.name,
                                 expanded )
        #(On Colab, the kernel restarts after installing conda:)
        restart_after = ( colab_restart_cell( expanded )
                          if target == 'colabtest' else None )
        prepared.append( ( nb, env, nbfile,
                           time_limits( args, cfg, target, nb.settings.slow ),
                           restart_after ) )
    #Warm up each environment, so one-time costs (e.g. building the font cache
    #of matplotlib, or the first imports of large packages on macOS) do not
    #count in the times of the notebooks:
    warmed = set()
    for _, env, _, _, _ in prepared:
        if str(env.python) not in warmed:
            warmed.add( str(env.python) )
            env.run( [ env.python, '-c', WARMUP_CODE ] )

    import threading
    lock = threading.Lock()
    counts = { 'started' : 0, 'done' : 0 }
    ntot = len(prepared)

    def run( item ):
        nb, env, nbfile, ( limit, minimum ), restart_after = item
        with lock:
            counts['started'] += 1
            print(f'Running ({counts["started"]}/{ntot}) {nb.shortkey}'
                  f' ({nb.relpath}) in {env.description}', flush = True)
        res = run_notebook( env, nbfile, limit,
                            workdir / f'{nb.shortkey}.log', restart_after )
        if res.ok and minimum is not None and res.seconds < minimum:
            res.ok = False
            res.message = ( f'The notebook is marked as slow, but ran in only'
                            f' {res.seconds:.0f} seconds (less than'
                            f' {minimum:g} seconds). Please remove "# slow:'
                            ' yes" from its settings cell.' )
        with lock:
            counts['done'] += 1
            print(f'  {"OK" if res.ok else "FAILED"}: {nb.shortkey}'
                  f' ({res.seconds:.0f} s) [{counts["done"]}/{ntot} done]',
                  flush = True)
        return nb, res

    with ThreadPoolExecutor( max_workers = max(1,args.j) ) as ex:
        return list( ex.map( run, prepared ) )

def print_summary( results, workdir, limits = None ):
    """Print summary, and return the number of failures."""
    print('\nSummary' + ( f' (time limits: {limits}):' if limits else ':' ))
    nfail = 0
    for nb, res in results:
        print(f'  {"OK    " if res.ok else "FAILED"} {res.seconds:6.0f} s'
              f'  {nb.shortkey:<14} {nb.relpath}')
        nfail += 0 if res.ok else 1
    for nb, res in results:
        if not res.ok:
            print(f'\n===== {nb.shortkey} failed (log: '
                  f'{workdir / (nb.shortkey + ".log")}):\n{res.message}')
    return nfail
