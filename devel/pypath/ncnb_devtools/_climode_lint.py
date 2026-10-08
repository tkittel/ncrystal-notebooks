#The rules of ruff for the code in the notebooks: only a few simple ones, since
#notebook code is not module code (e.g. packages may be imported for later
#exercises, and names redefined when exploring). Syntax errors, undefined
#names, invalid comparisons and misplaced statements, and the comparison idioms
#(e.g. "x is None" and "a not in b"):
LINT_NOTEBOOK_RULES = ( 'E9', 'F63', 'F7', 'F82',
                        'E711', 'E712', 'E713', 'E714', 'E721' )

def short_description():
    return 'Lint the Python code and the notebooks with ruff'

def main( parser ):
    parser.init( short_description() + """. The Python code in the repository
    (this tool and the utilities) is checked with the strict rules in
    ruff.toml, and the code in the notebooks with only a few simple rules (also
    run by "precommit"). Requires ruff (e.g. "pip install ruff").""" )
    parser.add_argument( '--fix', action = 'store_true',
                         help = """Let ruff fix what it can in the Python code
                         (not in the notebooks).""" )
    args = parser.parse_args()
    if not lint( fix = args.fix ):
        raise SystemExit(1)
    print('Lint OK')

def find_ruff():
    """The command for running ruff (as a list), or None if not available:
    the ruff command, or ruff as a module of the Python running the tool (e.g.
    when installed in a virtual environment which is not activated)."""
    import importlib.util
    import shutil
    import sys
    if shutil.which('ruff'):
        return [ 'ruff' ]
    if importlib.util.find_spec('ruff'):
        return [ sys.executable, '-m', 'ruff' ]
    return None

def lint( *, fix = False, notebooks = None ):
    """Lint the Python code and the notebooks (by default all), and return
    True if there were no problems."""
    import subprocess

    from .dirs import reporoot
    ruff = find_ruff()
    if not ruff:
        raise SystemExit('ERROR: ruff is needed for linting, also by'
                         ' "precommit" (install it with e.g. "pip install'
                         ' \'ruff>=0.16.10,<0.17\'")')
    print('Linting the Python code', flush = True)
    #(The notebooks are linted separately below, so they are always excluded
    #here, as in ruff.toml:)
    cmd = [ *ruff, 'check', '--quiet', '--color', 'never',
            '--output-format', 'concise', '--extend-exclude', 'notebooks' ]
    ok = subprocess.run( cmd + ( ['--fix'] if fix else [] ),
                         cwd = reporoot(), check = False ).returncode == 0
    print('Linting the notebooks', flush = True)
    return lint_notebooks( ruff, notebooks ) and ok

def lint_notebooks( ruff, notebooks = None ):
    """Lint the code in the notebooks with LINT_NOTEBOOK_RULES. The notebooks
    are expanded as for editing (so the generated setup code, e.g. "import
    NCrystal as NC", is included, and the cells are numbered as in the
    notebooks), and the messages refer to the notebooks in the repository."""
    import json
    import pathlib
    import subprocess
    import tempfile

    from .config import load_config
    from .expand import expand
    from .nbsettings import find_notebooks
    cfg = load_config()
    notebooks = notebooks if notebooks is not None else find_notebooks()
    with tempfile.TemporaryDirectory() as tmpdir:
        names = {}
        for nb in notebooks:
            if nb.settings is None:
                continue
            f = pathlib.Path(tmpdir) / f'{nb.shortkey}.ipynb'
            f.write_text( json.dumps( expand( nb, cfg, 'launch',
                                              generated_cell = False ) ),
                          encoding = 'utf-8' )
            names[f.name] = nb.relpath
        p = subprocess.run( [ *ruff, 'check', '--isolated', '--quiet',
                              '--color', 'never', '--output-format', 'concise',
                              '--select', ','.join(LINT_NOTEBOOK_RULES),
                              '--no-cache', '.' ],
                            cwd = tmpdir, capture_output = True, text = True,
                            check = False )
    out = p.stdout
    for name, relpath in names.items():
        out = out.replace( name, relpath )
    if out.strip():
        print( out.rstrip() )
    if p.returncode != 0 and not out.strip():
        print( p.stderr.rstrip() )
    return p.returncode == 0
