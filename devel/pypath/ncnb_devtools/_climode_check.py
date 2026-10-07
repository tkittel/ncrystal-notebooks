def short_description():
    return 'Quick checks of all notebooks (format, settings, line lengths)'

def main( parser ):
    parser.init( short_description() + """. This is fast and does not run the
    notebooks (see the "test" mode for that). It fails if a notebook is not in
    canonical form, in which case "precommit" will fix it.""" )
    parser.parse_args()
    from .config import load_config
    from .nbsettings import find_notebooks
    from .checks import check_all, report
    notebooks = find_notebooks()
    if not report( check_all( notebooks, load_config() ) ):
        raise SystemExit(1)
    print(f'All {len(notebooks)} notebooks OK')
