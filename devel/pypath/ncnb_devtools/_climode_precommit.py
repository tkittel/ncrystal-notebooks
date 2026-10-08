def short_description():
    return ( 'Bring notebooks into canonical form and check them (run before'
             ' commits)' )

def main( parser ):
    parser.init( short_description() + """. This removes outputs and
    non-standard metadata from all notebooks, writes them in a canonical JSON
    format (which keeps diffs readable), and runs the same quick checks as the
    "check" mode. Notebooks are not run.""" )
    parser.add_argument( 'NOTEBOOK', nargs = '*',
                         help = """Notebooks (shortkeys or paths; default:
                         all).""" )
    args = parser.parse_args()
    from .checks import check_all, report
    from .config import load_config
    from .nbfile import canonical_text, source_str, split_source
    from .nbsettings import (
        find_notebooks,
        select_notebooks,
        split_settings_source,
    )
    for nb in select_notebooks( args.NOTEBOOK, find_notebooks() ):
        if nb.nb is None:
            continue
        cells = nb.nb['cells']
        if cells and cells[0]['cell_type'] == 'code':
            #Remove generated code from the settings cell:
            settings_src, generated = split_settings_source(
                source_str(cells[0]) )
            if generated:
                cells[0]['source'] = split_source(settings_src)
        text = canonical_text(nb.nb)
        if nb.path.read_text(encoding='utf-8') != text:
            nb.path.write_text(text,encoding='utf-8')
            print(f'Updated {nb.relpath}')
    allnbs = find_notebooks()
    notebooks = select_notebooks( args.NOTEBOOK, allnbs )
    selected = { nb.relpath for nb in notebooks }
    problems = [ ( r, p ) for r, p in check_all( allnbs, load_config() )
                 if r in selected ]
    if not report( problems ):
        raise SystemExit(1)
    n = len(notebooks)
    print(f'All {n} notebook{"s" if n != 1 else ""} OK')
