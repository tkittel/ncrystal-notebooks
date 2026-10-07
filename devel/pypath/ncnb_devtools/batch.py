"""Running a set of notebooks (shared by the test and site modes)."""

import pathlib
import shutil
import tempfile

def add_batch_args( parser ):
    from .envsetup import add_env_args
    add_env_args( parser )
    parser.add_argument( '-j', type = int, default = 1, metavar = 'N',
                         help = 'Number of notebooks to run in parallel.' )
    parser.add_argument( '--time-limit', type = int, metavar = 'SECONDS',
                         help = """Override the time limit for each notebook
                         (default: max_test_time or max_full_time from
                         notebook_settings.toml), e.g. for debugging.""" )
    parser.add_argument( '--workdir', metavar = 'DIR',
                         help = """Directory for run directories and logs
                         (default: a new temporary directory, removed when
                         done unless there were failures).""" )
    parser.add_argument( '--keep', action = 'store_true',
                         help = 'Keep the work directory.' )

def quick_checks( cfg ):
    from .nbsettings import find_notebooks
    from .checks import check_all, report
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

def time_limit( args, cfg, target ):
    if args.time_limit:
        return args.time_limit
    return cfg.max_test_time if target == 'test' else cfg.max_full_time

def run_batch( jobs, args, cfg, workdir, target ):
    """Run the notebooks in jobs (list of (notebook,envkind)), expanded for the
    target, and return a list of (notebook,RunResult)."""
    from concurrent.futures import ThreadPoolExecutor
    from .expand import expand
    from .envsetup import EnvSetup
    from .runner import prepare_rundir, run_notebook
    setup = EnvSetup( args, cfg, workdir )
    prepared = []
    for nb, kind in jobs:
        env = setup.env_for( nb, kind )
        nbfile = prepare_rundir( workdir / nb.shortkey, nb.path.name,
                                 expand( nb, cfg, target ) )
        prepared.append( ( nb, env, nbfile,
                           time_limit( args, cfg, target ) ) )

    def run( item ):
        nb, env, nbfile, limit = item
        print(f'Running {nb.shortkey} ({nb.relpath}) in {env.description}',
              flush = True)
        res = run_notebook( env, nbfile, limit,
                            workdir / f'{nb.shortkey}.log' )
        print(f'  {"OK" if res.ok else "FAILED"}: {nb.shortkey}'
              f' ({res.seconds:.0f} s)', flush = True)
        return nb, res

    with ThreadPoolExecutor( max_workers = max(1,args.j) ) as ex:
        return list( ex.map( run, prepared ) )

def print_summary( results, workdir, limit = None ):
    """Print summary, and return the number of failures."""
    print('\nSummary' + ( f' (time limit per notebook: {limit} s):'
                          if limit else ':' ))
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
