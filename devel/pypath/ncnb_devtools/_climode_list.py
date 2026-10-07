def short_description():
    return 'List the notebooks by section, as on the website'

def main( parser ):
    parser.init( short_description() + """. Shows shortkeys, titles and
    requirements, as declared in the settings cells of the notebooks.""" )
    parser.add_argument( '--paths', action='store_true',
                         help='Also show the paths of the notebooks.' )
    args = parser.parse_args()
    from .config import load_config
    from .nbsettings import find_notebooks
    cfg = load_config()
    notebooks = find_notebooks()
    nshown = 0
    for section in cfg.sections:
        nbs = [ nb for nb in notebooks
                if nb.settings and nb.settings.section == section.key ]
        print(f'{section.title} [{section.key}]:')
        if not nbs:
            print('    (no notebooks)')
        for nb in nbs:
            s = nb.settings
            extra = [ r for r in s.requires ] + [ f'plugin:{p}'
                                                 for p in s.plugins ]
            if s.slow:
                extra.append('slow')
            req = f'  [{", ".join(extra)}]' if extra else ''
            print(f'    {s.shortkey:<14} {s.title}{req}')
            if args.paths:
                print(f'    {"":<14} {nb.relpath}')
            nshown += 1
        print()
    for nb in notebooks:
        if not nb.settings:
            print(f'Invalid: {nb.relpath} ({nb.error})')
        elif not cfg.section(nb.settings.section):
            print(f'Unknown section "{nb.settings.section}": {nb.relpath}')
