"""Environments for running notebooks.

A "base" environment provides the requirements of a notebook. It is either a
venv (pip), a conda environment, or the current environment. Venv and conda
environments are created by the tool and cached (one per distinct set of
packages), with all conda environments sharing the same package cache (so
packages are hardlinked rather than copied).

On top of the base environment, an "overlay" venv can be created for a
particular run. It sees all packages of the base environment (via a .pth
file), and is used for installing packages which must not end up in the
cached environments or in the current environment: local packages from this
repository (e.g. the notebook utilities), NCrystal built from a local clone
of the NCrystal repository, and (in the current environment) anything
missing.

Conda environments are used as if activated (with environment variables set
by their activation scripts, e.g. for compilers), as captured with "conda run".
"""

import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys

from .dirs import cache_dir, reporoot

#Packages needed for running notebooks with nbclient (and for checking that
#they can be converted to HTML):
EXEC_PIP_PACKAGES = [ 'nbclient', 'ipykernel', 'nbformat', 'nbconvert' ]
EXEC_CONDA_PACKAGES = [ 'nbclient', 'ipykernel', 'nbformat', 'nbconvert',
                        'pip' ]
#Modules to check for in the current environment:
EXEC_MODULES = { 'nbclient' : 'nbclient', 'ipykernel' : 'ipykernel',
                 'nbformat' : 'nbformat', 'nbconvert' : 'nbconvert' }

_complete_marker = '.ncnotebookdevtool_complete'

_is_windows = ( sys.platform == 'win32' )

def _venv_layout( d ):
    """The Python and the directories with executables of a venv."""
    if _is_windows:
        return d / 'Scripts' / 'python.exe', [ d / 'Scripts' ]
    return d / 'bin' / 'python', [ d / 'bin' ]

def _conda_layout( d ):
    """The Python and the directories with executables of a conda env."""
    if _is_windows:
        return d / 'python.exe', [ d, d / 'Library' / 'mingw-w64' / 'bin',
                                   d / 'Library' / 'usr' / 'bin',
                                   d / 'Library' / 'bin', d / 'Scripts',
                                   d / 'bin' ]
    return d / 'bin' / 'python', [ d / 'bin' ]

class EnvError(RuntimeError):
    pass

#Time limit for commands (e.g. installations). Installations should take at
#most a few minutes, unless something is compiled from source unexpectedly:
COMMAND_TIME_LIMIT = 1200

def _run( cmd, *, env = None, log = None, cwd = None ):
    """Run a command, failing with the output if it fails."""
    try:
        p = subprocess.run( [str(e) for e in cmd], env = env, cwd = cwd,
                            stdout = subprocess.PIPE,
                            stderr = subprocess.STDOUT, text = True,
                            encoding = 'utf-8', errors = 'replace',
                            timeout = COMMAND_TIME_LIMIT )
    except subprocess.TimeoutExpired as e:
        out = e.stdout or ''
        out = out.decode('utf-8','replace') if isinstance(out,bytes) else out
        if log is not None:
            with open(log,'a',encoding='utf-8') as fh:
                fh.write('$> ' + ' '.join(str(e) for e in cmd) + '\n' + out)
        raise EnvError( f'Command took more than {COMMAND_TIME_LIMIT} seconds'
                        ' (perhaps something was compiled from source): '
                        + ' '.join(str(e) for e in cmd) + '\n' + out[-3000:] )
    if log is not None:
        with open(log,'a',encoding='utf-8') as fh:
            fh.write('$> ' + ' '.join(str(e) for e in cmd) + '\n')
            fh.write(p.stdout)
    if p.returncode != 0:
        raise EnvError( 'Command failed: ' + ' '.join(str(e) for e in cmd)
                        + '\n' + p.stdout[-3000:] )
    return p.stdout

def find_conda_tool():
    for name in ('mamba','micromamba','conda'):
        t = shutil.which(name)
        if t:
            return pathlib.Path(t)
    raise EnvError('No conda tool (mamba, micromamba or conda) found')

class Env:
    """An environment in which notebooks can run."""

    def __init__( self, python, bindirs, description, conda_prefix = None,
                  jupyter_paths = (), activated = None ):
        self.python = pathlib.Path(python)
        self.bindirs = [ pathlib.Path(d) for d in bindirs ]
        #Jupyter data directories (e.g. with nbconvert templates) of the
        #environment and, for overlays, of the base environment:
        self.jupyter_paths = [ pathlib.Path(d) for d in jupyter_paths ]
        self.description = description
        self.conda_prefix = conda_prefix
        #Environment variables of the activated conda environment (None for
        #other environments):
        self.activated = activated

    def environ( self ):
        """Environment variables for processes in this environment."""
        env = dict( self.activated or os.environ )
        env['PATH'] = os.pathsep.join( [ str(d) for d in self.bindirs ]
                                       + [ env.get('PATH','') ] )
        #Output of Python processes (e.g. pip) is read as UTF-8:
        env['PYTHONIOENCODING'] = 'utf-8'
        #Never compile the optional C++ extension of endf-parserpy, which can
        #take very long when no binary wheel is used (cf.
        #https://github.com/IAEA-NDS/endf-parserpy/issues/42):
        env.setdefault( 'INSTALL_ENDF_PARSERPY_CPP', 'no' )
        for k in ('PYTHONPATH','PYTHONHOME','VIRTUAL_ENV'):
            env.pop(k,None)
        if self.conda_prefix:
            env['CONDA_PREFIX'] = str(self.conda_prefix)
        #Avoid using kernels, configuration and data from the user's Jupyter
        #installation:
        jdir = cache_dir() / 'jupyter_isolated'
        jdir.mkdir( parents = True, exist_ok = True )
        env['JUPYTER_CONFIG_DIR'] = str(jdir / 'config')
        env['JUPYTER_DATA_DIR'] = str(jdir / 'data')
        env['JUPYTER_PLATFORM_DIRS'] = '1'
        env['JUPYTER_PATH'] = os.pathsep.join( str(d) for d in
                                               self.jupyter_paths )
        env['MPLBACKEND'] = 'agg'
        #Cache for large data downloaded by notebooks (see the
        #ncrystal_notebook_utilities package):
        env.setdefault( 'NCRYSTAL_NOTEBOOK_DATA_CACHE',
                        str( cache_dir() / 'data' ) )
        return env

    def run( self, cmd, **kwargs ):
        return _run( cmd, env = self.environ(), **kwargs )

    def python_output( self, code ):
        return _run( [ self.python, '-c', code ], env = self.environ() ).strip()

    def missing_modules( self, modules ):
        code = ( 'import importlib.util as u;'
                 f'print(" ".join(m for m in {list(modules)!r}'
                 ' if u.find_spec(m) is None))' )
        return self.python_output(code).split()

def _key( *data ):
    return hashlib.sha256( json.dumps(data,sort_keys=True).encode()
                           ).hexdigest()[:16]

def _envs_dir():
    d = cache_dir() / 'envs'
    d.mkdir( parents = True, exist_ok = True )
    return d

def venv_env( pip_packages, *, python = None, fresh = False, log = None ):
    """Cached venv with the given packages."""
    python = pathlib.Path( python or sys.executable )
    pyver = _run( [ python, '-c', 'import sys;print(sys.version)' ] ).strip()
    pkgs = sorted(set( pip_packages + EXEC_PIP_PACKAGES ))
    d = _envs_dir() / ( 'venv-' + _key( 'venv', str(python), pyver, pkgs ) )
    env = Env( *_venv_layout(d), f'venv {d.name}',
               jupyter_paths = [ d / 'share' / 'jupyter' ] )
    if fresh or not ( d / _complete_marker ).exists():
        if d.exists():
            shutil.rmtree(d)
        print(f'Creating environment {d.name} (pip: {" ".join(pkgs)})',
              flush = True)
        _run( [ python, '-m', 'venv', d ], log = log )
        env.run( [ env.python, '-m', 'pip', 'install', '-q', '--upgrade',
                   'pip' ], log = log )
        env.run( [ env.python, '-m', 'pip', 'install', '-q' ] + pkgs,
                 log = log )
        ( d / _complete_marker ).write_text( ' '.join(pkgs)+'\n',
                                             encoding = 'utf-8' )
    return env

def conda_env( conda_packages, pip_packages, *, fresh = False, log = None ):
    """Cached conda environment with the given packages (from conda-forge),
    and the given extra packages installed with pip."""
    cpkgs = sorted(set( conda_packages + EXEC_CONDA_PACKAGES + ['python'] ))
    ppkgs = sorted(set( pip_packages ))
    d = _envs_dir() / ( 'conda-' + _key( 'conda', cpkgs, ppkgs ) )
    tool = find_conda_tool()
    python, bindirs = _conda_layout(d)
    env = Env( python, bindirs, f'conda {d.name}',
               conda_prefix = d, jupyter_paths = [ d / 'share' / 'jupyter' ] )
    if fresh or not ( d / _complete_marker ).exists():
        if d.exists():
            shutil.rmtree(d)
        print(f'Creating environment {d.name} (conda: {" ".join(cpkgs)}'
              + ( f'; pip: {" ".join(ppkgs)}' if ppkgs else '' ) + ')',
              flush = True)
        cenv = dict(os.environ)
        #Shared package cache, so files are hardlinked between environments:
        pkgsdir = cache_dir() / 'conda-pkgs'
        pkgsdir.mkdir( parents = True, exist_ok = True )
        cenv['CONDA_PKGS_DIRS'] = str(pkgsdir)
        _run( [ tool, 'create', '-y', '-p', d, '--override-channels',
                '-c', 'conda-forge' ] + cpkgs, env = cenv, log = log )
        if ppkgs:
            env.run( [ env.python, '-m', 'pip', 'install', '-q' ] + ppkgs,
                     log = log )
        ( d / _complete_marker ).write_text( ' '.join(cpkgs+ppkgs)+'\n',
                                             encoding = 'utf-8' )
    env.activated = activated_environ( tool, d, python )
    return env

def activated_environ( tool, prefix, python ):
    """The environment variables in the activated conda environment."""
    out = _run( [ tool, 'run', '-p', prefix, python, '-c',
                  'import os,json;print("@@@"+json.dumps(dict(os.environ)))' ] )
    for line in out.splitlines():
        if line.startswith('@@@'):
            return json.loads(line[3:])
    raise EnvError(f'Could not get the environment of {prefix}:\n{out}')

def current_env():
    """The environment of the Python running this tool."""
    python = pathlib.Path(sys.executable)
    bindirs = [ python.parent ]
    if _is_windows and ( python.parent / 'Scripts' ).is_dir():
        bindirs.append( python.parent / 'Scripts' )
    prefix = os.environ.get('CONDA_PREFIX')
    return Env( python, bindirs, f'current environment ({sys.prefix})',
                conda_prefix = prefix,
                jupyter_paths = [ pathlib.Path(sys.prefix)/'share'/'jupyter' ] )

def overlay_env( base, path, *, log = None ):
    """Create an overlay venv at path on top of the base environment."""
    if path.exists():
        shutil.rmtree(path)
    path.parent.mkdir( parents = True, exist_ok = True )
    _run( [ base.python, '-m', 'venv', path ], env = base.environ(), log = log )
    python, bindirs = _venv_layout(path)
    ov = Env( python, bindirs + base.bindirs,
              f'{base.description} + overlay', conda_prefix = base.conda_prefix,
              jupyter_paths = ( [ path / 'share' / 'jupyter' ]
                                + base.jupyter_paths ),
              activated = base.activated )
    #Make the packages of the base environment available (after those of the
    #overlay), including processing of their .pth files:
    base_sp = json.loads( base.python_output(
        'import site,json;print(json.dumps(site.getsitepackages()))' ) )
    ov_sp = pathlib.Path( ov.python_output(
        'import site;print(site.getsitepackages()[0])' ) )
    ov_sp.joinpath('_ncnotebookdevtool_base.pth').write_text(
        ''.join( f'import site; site.addsitedir({str(p)!r})\n'
                 for p in base_sp ), encoding = 'utf-8' )
    ov.run( [ ov.python, '-m', 'pip', 'install', '-q', '--upgrade', 'pip' ],
            log = log )
    return ov

def pip_install( env, packages, *, extra_args = (), log = None ):
    if packages:
        env.run( [ env.python, '-m', 'pip', 'install', '-q' ]
                 + list(extra_args) + [ str(p) for p in packages ], log = log )

################################################################################
# NCrystal from a local clone of the NCrystal repository

def wheel_version( wheel ):
    #Wheel file names are NAME-VERSION-...:
    return pathlib.Path(wheel).name.split('-')[1]

def build_ncrystal_wheels( srcdir, wheeldir, *, log = None ):
    """Build wheels of ncrystal-core and ncrystal-python from a local clone of
    the NCrystal repository."""
    srcdir = pathlib.Path(srcdir).absolute()
    for sub in ('ncrystal_core','ncrystal_python'):
        if not ( srcdir / sub / 'pyproject.toml' ).is_file():
            raise EnvError(f'Not an NCrystal repository: {srcdir}')
    if wheeldir.exists():
        shutil.rmtree(wheeldir)
    wheeldir.mkdir( parents = True )
    print(f'Building NCrystal from {srcdir} (this takes a few minutes)',
          flush = True)
    for sub in ('ncrystal_core','ncrystal_python'):
        _run( [ sys.executable, '-m', 'pip', 'wheel', '-q', '--no-deps',
                '-w', wheeldir, srcdir / sub ], log = log )
    wheels = sorted(wheeldir.glob('*.whl'))
    if len(wheels) != 2:
        raise EnvError(f'Expected 2 NCrystal wheels, got: {wheels}')
    versions = set( wheel_version(w) for w in wheels )
    if len(versions) != 1:
        raise EnvError(f'Inconsistent versions of NCrystal wheels: {wheels}')
    return wheels

def verify_ncrystal( env, *, expect_dir = None, expect_version = None ):
    """Check which NCrystal the environment uses (returns a description)."""
    code = ( 'import json,shutil,NCrystal as NC;'
             'print(json.dumps([NC.__file__,NC.__version__,'
             'shutil.which("ncrystal-config") or ""]))' )
    ncfile, version, cfgcmd = json.loads( env.python_output(code) )
    if expect_dir is not None:
        expect_dir = str(pathlib.Path(expect_dir).resolve())
        for what, p in ( ('NCrystal module',ncfile),
                         ('ncrystal-config command',cfgcmd) ):
            if not str(pathlib.Path(p).resolve()).startswith(expect_dir):
                raise EnvError(f'The {what} used is not the one built from the'
                               f' local NCrystal repository: {p}')
    if expect_version is not None and version != expect_version:
        raise EnvError(f'NCrystal version {version} is used, but the local'
                       f' NCrystal repository has version {expect_version}')
    return f'NCrystal {version} from {pathlib.Path(ncfile).parent}'

################################################################################
# Environments for notebooks

class EnvRequest:
    """What a notebook needs from its environment."""

    def __init__( self, reqs, kind, *, ncrystal_src = False ):
        assert kind in ('venv','conda','current')
        self.kind = kind
        self.local = reqs.local_packages
        local_names = set(self.local)
        def nonlocal_pkgs( pkgs ):
            return [ p for p in pkgs if p not in local_names ]
        #With NCrystal from a local repository, plugins must be built against
        #it, so they are installed in the overlay:
        self.overlay_plugins = list(reqs.plugins) if ( ncrystal_src or
                                                      kind == 'current' ) else []
        base_plugins = [] if self.overlay_plugins else list(reqs.plugins)
        if kind == 'venv':
            assert not reqs.needs_conda
            self.key = ( 'venv', sorted(nonlocal_pkgs(reqs.pip_packages)
                                        + base_plugins) )
        elif kind == 'conda':
            from .envsetup import conda_platform
            self.key = ( 'conda',
                         sorted(reqs.conda_packages_for(conda_platform())),
                         sorted(nonlocal_pkgs(reqs.conda_pip_packages)
                                + base_plugins) )
        else:
            self.key = ( 'current', )
        self.needs_overlay = bool( self.local or self.overlay_plugins
                                   or ncrystal_src or kind == 'current' )

    def overlay_key( self ):
        return ( self.key, sorted(self.local.items()),
                 sorted(self.overlay_plugins) )

def create_base_env( req, *, python = None, fresh = False, log = None ):
    if req.kind == 'venv':
        return venv_env( req.key[1], python = python, fresh = fresh, log = log )
    if req.kind == 'conda':
        return conda_env( req.key[1], req.key[2], fresh = fresh, log = log )
    return current_env()

def create_overlay( req, base, path, *, ncrystal_wheels = None,
                    ncrystal_src = None, log = None ):
    """Create the overlay for the request on top of the base environment."""
    print(f'Creating overlay environment {path.name} on top of'
          f' {base.description}', flush = True)
    ov = overlay_env( base, path, log = log )
    if req.kind == 'current':
        missing = ov.missing_modules( EXEC_MODULES.values() )
        pip_install( ov, [ k for k, m in EXEC_MODULES.items()
                           if m in missing ], log = log )
    if ncrystal_wheels:
        pip_install( ov, ncrystal_wheels,
                     extra_args = ('--no-deps','--force-reinstall'), log = log )
    pip_install( ov, [ reporoot() / d for d in req.local.values() ],
                 extra_args = ('--no-deps','--force-reinstall'), log = log )
    if req.overlay_plugins:
        if ncrystal_wheels:
            #Build the plugins against the local NCrystal:
            pip_install( ov, ['scikit-build-core','cmake'], log = log )
            pip_install( ov, req.overlay_plugins,
                         extra_args = ('--no-deps','--no-build-isolation'),
                         log = log )
        else:
            pip_install( ov, req.overlay_plugins, extra_args = ('--no-deps',),
                         log = log )
    if ncrystal_wheels:
        verify_ncrystal( ov, expect_dir = path,
                         expect_version = wheel_version(ncrystal_wheels[0]) )
    return ov
