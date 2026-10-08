"""Preparing environments for a set of notebooks (shared by the modes which
run notebooks)."""

import pathlib

from .envs import (
    EnvRequest,
    build_ncrystal_wheels,
    create_base_env,
    create_overlay,
    verify_ncrystal,
)
from .expand import Requirements

ENV_CHOICES = ('auto','venv','conda','current')

def add_env_args( parser ):
    parser.add_argument( '--env', choices = ENV_CHOICES, default = 'auto',
                         help = """Environments to use: "venv" (pip),
                         "conda", or "auto" (venv, except for notebooks
                         needing conda), all created by the tool and cached
                         (in ~/.cache/ncnotebookdevtool or
                         $NCNOTEBOOKDEVTOOL_CACHEDIR). With "current", the
                         current environment is used (with anything missing
                         installed in a separate overlay venv, so the current
                         environment is not modified).""" )
    parser.add_argument( '--ncrystal-src', metavar = 'DIR',
                         help = """Use NCrystal built from this local clone of
                         the NCrystal repository (instead of the released
                         NCrystal).""" )
    parser.add_argument( '--fresh-envs', action = 'store_true',
                         help = """Recreate cached environments, instead of
                         reusing them.""" )
    parser.add_argument( '--python', metavar = 'PYTHON',
                         help = """Python used to create venv environments
                         (default: the Python running this tool).""" )

def conda_platform():
    """The conda platform name (e.g. "linux-64") of this machine."""
    import platform
    import sys
    m = platform.machine().lower()
    os_name = { 'linux' : 'linux', 'darwin' : 'osx',
                'win32' : 'win' }.get( sys.platform, sys.platform )
    arch = { 'x86_64' : '64', 'amd64' : '64', 'aarch64' : 'aarch64',
             'arm64' : ( 'arm64' if os_name == 'osx' else 'aarch64' )
            }.get( m, m )
    return f'{os_name}-{arch}'

def env_kind( reqs, choice ):
    """The kind of environment for a notebook (None if not possible)."""
    if choice == 'auto':
        return 'conda' if reqs.needs_conda else 'venv'
    if choice == 'venv' and reqs.needs_conda:
        return None
    return choice

def colab_env():
    """The current environment as it is, for running notebooks in Google's
    Colab runtime image (where the notebooks install their requirements
    themselves, as on Google Colab)."""
    import sys

    from .envs import Env
    python = pathlib.Path(sys.executable)
    return Env( python, [ python.parent ], 'the Colab runtime environment',
                keep_pythonpath = True )

def in_colab_image():
    """Whether this runs in Google's Colab runtime image (or on Colab)."""
    import importlib.util
    try:
        return importlib.util.find_spec('google.colab') is not None
    except ImportError:
        return False

class EnvSetup:
    """Environments for notebooks, created on demand."""

    def __init__( self, args, cfg, workdir ):
        self.args = args
        self.cfg = cfg
        self.workdir = pathlib.Path(workdir)
        self.workdir.mkdir( parents = True, exist_ok = True )
        self.log = self.workdir / 'environments.log'
        self.ncrystal_src = ( pathlib.Path(args.ncrystal_src).absolute()
                              if args.ncrystal_src else None )
        self._wheels = None
        self._bases = {}
        self._overlays = {}

    def _ncrystal_wheels( self ):
        if self.ncrystal_src and self._wheels is None:
            self._wheels = build_ncrystal_wheels(
                self.ncrystal_src, self.workdir / 'ncrystal_wheels',
                log = self.log )
        return self._wheels

    def env_for( self, nb, kind ):
        """The environment for the notebook."""
        if kind == 'colab':
            return colab_env()
        reqs = Requirements( nb.settings, self.cfg )
        req = EnvRequest( reqs, kind, ncrystal_src = bool(self.ncrystal_src) )
        bkey = repr(req.key)
        if bkey not in self._bases:
            self._bases[bkey] = create_base_env(
                req, python = self.args.python, fresh = self.args.fresh_envs,
                log = self.log )
        base = self._bases[bkey]
        if not req.needs_overlay:
            return base
        okey = repr(req.overlay_key())
        if okey not in self._overlays:
            path = self.workdir / 'overlays' / f'overlay{len(self._overlays)}'
            ov = create_overlay( req, base, path,
                                 ncrystal_wheels = self._ncrystal_wheels(),
                                 log = self.log )
            if self.ncrystal_src:
                print('  Verified: '+verify_ncrystal(ov),flush=True)
            self._overlays[okey] = ov
        return self._overlays[okey]
