import json
import os
import pathlib
import shutil
import subprocess
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent.parent
TOOL = REPO / 'devel' / 'bin' / 'ncnotebookdevtool'
sys.path.insert( 0, str( REPO / 'devel' / 'pypath' ) )

MINIMAL_TOML = '''
[general]
ncrystal_min_version = "4.2.0"
max_line_length = 40

[[sections]]
key = "basics"
title = "Basics"

[requirements.ncrystal]
pip = ["ncrystal"]
conda = ["ncrystal"]

[requirements.plot]
description = "matplotlib"
pip = ["matplotlib"]
conda = ["matplotlib-base"]

[requirements.openmc]
description = "OpenMC"
conda = ["openmc"]

[plugins]
Dummy = "ncrystal-plugin-Dummy"
'''

def make_nb( cells ):
    """A notebook (dict) from a list of (cell_type, source)."""
    return { 'cells' : [ { 'cell_type' : ct, 'metadata' : {}, 'source' : src,
                           **( { 'outputs' : [], 'execution_count' : None }
                               if ct == 'code' else {} ) }
                         for ct, src in cells ],
             'metadata' : {}, 'nbformat' : 4, 'nbformat_minor' : 4 }

SETTINGS = ( '# NCrystal notebook settings\n# title: {title}\n'
             '# shortkey: {key}\n# section: basics\n# requires: plot' )

@pytest.fixture
def fakerepo( tmp_path, monkeypatch ):
    """A minimal repository with two notebooks (in canonical form)."""
    ( tmp_path / 'notebook_settings.toml' ).write_text( MINIMAL_TOML )
    shutil.copytree( REPO / 'devel' / 'codcache', tmp_path / 'devel' / 'codcache' )
    nbdir = tmp_path / 'notebooks'
    nbdir.mkdir()
    for key in ('one','two'):
        nb = make_nb( [ ('code', SETTINGS.format( title = f'Notebook {key}',
                                                  key = key ) ),
                        ('markdown', 'Some text.'),
                        ('code', 'x = NC.load("Al_sg225.ncmat")') ] )
        ( nbdir / f'{key}.ipynb' ).write_text( json.dumps(nb) )
    monkeypatch.setenv( 'NCNOTEBOOKDEVTOOL_REPOROOT', str(tmp_path) )
    import ncnb_devtools.config as cfgmod
    cfgmod._cache[0] = None
    run_tool( 'precommit' )
    return tmp_path

def run_tool( *args, check = True ):
    p = subprocess.run( [ sys.executable, str(TOOL) ] + list(args),
                        capture_output = True, text = True,
                        env = dict(os.environ) )
    if check and p.returncode != 0:
        raise RuntimeError( f'Tool failed: {args}\n{p.stdout}\n{p.stderr}' )
    return p
