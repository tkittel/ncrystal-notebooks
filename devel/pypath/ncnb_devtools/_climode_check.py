from .utils import print_msg


def short_description():
    return 'Quick checks of all notebooks (format, settings, line lengths)'

def main( parser ):
    parser.init( short_description() + """. This is fast and does not run the
    notebooks (see the "test" mode for that). It fails if a notebook is not in
    canonical form, in which case "precommit" will fix it.""" )
    parser.add_argument( 'NOTEBOOK', nargs = '*',
                         help = """Notebooks (shortkeys or paths; default:
                         all).""" )
    args = parser.parse_args()
    from .checks import check_all, report
    from .config import load_config
    from .nbsettings import find_notebooks, select_notebooks
    allnbs = find_notebooks()
    notebooks = select_notebooks( args.NOTEBOOK, allnbs )
    #Check all (e.g. for unique shortkeys), but report only the selected:
    selected = { nb.relpath for nb in notebooks }
    problems = [ ( r, p ) for r, p in check_all( allnbs, load_config() )
                 if r in selected ]
    if not report( problems ):
        raise SystemExit(1)
    n = len(notebooks)
    print_msg(f'All {n} notebook{"s" if n != 1 else ""} OK')
