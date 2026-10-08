def short_description():
    return 'Write the generated version of a notebook for a given target'

def main( parser ):
    from .expand import TARGETS
    parser.init( short_description() + """, e.g. to inspect the version for
    Google Colab or for pip users. The generated notebook is not run.""" )
    parser.add_argument( 'NOTEBOOK', help = 'Notebook (shortkey or path).' )
    parser.add_argument( '--target', choices = TARGETS, required = True,
                         help = 'The target.' )
    parser.add_argument( '-o', '--output', metavar = 'FILE', required = True,
                         help = 'Output file (.ipynb).' )
    args = parser.parse_args()
    import pathlib

    from .config import load_config
    from .expand import expand
    from .nbfile import dumps
    from .nbsettings import find_notebooks, select_notebooks
    nb = select_notebooks( [args.NOTEBOOK], find_notebooks() )[0]
    if nb.settings is None:
        raise SystemExit(f'ERROR: {nb.relpath}: {nb.error}')
    out = pathlib.Path(args.output)
    out.write_text( dumps( expand( nb, load_config(), args.target ) ),
                    encoding = 'utf-8' )
    print(f'Wrote {out}')
