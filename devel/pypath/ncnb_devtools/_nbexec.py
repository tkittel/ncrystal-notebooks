"""Run a notebook with nbclient, and check that it can be converted to HTML.

This script runs with the Python of the environment in which the notebook
runs (it is not imported as part of the ncnb_devtools package).

Usage: python _nbexec.py INPUT OUTPUT TIMEOUT
"""

import sys
import time

def main():
    inp, outp, timeout = sys.argv[1], sys.argv[2], int(sys.argv[3])
    import nbformat
    from nbclient import NotebookClient
    from nbclient.exceptions import CellExecutionError
    nb = nbformat.read( inp, as_version = 4 )
    nbformat.validate(nb)
    client = NotebookClient( nb, timeout = timeout, kernel_name = 'python3',
                             resources = { 'metadata' : { 'path' : '.' } } )
    t0 = time.time()
    ok = True
    try:
        client.execute()
    except CellExecutionError as e:
        ok = False
        print( str(e)[-6000:] )
    finally:
        nbformat.write( nb, outp )
    print(f'Executed in {time.time()-t0:.1f} seconds')
    if ok:
        #Check that the notebook can be converted to HTML (cf. ncrystal#266):
        from nbconvert import HTMLExporter
        html, _ = HTMLExporter().from_notebook_node(nb)
        with open( outp.rsplit('.',1)[0] + '.html', 'w' ) as fh:
            fh.write(html)
    return 0 if ok else 1

if __name__ == '__main__':
    sys.exit(main())
