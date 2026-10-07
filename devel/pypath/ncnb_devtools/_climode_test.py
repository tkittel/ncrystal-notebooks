def short_description():
    return 'Run notebooks (as in CI), after the quick checks'

def main( parser ):
    parser.init( short_description() + """. Each notebook runs in a fresh
    directory with a fresh kernel, in an environment providing its
    requirements, and must run without errors and be convertible to HTML. By
    default all notebooks are run.""" )
    parser.add_argument( 'NOTEBOOK', nargs = '*',
                         help = 'Notebooks to run (shortkeys or paths).' )
    parser.add_argument( '--select', choices = ('all','pip','conda'),
                         default = 'all',
                         help = """Only run notebooks which can be installed
                         with pip ("pip"), or only those needing conda
                         ("conda").""" )
    from .batch import add_batch_args
    add_batch_args( parser )
    args = parser.parse_args()
    run_tests( args )

def run_tests( args ):
    from .config import load_config
    from .nbsettings import select_notebooks
    from .expand import Requirements
    from .envsetup import env_kind, conda_platform
    from .batch import ( time_limit, quick_checks, make_workdir, run_batch, print_summary,
                         cleanup_workdir )
    cfg = load_config()
    notebooks = quick_checks( cfg )
    jobs = []
    for nb in select_notebooks( args.NOTEBOOK, notebooks ):
        reqs = Requirements( nb.settings, cfg )
        if args.select == 'pip' and reqs.needs_conda:
            continue
        if args.select == 'conda' and not reqs.needs_conda:
            continue
        kind = env_kind( reqs, args.env )
        if kind is None:
            if args.NOTEBOOK:
                raise SystemExit(f'ERROR: {nb.shortkey} needs conda, and can'
                                 ' not run with --env=venv')
            print(f'Skipping {nb.shortkey} (needs conda)')
            continue
        unavail = ( reqs.unavailable_with_conda( conda_platform() )
                    if kind == 'conda' else [] )
        if unavail:
            msg = ( f'{nb.shortkey} needs {", ".join(unavail)}, which is not'
                    f' available with conda on {conda_platform()}' )
            if args.NOTEBOOK:
                raise SystemExit(f'ERROR: {msg}')
            print(f'Skipping {msg}')
            continue
        jobs.append( ( nb, kind ) )
    if not jobs:
        raise SystemExit('ERROR: No notebooks selected')
    workdir = make_workdir( args )
    results = run_batch( jobs, args, cfg, workdir, 'test' )
    nfail = print_summary( results, workdir,
                           time_limit( args, cfg, 'test' ) )
    cleanup_workdir( args, workdir, nfail )
    if nfail:
        raise SystemExit(f'\nERROR: {nfail} of {len(results)} notebooks'
                         ' failed')
    print(f'\nAll {len(results)} notebooks OK')
