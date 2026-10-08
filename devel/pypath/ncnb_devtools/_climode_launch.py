from .utils import print_msg


def short_description():
    return ( 'Open a notebook in Jupyter Lab, in a fresh directory and'
             ' environment' )

def main( parser ):
    parser.init( short_description() + """. The notebook (given by shortkey or
    path) is copied to a fresh directory, with its settings cell expanded with
    setup code, and opened in Jupyter Lab running in an environment providing
    its requirements. When Jupyter Lab is stopped (Ctrl-C), the edited notebook
    is written back in canonical form (with the settings cell restored), and
    the previous version is kept as NOTEBOOK.ipynb.orig.""" )
    parser.add_argument( 'NOTEBOOK', help = 'Notebook (shortkey or path).' )
    from .envsetup import add_env_args
    add_env_args( parser )
    parser.add_argument( '--workdir', metavar = 'DIR',
                         help = """Directory in which to run (default: a new
                         temporary directory). Its contents are deleted.""" )
    parser.add_argument( '--no-browser', action = 'store_true',
                         help = 'Do not open a browser (just print the URL).' )
    args = parser.parse_args()
    launch( args )

def launch( args ):
    import os
    import pathlib
    import shutil
    import subprocess
    import tempfile

    from .config import load_config
    from .envs import pip_install
    from .envsetup import EnvSetup, env_kind
    from .expand import Requirements, collapse, expand, generated_cell_source
    from .nbfile import canonical_text, load
    from .nbsettings import find_notebooks, select_notebooks
    from .runner import prepare_rundir, write_kernelspec

    cfg = load_config()
    nb = select_notebooks( [args.NOTEBOOK], find_notebooks() )[0]
    if nb.settings is None:
        raise SystemExit(f'ERROR: {nb.relpath}: {nb.error}')
    reqs = Requirements( nb.settings, cfg )
    kind = env_kind( reqs, args.env )
    if kind is None:
        raise SystemExit(f'ERROR: {nb.shortkey} needs conda')
    base = pathlib.Path( args.workdir or tempfile.mkdtemp(
        prefix = f'ncnotebookdevtool_{nb.shortkey}_' ) ).absolute()
    if args.workdir and base.exists():
        shutil.rmtree(base)
    base.mkdir( parents = True, exist_ok = True )
    env = EnvSetup( args, cfg, base / 'setup' ).env_for( nb, kind )
    #Jupyter Lab is only installed when needed:
    if env.missing_modules(['jupyterlab']):
        print_msg('Installing jupyterlab in the environment', flush = True)
        pip_install( env, ['jupyterlab'] )
    rundir = base / nb.shortkey
    expanded = expand( nb, cfg, 'launch' )
    nbfile = prepare_rundir( rundir, nb.path.name, expanded )
    jdatadir = base / 'jupyterdata'
    write_kernelspec( env, jdatadir )
    environ = env.environ()
    environ['JUPYTER_DATA_DIR'] = str(jdatadir)
    environ['JUPYTER_PATH'] = os.pathsep.join( [ str(jdatadir),
                                                 environ['JUPYTER_PATH'] ] )
    original = nb.path.read_text( encoding = 'utf-8' )
    print_msg(f'\nOpening {nb.relpath} in Jupyter Lab (in {rundir}).'
              '\nStop Jupyter Lab with Ctrl-C when done, to save the notebook'
              ' back into the repository.\n', flush = True)
    #The browser opens the address of the notebook in Jupyter Lab directly, not
    #a redirect file in the (temporary) Jupyter data directory, which browsers
    #with their own /tmp (e.g. snap packages on Ubuntu) can not open:
    import urllib.parse
    cmd = [ str(env.python), '-m', 'jupyterlab',
            '--ServerApp.use_redirect_file=False',
            '--LabApp.default_url=/lab/tree/'
            + urllib.parse.quote(nbfile.name) ]
    if args.no_browser:
        cmd.append('--no-browser')
    proc = subprocess.Popen( cmd, cwd = rundir, env = environ )
    try:
        proc.wait()
    except KeyboardInterrupt:
        #Jupyter Lab asks for confirmation after Ctrl-C, so shut it down
        #explicitly (SIGTERM is a clean shutdown):
        try:
            proc.terminate()
            proc.wait( timeout = 30 )
        except (subprocess.TimeoutExpired, KeyboardInterrupt):
            proc.kill()
            proc.wait()

    #Save the edited notebook back in canonical form:
    edited = load( nbfile )
    gensrc = generated_cell_source( edited )
    if gensrc is not None and gensrc != generated_cell_source( expanded ):
        print_msg('\nWARNING: Your changes to the cell with generated code were'
                  ' discarded (to change the setup, edit the settings cell).')
    collapse( edited )
    text = canonical_text( edited )
    if text == original:
        print_msg(f'\nNo changes to {nb.relpath}')
    else:
        if nb.path.read_text( encoding = 'utf-8' ) != original:
            raise SystemExit(f'\nERROR: {nb.relpath} was modified while the'
                             f' notebook was open. Your edited version is in'
                             f' {nbfile} (not saved back).')
        orig = nb.path.with_name( nb.path.name + '.orig' )
        orig.write_text( original, encoding = 'utf-8' )
        nb.path.write_text( text, encoding = 'utf-8' )
        print_msg(f'\nSaved changes to {nb.relpath} (previous version kept in'
                  f' {orig.relative_to(nb.path.parent.parent)})')
    if not args.workdir:
        shutil.rmtree( base, ignore_errors = True )
