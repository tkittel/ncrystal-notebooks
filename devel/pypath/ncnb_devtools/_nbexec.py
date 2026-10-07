"""Run a notebook with nbclient, and check that it can be converted to HTML.

This script runs with the Python of the environment in which the notebook
runs (it is not imported as part of the ncnb_devtools package).

Usage: python _nbexec.py INPUT OUTPUT TIMELIMIT
"""

import sys
import time

def main():
    inp, outp, limit = sys.argv[1], sys.argv[2], int(sys.argv[3])
    import nbformat
    from nbclient import NotebookClient
    from nbclient.exceptions import CellExecutionError, CellTimeoutError
    nb = nbformat.read( inp, as_version = 4 )
    nbformat.validate(nb)
    t0 = time.time()
    deadline = t0 + limit
    def remaining_time( cell ):
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
        client.execute()
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
        with open( outp.rsplit('.',1)[0] + '.html', 'w',
                   encoding = 'utf-8' ) as fh:
            fh.write(html)
    return 0 if ok else 1

if __name__ == '__main__':
    sys.exit(main())
