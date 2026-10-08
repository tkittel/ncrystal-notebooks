from .utils import print_msg


def short_description():
    return 'List the notebooks by section, as on the website'

def main( parser ):
    parser.init( short_description() + """. Shows shortkeys, titles and
    requirements, as declared in the settings cells of the notebooks.""" )
    parser.add_argument( 'NOTEBOOK', nargs = '*',
                         help = """Notebooks (shortkeys or paths; default:
                         all).""" )
    parser.add_argument( '--paths', action='store_true',
                         help='Also show the paths of the notebooks.' )
    args = parser.parse_args()
    from .config import load_config
    from .nbsettings import find_notebooks, section_notebooks, select_notebooks
    cfg = load_config()
    notebooks = select_notebooks( args.NOTEBOOK, find_notebooks() )
    nshown = 0
    for section in cfg.sections:
        nbs = section_notebooks( notebooks, section.key )
        if not nbs and args.NOTEBOOK:
            continue
        print_msg(f'{section.title} [{section.key}]:')
        if not nbs:
            print_msg('    (no notebooks)')
        for nb in nbs:
            s = nb.settings
            extra = list(s.requires) + [ f'plugin:{p}'
                                                 for p in s.plugins ]
            if s.slow:
                extra.append('slow')
            req = f'  [{", ".join(extra)}]' if extra else ''
            print_msg(f'    {s.shortkey:<14} {s.title}{req}')
            if args.paths:
                print_msg(f'    {"":<14} {nb.relpath}')
            nshown += 1
        print_msg()
    for nb in notebooks:
        if not nb.settings:
            print_msg(f'Invalid: {nb.relpath} ({nb.error})')
        elif not cfg.section(nb.settings.section):
            print_msg(f'Unknown section "{nb.settings.section}": {nb.relpath}')
