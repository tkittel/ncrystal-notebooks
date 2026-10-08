"""Command line interface of ncnotebookdevtool, with modes implemented in
the _climode_*.py files."""

def get_mode_list():
    import pathlib
    return sorted( m.name[9:-3]
                   for m in
                   pathlib.Path(__file__).parent.glob('_climode_*.py') )

def progname():
    return 'ncnotebookdevtool'

def usage():
    theprogname = progname()
    ml = get_mode_list()
    example_mode = 'list'
    assert example_mode in ml
    modelist_indent = '\n     '
    modelist_str=''
    nadjust = max(len(mode) for mode in ml)
    for mode in ml:
        descr = get_module_short_description(mode)
        ms = mode.ljust(nadjust)
        modelist_str += f'{modelist_indent}{ms} : {descr}'
    #modelist_str = modelist_indent + f'{modelist_indent}'.join(ml)
    print(f"""Usage:

  $> {theprogname} MODE <mode options>

Available MODEs are:
{modelist_str}

Use the -h or --help flag to get information about the options
available for a given mode. For example:

  $> {theprogname} {example_mode} --help
""")

def import_sibling_module( mode = None, module_name = None ):
    assert int(mode is None)+int(module_name is None) == 1
    module_name = module_name or f'_climode_{mode}'
    import importlib
    pkgarg = __name__
    if pkgarg == '__main__':
        #Make running as python -m <packagename>.<thismodule> work:
        pkgarg = f'{__package__}.foo'
    return importlib.import_module(f'..{module_name}',pkgarg)

def get_module_short_description( mode ):
    return import_sibling_module(mode=mode).short_description()

def main():
    #Error messages (given to SystemExit) are also printed with the prefix of
    #all output of the tool:
    import sys

    from .utils import prefixed
    try:
        _main()
    except SystemExit as e:
        if not isinstance( e.code, str ):
            raise
        sys.stdout.flush()
        print( prefixed( e.code.strip('\n') ), file = sys.stderr )
        raise SystemExit(1) from None

def _main():
    import sys
    if len(sys.argv)<2 or sys.argv[1] in ('-h','--h','--he','--hel','--help'):
        usage()
        return
    if len(sys.argv)==2 and sys.argv[1]=='--show-completion-list':
        print( ' '.join(get_mode_list()) )
        return

    mode = sys.argv[1]
    if mode not in get_mode_list():
        raise SystemExit(f'ERROR: Invalid mode "{mode}". Run without'
                         ' arguments to list available modes.')

    parser = ArgParser( cliname = progname(),
                                  modename = mode,
                                  args = sys.argv[2:] )

    from .envs import EnvError
    try:
        import_sibling_module(mode=mode).main( parser )
    except EnvError as e:
        raise SystemExit(f'ERROR: {e}') from None

class ArgParser:

    def __init__(self, *, cliname, modename, args ):
        self.__parser = None
        self.__helpw = 59
        self.__descrw = 79
        self.__progname = f'{cliname} {modename}'
        self.__needs_wrap = False
        self.__args = args

    def get_raw_args( self ):
        #For special modes, not using the usual parser
        return self.__args

    def init( self, descr, **kwargs ):
        assert 'prog' not in kwargs
        assert 'descr' not in kwargs
        import argparse
        if 'formatter_class' not in kwargs:
            self.__needs_wrap = True
            import textwrap
            kwargs['formatter_class'] = argparse.RawTextHelpFormatter
            newdescr = ''
            for i, p in enumerate(descr.strip().split('\n\n')):
                if i:
                    newdescr += '\n\n'
                newdescr += textwrap.fill(' '.join(p.strip().split()),
                                          self.__descrw)
            #'`N' and '`' are preserved newlines and spaces respectively.
            descr = newdescr.replace('`N','\n').replace('`',' ')
        self.__parser = argparse.ArgumentParser( prog = self.__progname,
                                                 description=descr,
                                                 **kwargs )

    def __fixhelp( self, msg ):
        assert self.__parser is not None
        if self.__needs_wrap:
            import textwrap
            return textwrap.fill( ' '.join(msg.split()), width=self.__helpw )
        return msg

    def add_argument( self, *args, **kwargs ):
        assert 'help' in kwargs
        kwargs['help'] = self.__fixhelp( kwargs['help'] )
        self.__parser.add_argument(*args, **kwargs)

    def parse_args( self ):
        return self.__parser.parse_args( self.__args )

    def error( self, msg ):
        self.__parser.error(msg)

if __name__ == '__main__':
    main()
