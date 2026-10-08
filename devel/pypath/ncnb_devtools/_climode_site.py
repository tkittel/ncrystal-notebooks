from .utils import print_msg


def short_description():
    return 'Run all notebooks and build the website'

def main( parser ):
    parser.init( short_description() + """. All notebooks are run (as in the
    "test" mode, but with setup code for the website) and turned into a Sphinx
    website, which also provides versions of the notebooks for download and for
    Google Colab. Give notebooks (shortkeys or paths) to build a website with
    just those, e.g. to quickly see how a new notebook will look.""" )
    parser.add_argument( 'NOTEBOOK', nargs = '*',
                         help = """Notebooks to include (shortkeys or paths;
                         default: all).""" )
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

SLOW_WARNING = ( 'This notebook takes a long time to run, so the website is'
                 ' currently built without running it, and its outputs are'
                 ' not shown. To see them, run it yourself: download it or'
                 ' open it in Google Colab with the links above.' )
FAILED_WARNING = ( 'This notebook failed when the website was built, so its'
                   ' outputs are not shown.' )

def build_site( args ):
    import json
    import pathlib

    from .batch import (
        cleanup_workdir,
        limits_description,
        make_workdir,
        print_summary,
        quick_checks,
        run_batch,
    )
    from .config import load_config
    from .envs import venv_env
    from .envsetup import conda_platform, env_kind
    from .expand import Requirements
    from .nbsettings import select_notebooks
    from .site import (
        SPHINX_PACKAGES,
        build_html,
        finalize_executed,
        links_markdown,
        write_sources,
    )
    cfg = load_config()
    notebooks = select_notebooks( args.NOTEBOOK, quick_checks( cfg ) )
    out = pathlib.Path(args.output).absolute()
    out.mkdir( parents = True, exist_ok = True )
    workdir = make_workdir( args )
    executed = {}
    warnings = {}
    nfail = 0
    if not args.no_execute:
        torun = notebooks
        if args.skip_slow and not args.NOTEBOOK:
            torun = [ nb for nb in notebooks if not nb.settings.slow ]
            for nb in notebooks:
                if nb.settings.slow:
                    print_msg(f'Skipping {nb.shortkey} (slow, shown'
                              ' unexecuted)')
                    warnings[nb.shortkey] = SLOW_WARNING
        jobs = [ ( nb, env_kind( Requirements( nb.settings, cfg ), args.env ) )
                 for nb in torun ]
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
                           limits_description( args, cfg, 'site' ) )
        if nfail and not args.allow_failures:
            cleanup_workdir( args, workdir, nfail )
            raise SystemExit(f'\nERROR: {nfail} notebooks failed (use'
                             ' --allow-failures to build the website anyway)')
        for nb, res in results:
            if not res.ok:
                warnings[nb.settings.shortkey] = FAILED_WARNING
            if res.ok:
                page = json.loads( res.output.read_text( encoding = 'utf-8' ) )
                page = finalize_executed( page )
                #Add the links after the title cell:
                page['cells'].insert( 1, { 'cell_type' : 'markdown',
                                           'id' : 'ncnb-links',
                                           'metadata' : {},
                                           'source' : links_markdown(nb,cfg) } )
                executed[nb.settings.shortkey] = page
    print_msg('Building the website', flush = True)
    write_sources( notebooks, executed, cfg, out / 'src', out / 'colab',
                   warnings )
    env = venv_env( SPHINX_PACKAGES, python = args.python,
                    log = workdir / 'environments.log' )
    build_html( env, out / 'src', out / 'html', workdir / 'sphinx.log' )
    cleanup_workdir( args, workdir, nfail )
    html = out / 'html'
    print_msg(f'\nWebsite built in {html} (open {html / "index.html"}'
              ' in a browser)')
