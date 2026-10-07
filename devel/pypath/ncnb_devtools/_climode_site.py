def short_description():
    return 'Run all notebooks and build the website'

def main( parser ):
    parser.init( short_description() + """. All notebooks are run (as in the
    "test" mode, but with setup code for the website) and turned into a Sphinx
    website, which also provides versions of the notebooks for download and for
    Google Colab.""" )
    from .batch import add_batch_args
    add_batch_args( parser )
    parser.add_argument( '-o', '--output', metavar = 'DIR', required = True,
                         help = """Output directory (the website is put in
                         DIR/html, and the notebooks for Google Colab in
                         DIR/colab).""" )
    parser.add_argument( '--no-execute', action = 'store_true',
                         help = """Do not run the notebooks (quick builds,
                         e.g. when working on the website itself).""" )
    parser.add_argument( '--allow-failures', action = 'store_true',
                         help = """Build the website even if notebooks fail
                         (they are then shown unexecuted).""" )
    args = parser.parse_args()
    build_site( args )

def build_site( args ):
    import json
    import pathlib
    from .config import load_config
    from .expand import Requirements
    from .envsetup import env_kind, conda_platform
    from .envs import venv_env
    from .batch import ( time_limit, quick_checks, make_workdir, run_batch, print_summary,
                         cleanup_workdir )
    from .site import ( write_sources, build_html, finalize_executed,
                        links_markdown, SPHINX_PACKAGES )
    cfg = load_config()
    notebooks = quick_checks( cfg )
    out = pathlib.Path(args.output).absolute()
    out.mkdir( parents = True, exist_ok = True )
    workdir = make_workdir( args )
    executed = {}
    nfail = 0
    if not args.no_execute:
        jobs = [ ( nb, env_kind( Requirements( nb.settings, cfg ), args.env ) )
                 for nb in notebooks ]
        skipped = [ nb.shortkey for nb, k in jobs if k is None ]
        if skipped:
            raise SystemExit('ERROR: Notebooks needing conda can not be run'
                             f' with --env=venv: {" ".join(skipped)}')
        unavail = [ nb.shortkey for nb, k in jobs if k == 'conda' and
                    Requirements( nb.settings, cfg ).unavailable_with_conda(
                        conda_platform() ) ]
        if unavail:
            raise SystemExit('ERROR: Notebooks with requirements not available'
                             f' with conda on {conda_platform()}:'
                             f' {" ".join(unavail)}')
        results = run_batch( jobs, args, cfg, workdir, 'site' )
        nfail = print_summary( results, workdir,
                           time_limit( args, cfg, 'site' ) )
        if nfail and not args.allow_failures:
            cleanup_workdir( args, workdir, nfail )
            raise SystemExit(f'\nERROR: {nfail} notebooks failed (use'
                             ' --allow-failures to build the website anyway)')
        for nb, res in results:
            if res.ok:
                page = json.loads( res.output.read_text() )
                page = finalize_executed( page )
                #Add the links after the title cell:
                page['cells'].insert( 1, { 'cell_type' : 'markdown',
                                           'id' : 'ncnb-links',
                                           'metadata' : {},
                                           'source' : links_markdown(nb,cfg) } )
                executed[nb.settings.shortkey] = page
    print('Building the website', flush = True)
    write_sources( notebooks, executed, cfg, out / 'src', out / 'colab' )
    env = venv_env( SPHINX_PACKAGES, python = args.python,
                    log = workdir / 'environments.log' )
    build_html( env, out / 'src', out / 'html', workdir / 'sphinx.log' )
    cleanup_workdir( args, workdir, nfail )
    print(f'\nWebsite built in {out / "html"} (open {out / "html" / "index.html"}'
          ' in a browser)')
