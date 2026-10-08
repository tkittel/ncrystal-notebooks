"""Utilities used throughout the tool."""

#Every line printed by the tool starts with this prefix, so that its output can
#be told apart from the output of other programs it runs (e.g. Jupyter Lab):
PRINT_PREFIX = 'ncnotebookdevtool::'

def prefixed( text ):
    """The text with PRINT_PREFIX at the start of every line."""
    return '\n'.join( f'{PRINT_PREFIX} {line}' if line else PRINT_PREFIX
                      for line in str(text).split('\n') )

def print_msg( *args, sep = ' ', file = None, flush = False ):
    """Print like print(), but with PRINT_PREFIX at the start of every line.
    All output of the tool is printed with this function."""
    import sys
    print( prefixed( sep.join( str(a) for a in args ) ),
           file = file or sys.stdout, flush = flush )
