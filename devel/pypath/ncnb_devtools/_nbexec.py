"""Run a notebook with nbclient, and check that it can be converted to HTML.

This script runs with the Python of the environment in which the notebook
runs (it is not imported as part of the ncnb_devtools package).

Usage: python _nbexec.py INPUT OUTPUT TIMELIMIT [RESTARTCELLID]

If RESTARTCELLID is given, the cell with that id is expected to restart the
kernel (like condacolab.install_miniforge() on Google Colab), and the
following cells run in a new kernel (see execute).
"""

import sys
import time


def patch_jupyter_client():
    """Work around messages from the kernel which nbclient (or rather the
    zmq-based channels of jupyter_client) sometimes only receives when its wait
    for them times out. This happens in particular for notebooks with
    ipywidgets.interact, which then hang until the cell timeout, while the
    kernel sent its reply right away. Waiting in short slices avoids this."""
    import importlib
    import inspect
    from queue import Empty
    #The asynchronous channel class used by nbclient, in jupyter_client 8 and
    #later, 7 (e.g. in Google's Colab runtime image), and 6:
    candidates = [ ('jupyter_client.channels','AsyncZMQSocketChannel'),
                   ('jupyter_client.channels','ZMQSocketChannel'),
                   ('jupyter_client.asynchronous.channels','ZMQSocketChannel') ]
    AsyncZMQSocketChannel = None
    for modname, clsname in candidates:
        try:
            cls = getattr( importlib.import_module(modname), clsname )
        except (ImportError, AttributeError):
            continue
        if inspect.iscoroutinefunction( cls.get_msg ):
            AsyncZMQSocketChannel = cls
            break
    if AsyncZMQSocketChannel is None:
        print('Note: not working around delayed kernel messages (unknown'
              ' version of jupyter_client)')
        return
    orig_get_msg = AsyncZMQSocketChannel.get_msg
    async def get_msg( self, timeout = None ):
        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            dt = 0.2
            if deadline is not None:
                dt = min( dt, max( 0.0, deadline - time.monotonic() ) )
            try:
                return await orig_get_msg( self, timeout = dt )
            except Empty:
                if deadline is not None and time.monotonic() >= deadline:
                    raise
    AsyncZMQSocketChannel.get_msg = get_msg

def execute( client, restart_after = None ):
    """Execute the notebook of the client, like NotebookClient.execute, except
    that after the cell with the id restart_after (if any), the kernel is
    restarted, as on Google Colab after a cell restarting the kernel (e.g.
    condacolab.install_miniforge(), which restarts it through a wrapper of the
    Python executable, setting up the conda environment). The new kernel is
    started in the same way as the first one, i.e. with the same executable,
    which is then the wrapper."""
    from nbclient.exceptions import DeadKernelError
    nb = client.nb
    client.reset_execution_trackers()
    start = 0
    while start < len(nb.cells):
        with client.setup_kernel():
            info = client.wait_for_reply( client.kc.kernel_info() )
            if info is not None and 'language_info' in info['content']:
                nb.metadata['language_info'] = info['content']['language_info']
            cells = list( enumerate(nb.cells) )[start:]
            start = len(nb.cells)
            for index, cell in cells:
                restart = ( restart_after is not None
                            and cell.get('id') == restart_after )
                try:
                    client.execute_cell( cell, index, execution_count
                                         = client.code_cells_executed + 1 )
                except DeadKernelError:
                    if not restart:
                        raise
                if restart:
                    print(f'Restarting the kernel after cell {index+1}, as on'
                          ' Google Colab', flush = True)
                    start = index + 1
                    break
    client.set_widgets_metadata()

def main():
    inp, outp, limit = sys.argv[1], sys.argv[2], int(sys.argv[3])
    restart_after = sys.argv[4] if len(sys.argv) > 4 else None
    patch_jupyter_client()
    import nbformat
    from nbclient import NotebookClient
    from nbclient.exceptions import CellExecutionError, CellTimeoutError
    nb = nbformat.read( inp, as_version = 4 )
    nbformat.validate(nb)
    t0 = time.time()
    deadline = t0 + limit
    def remaining_time( _cell ):
        #Each cell can use the time left until the deadline:
        return max( 1, int( deadline - time.time() ) + 1 )
    current = {}
    def on_cell_execute( cell, cell_index ):
        current['cell'], current['index'] = cell, cell_index
    client = NotebookClient( nb, timeout_func = remaining_time,
                             on_cell_execute = on_cell_execute,
                             kernel_name = 'python3',
                             resources = { 'metadata' : { 'path' : '.' } } )
    ok, timed_out = True, False
    try:
        execute( client, restart_after )
    except CellTimeoutError:
        ok, timed_out = False, True
    except CellExecutionError as e:
        ok = False
        print( str(e)[-6000:] )
    finally:
        nbformat.write( nb, outp )
    dt = time.time() - t0
    print(f'Executed in {dt:.1f} seconds')
    if timed_out or dt > limit:
        ok = False
        if timed_out and current:
            src = current['cell']['source'].splitlines()
            print(f'Stopped while running cell {current["index"]+1}, which'
                  ' starts with:\n' + '\n'.join( '    '+e for e in src[:6] ))
        print(f'ERROR: The notebook exceeded the time limit of {limit} seconds'
              ' (see the time limits in notebook_settings.toml). Please make'
              ' it faster (for tests, perhaps with test-parameters), or mark'
              ' it as slow.')
    if ok:
        #Check that the notebook can be converted to HTML (cf. ncrystal#266):
        from nbconvert import HTMLExporter
        html, _ = HTMLExporter().from_notebook_node(nb)
        import pathlib
        pathlib.Path( outp.rsplit('.',1)[0] + '.html' ).write_text(
            html, encoding = 'utf-8' )
    return 0 if ok else 1

if __name__ == '__main__':
    sys.exit(main())
