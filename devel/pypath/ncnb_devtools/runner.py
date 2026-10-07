"""Preparing run directories and running notebooks."""

import json
import os
import pathlib
import shutil
import subprocess
import time

from .dirs import codcache_dir
from .nbfile import dumps

def write_kernelspec( env, datadir ):
    """Make the "python3" kernel use the Python of the environment (taking
    precedence over any other python3 kernel found by Jupyter)."""
    kdir = pathlib.Path(datadir) / 'kernels' / 'python3'
    kdir.mkdir( parents = True, exist_ok = True )
    ( kdir / 'kernel.json' ).write_text( json.dumps( {
        'argv' : [ str(env.python), '-m', 'ipykernel_launcher', '-f',
                   '{connection_file}' ],
        'display_name' : 'Python 3 (ipykernel)',
        'language' : 'python' }, indent = 1 ), encoding = 'utf-8' )

def prepare_rundir( rundir, nbname, nbdict ):
    """Create a fresh run directory with the notebook (and the cached files from
    the Crystallography Open Database)."""
    rundir = pathlib.Path(rundir)
    if rundir.exists():
        shutil.rmtree(rundir)
    rundir.mkdir( parents = True )
    shutil.copytree( codcache_dir(), rundir / 'ncrystal_onlinedb_filecache' )
    nbfile = rundir / nbname
    nbfile.write_text( dumps(nbdict), encoding = 'utf-8' )
    return nbfile

class RunResult:
    def __init__( self, ok, seconds, message, output ):
        self.ok = ok
        self.seconds = seconds
        self.message = message
        self.output = output

def run_notebook( env, nbfile, limit, logfile ):
    """Run the notebook file (in its directory) in the environment. It fails
    if its execution takes longer than limit seconds."""
    nbfile = pathlib.Path(nbfile)
    rundir = nbfile.parent
    output = rundir / ( nbfile.stem + '.executed.ipynb' )
    jdatadir = rundir.parent / ( rundir.name + '.jupyterdata' )
    write_kernelspec( env, jdatadir )
    environ = env.environ()
    environ['JUPYTER_DATA_DIR'] = str(jdatadir)
    #JUPYTER_PATH is searched before JUPYTER_DATA_DIR, so our kernel must also
    #be first there:
    environ['JUPYTER_PATH'] = os.pathsep.join( [ str(jdatadir),
                                                 environ['JUPYTER_PATH'] ] )
    script = pathlib.Path(__file__).parent / '_nbexec.py'
    t0 = time.time()
    try:
        p = subprocess.run( [ str(env.python), str(script), nbfile.name,
                              output.name, str(limit) ],
                            cwd = rundir, env = environ, text = True,
                            encoding = 'utf-8', errors = 'replace',
                            stdout = subprocess.PIPE,
                            stderr = subprocess.STDOUT,
                            timeout = limit + 300 )
        out, rc = p.stdout, p.returncode
    except subprocess.TimeoutExpired as e:
        out = ( e.stdout or b'' )
        out = out.decode() if isinstance(out,bytes) else out
        out += f'\nKilled after {limit+300} seconds'
        rc = 1
    dt = time.time() - t0
    pathlib.Path(logfile).write_text( out, encoding = 'utf-8' )
    #Remove terminal colour codes (from IPython tracebacks):
    import re
    out = re.sub( r'\x1b\[[0-9;]*m', '', out )
    lines = [ e for e in out.strip().splitlines() if e.strip() ]
    msg = '' if rc == 0 else '\n'.join(lines[-25:])
    #Use the time of the execution itself (to which the time limits apply), if
    #reported:
    m = re.search( r'^Executed in ([0-9.]+) seconds$', out, re.M )
    return RunResult( rc == 0, float(m.group(1)) if m else dt, msg, output )
