def short_description():
    return 'Run notebooks (as in CI), after the quick checks'

def main( parser ):
    parser.init( short_description() + """. Each notebook runs in a fresh
    directory with a fresh kernel, in an environment providing its
    requirements, and must run without errors and be convertible to HTML. By
    default all notebooks are run.""" )
    parser.add_argument( 'NOTEBOOK', nargs = '*',
                         help = 'Notebooks to run (shortkeys or paths).' )
    parser.add_argument( '--only-slow', action = 'store_true',
                         help = """Only run notebooks marked as slow in their
                         settings cells (the counterpart of --skip-slow, e.g.
                         for a separate CI job).""" )
    parser.add_argument( '--colab', action = 'store_true',
                         help = """Run the notebooks as on Google Colab: the
                         Colab versions of the notebooks (with their
                         installation cells, and the test parameters) run in
                         the current Python environment, without the tool
                         installing anything. This modifies the environment,
                         and is only possible in Google's Colab runtime image
                         (as in the colab workflow of the repository).
                         Notebooks needing conda are not supported yet.""" )
    parser.add_argument( '--write-selected', metavar = 'FILE',
                         help = """Only write the shortkeys of the selected
                         notebooks to this file (one per line), instead of
                         running them. With --colab, this is also possible
                         outside Google's Colab runtime image, e.g. for running
                         each notebook in its own fresh container from it (as in
                         the colab workflow).""" )
    parser.add_argument( '--select', choices = ('all','pip','conda'),
                         default = 'all',
                         help = """Only run notebooks which can be installed
                         with pip ("pip"), or only those needing conda
                         ("conda").""" )
    from .batch import add_batch_args
    add_batch_args( parser )
    args = parser.parse_args()
    if args.only_slow and args.skip_slow:
        parser.error('--only-slow and --skip-slow can not be combined')
    if args.colab and ( args.env != 'auto' or args.ncrystal_src
                        or args.fresh_envs or args.python ):
        parser.error('--colab can not be combined with --env, --ncrystal-src,'
                     ' --fresh-envs or --python')
    run_tests( args )

def run_tests( args ):
    import sys

    from .batch import (
        cleanup_workdir,
        limits_description,
        make_workdir,
        print_summary,
        quick_checks,
        run_batch,
    )
    from .config import load_config
    from .envsetup import conda_platform, env_kind, in_colab_image
    from .expand import Requirements
    from .nbsettings import select_notebooks
    cfg = load_config()
    if args.colab and not args.write_selected and not in_colab_image():
        raise SystemExit('ERROR: --colab is only possible in Google\'s Colab'
                         ' runtime image (the notebooks install their'
                         ' requirements into the current environment)')
    notebooks = quick_checks( cfg )
    jobs = []
    for nb in select_notebooks( args.NOTEBOOK, notebooks ):
        reqs = Requirements( nb.settings, cfg )
        if args.only_slow and not nb.settings.slow and not args.NOTEBOOK:
            continue
        if args.skip_slow and nb.settings.slow and not args.NOTEBOOK:
            print(f'Skipping {nb.shortkey} (slow)')
            continue
        if args.select == 'pip' and reqs.needs_conda:
            continue
        if args.select == 'conda' and not reqs.needs_conda:
            continue
        if args.colab:
            if reqs.needs_conda:
                #TODO: The Colab versions of these notebooks install conda with
                #condacolab, which restarts the kernel (nbclient would see a
                #crash):
                msg = ( f'{nb.shortkey} needs conda, which is not yet'
                        ' supported with --colab' )
                if args.NOTEBOOK:
                    raise SystemExit(f'ERROR: {msg}')
                print(f'Skipping {msg}')
                continue
            jobs.append( ( nb, 'colab' ) )
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
        #TEMPORARY: Building NCrystal plugins from source fails on Windows with
        #NCrystal 4.4.6 and earlier (NCrystal.dll is not found in the
        #temporary environment of pip's build isolation). Remove this when a
        #NCrystal release with the fix is out:
        srcplugins = reqs.source_plugins()
        if srcplugins and sys.platform == 'win32':
            msg = ( f'{nb.shortkey} needs plugins built from source'
                    f' ({", ".join(srcplugins)}), which currently fails on'
                    ' Windows' )
            if args.NOTEBOOK:
                raise SystemExit(f'ERROR: {msg}')
            print(f'Skipping {msg}')
            continue
        jobs.append( ( nb, kind ) )
    if not jobs:
        raise SystemExit('ERROR: No notebooks selected')
    if args.write_selected:
        import pathlib
        pathlib.Path(args.write_selected).write_text(
            ''.join( f'{nb.shortkey}\n' for nb, _ in jobs ),
            encoding = 'utf-8' )
        print(f'Wrote the {len(jobs)} selected notebooks to'
              f' {args.write_selected}')
        return
    target = 'colabtest' if args.colab else 'test'
    workdir = make_workdir( args )
    results = run_batch( jobs, args, cfg, workdir, target )
    nfail = print_summary( results, workdir,
                           limits_description( args, cfg, target ) )
    cleanup_workdir( args, workdir, nfail )
    if nfail:
        raise SystemExit(f'\nERROR: {nfail} of {len(results)} notebooks'
                         ' failed')
    n = len(results)
    print(f'\nAll {n} notebook{"s" if n != 1 else ""} OK')
