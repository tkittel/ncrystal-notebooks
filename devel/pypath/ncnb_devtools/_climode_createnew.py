from .utils import prefixed, print_msg


def short_description():
    return 'Create a new notebook (asking for its settings)'

def main( parser ):
    parser.init( short_description() + """. Asks for the title, menu title,
    shortkey, section, sort-value, requirements and plugins of the new
    notebook (unless given with the options below), and creates it with its
    settings cell, ready for editing with the launch mode.""" )
    parser.add_argument( '--title', help = 'Title of the notebook.' )
    parser.add_argument( '--menutitle', help = """Short title of the notebook
                         (at most 30 characters), for the menu of the
                         website.""" )
    parser.add_argument( '--shortkey', help = """Short unique key (lowercase
                         letters and digits, at most 14 characters).""" )
    parser.add_argument( '--section', help = 'Key of the section.' )
    parser.add_argument( '--sort-value', metavar = 'N',
                         help = """Order in the section (an integer; larger
                         values come later; default: 100 more than the largest
                         value in the section, so the notebook comes
                         last).""" )
    parser.add_argument( '--requires', metavar = 'REQS',
                         help = """Requirements, separated by commas (use
                         "none" for none).""" )
    parser.add_argument( '--plugins', help = """NCrystal plugins, separated by
                         commas (use "none" for none).""" )
    parser.add_argument( '--path', help = """Path of the new notebook (default:
                         notebooks/SHORTKEY/SHORTKEY.ipynb).""" )
    args = parser.parse_args()
    createnew( args )

class _Asker:
    """Takes values from the command line options, or asks for them."""

    def __init__( self ):
        import sys
        #Both must be terminals (on Windows, isatty() is also true for NUL):
        self.interactive = sys.stdin.isatty() and sys.stdout.isatty()

    def get( self, value, option, prompt, check, default = None ):
        """Value of an option (checked), or asked for until valid. The check
        function returns an error message, or None if the value is fine."""
        if value is not None:
            err = check(value)
            if err:
                raise SystemExit(f'ERROR: {err}')
            return value
        if not self.interactive:
            raise SystemExit(f'ERROR: Not running interactively, so please'
                             f' provide the {option} option')
        while True:
            dflt = f' [{default}]' if default else ''
            try:
                v = input( prefixed(f'{prompt}{dflt}: ') ).strip()
            except (EOFError,KeyboardInterrupt):
                raise SystemExit('\nAborted') from None
            if not v and default:
                v = default
            err = check(v)
            if not err:
                return v
            print_msg(f'  {err}')

def _suggest_shortkey( title, taken ):
    import re
    words = [ w for w in re.findall( r'[a-z0-9]+', title.lower() )
              if w not in ('a','an','the','of','and','in','to','with','for',
                           'on','ncrystal') ]
    base = ''.join( words )[:14] or 'notebook'
    key, i = base, 2
    while key in taken:
        key = f'{base[:14-len(str(i))]}{i}'
        i += 1
    return key

def _parse_list( value ):
    import re
    if value.strip().lower() == 'none':
        return []
    return [ e for e in re.split(r'[,\s]+',value.strip()) if e ]

def createnew( args ):
    import pathlib

    from .config import load_config
    from .dirs import reporoot
    from .nbfile import make_cell, write
    from .nbsettings import (
        HEADER,
        MAX_MENUTITLE_LENGTH,
        NotebookSettings,
        SettingsError,
        _shortkey_re,
        find_notebooks,
        section_notebooks,
    )
    cfg = load_config()
    notebooks = find_notebooks()
    taken_keys = { nb.shortkey for nb in notebooks if nb.shortkey }
    taken_titles = { nb.settings.title for nb in notebooks if nb.settings }
    taken_menutitles = { nb.settings.menutitle for nb in notebooks
                            if nb.settings }
    ask = _Asker()

    def check_title( v ):
        if not v:
            return 'A title is needed'
        if v in taken_titles:
            return 'This title is already used by another notebook'
        return None
    title = ask.get( args.title, '--title', 'Title', check_title )

    def check_menutitle( v ):
        if not v:
            return 'A menu title is needed'
        if len(v) > MAX_MENUTITLE_LENGTH:
            return ( 'The menu title must be at most'
                     f' {MAX_MENUTITLE_LENGTH} characters' )
        if v in taken_menutitles:
            return 'This menu title is already used by another notebook'
        return None
    menutitle = ask.get( args.menutitle, '--menutitle',
                         'Short title for the menu of the website',
                         check_menutitle,
                         default = ( title if len(title) <= MAX_MENUTITLE_LENGTH
                                     else None ) )

    def check_shortkey( v ):
        if not _shortkey_re.match(v):
            return ('The shortkey must be 1-14 lowercase letters or digits'
                    ' (it is used in URLs, so it should never change)')
        if v in taken_keys:
            return 'This shortkey is already used by another notebook'
        return None
    shortkey = ask.get( args.shortkey, '--shortkey',
                        'Shortkey (for URLs etc.)', check_shortkey,
                        default = _suggest_shortkey( title, taken_keys ) )

    if args.section is None and ask.interactive:
        print_msg('Sections:')
        for s in cfg.sections:
            print_msg(f'  {s.key:<12} {s.title}')
    def check_section( v ):
        if not cfg.section(v):
            return ( f'Unknown section "{v}" (sections: '
                     + ', '.join( s.key for s in cfg.sections ) + ')' )
        return None
    section = ask.get( args.section, '--section', 'Section', check_section,
                       default = cfg.sections[0].key )

    in_section = section_notebooks( notebooks, section )
    taken_values = { nb.settings.sort_value for nb in in_section }
    if args.sort_value is None and ask.interactive and in_section:
        print_msg('Notebooks in the section, by sort-value:')
        for nb in in_section:
            print_msg(f'  {nb.settings.sort_value:>6}  {nb.settings.shortkey}')
    def check_sort_value( v ):
        try:
            v = int(v)
        except ValueError:
            return 'The sort-value must be an integer'
        if v in taken_values:
            return ( 'This sort-value is already used by another notebook in'
                     ' the section' )
        return None
    #(Without a terminal to ask, the default is used: last in the section)
    default_sort_value = str( max( taken_values, default = 0 ) + 100 )
    sort_value = int( ask.get(
        args.sort_value if ( args.sort_value is not None or ask.interactive )
        else default_sort_value, '--sort-value',
        'Sort-value (larger values come later)', check_sort_value,
        default = default_sort_value ) )

    if args.requires is None and ask.interactive:
        print_msg('Requirements besides NCrystal:')
        for key, r in cfg.requirements.items():
            if key != 'ncrystal':
                conda = '' if r.pip_available else ' (conda only)'
                print_msg(f'  {key:<12} {r.description}{conda}')
    def check_requires( v ):
        bad = [ r for r in _parse_list(v) if r not in cfg.requirements ]
        if bad:
            return f'Unknown requirements: {", ".join(bad)}'
        return None
    requires = [ r for r in _parse_list( ask.get(
        args.requires, '--requires', 'Requirements (separated by commas)',
        check_requires,
        default = 'plot' ) ) if r != 'ncrystal' ]

    if args.plugins is None and ask.interactive and cfg.plugins:
        print_msg('Plugins: ' + ', '.join(cfg.plugins))
    def check_plugins( v ):
        bad = [ p for p in _parse_list(v) if p not in cfg.plugins ]
        if bad:
            return ( f'Unknown plugins: {", ".join(bad)} (plugins must first'
                     ' be added to notebook_settings.toml)' )
        return None
    plugins = _parse_list( ask.get( args.plugins, '--plugins',
                                    'Plugins (separated by commas)',
                                    check_plugins, default = 'none' ) )

    if args.path:
        path = pathlib.Path(args.path).absolute()
    else:
        path = reporoot() / 'notebooks' / shortkey / f'{shortkey}.ipynb'
    if path.suffix != '.ipynb':
        raise SystemExit('ERROR: The path must end with .ipynb')
    if path.exists():
        raise SystemExit(f'ERROR: File already exists: {path}')
    nbdir = ( reporoot() / 'notebooks' ).resolve()
    if nbdir not in path.parent.resolve().parents \
       and path.parent.resolve() != nbdir:
        raise SystemExit(f'ERROR: The notebook must be in {nbdir}')

    lines = [ HEADER, f'# title: {title}', f'# menutitle: {menutitle}',
              f'# shortkey: {shortkey}',
              f'# section: {section}',
              f'# sort-value: {sort_value}' ]
    if requires:
        lines.append( '# requires: ' + ', '.join(requires) )
    if plugins:
        lines.append( '# plugins: ' + ', '.join(plugins) )
    settings_src = '\n'.join(lines)
    try:
        NotebookSettings( settings_src )
    except SettingsError as e:
        raise SystemExit(f'ERROR: {e}') from None
    nb = { 'cells' : [ make_cell( 'code', settings_src ),
                       make_cell( 'markdown', '## Introduction [intro]\n\n'
                                  'Describe here what this notebook is about.'
                                  ' (Section headings, like the one above, end'
                                  ' with a short key in brackets: see "Section'
                                  ' headings" in the developer'
                                  ' documentation.)' ),
                       make_cell( 'code', '' ) ],
           'metadata' : {}, 'nbformat' : 4, 'nbformat_minor' : 5 }
    path.parent.mkdir( parents = True, exist_ok = True )
    write( path, nb )
    relpath = path.relative_to( reporoot() ).as_posix()
    print_msg(f'\nCreated {relpath} with the settings:\n')
    print_msg( '\n'.join( '  ' + e for e in lines ) )
    print_msg('\nThe settings can be changed later by editing the first cell'
              ' (see the developer\ndocumentation). To edit the notebook,'
              ' run:\n')
    print_msg(f'  devel/bin/ncnotebookdevtool launch {shortkey}\n')
