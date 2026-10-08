"""Section headings in markdown cells, and their keys.

Headings of sections (## and ###) end with a key in brackets, e.g.
"## Interactive results [results]", unique within the notebook. In the
versions of the notebooks for users, the key is removed from the heading, and
an anchor is added instead, with the shortkey of the notebook and the key as
id (e.g. "sapphire-results", unique on the whole website), which links to
the section can use (e.g. sapphire.html#sapphire-results on the website). They
keep working if the heading text changes. Links to sections within the same
notebook are written as [text](#key) by authors, and changed accordingly.
"""

import re

#Keys: lowercase letters and digits, starting with a letter, at most 10
#characters:
KEY_RE = re.compile( r'^[a-z][a-z0-9]{0,9}$' )
KEY_RULE = ( 'lowercase letters (a-z) and digits, starting with a letter, at'
             ' most 10 characters' )

#The cell after the settings cell must start with this heading, followed by an
#introduction to the notebook:
INTRO_HEADING = '## Introduction [intro]'

_heading_re = re.compile( r'^( {0,3})(#{1,6})[ \t]+(.*?)[ \t]*$' )
_trailing_key_re = re.compile( r'^(.*?)[ \t]+\[([^\[\]]*)\]$' )
_fence_re = re.compile( r'^ {0,3}(```|~~~)' )

class Heading:
    def __init__( self, lineno, level, text, key ):
        self.lineno = lineno#index of the line in the cell
        self.level = level
        self.text = text#without the key
        self.key = key#None if there is no key in brackets at the end

def _strip_closing( text ):
    """Heading text without the optional closing sequence of #'s."""
    return re.sub( r'(^|[ \t]+)#+$', '', text ).rstrip()

def anchor_id( shortkey, key ):
    """The id of the anchor of a section."""
    return f'{shortkey}-{key}'

def find_headings( source ):
    """The (ATX) headings in the markdown source (outside fenced code)."""
    res = []
    fence = None
    for i, line in enumerate( source.split('\n') ):
        m = _fence_re.match(line)
        if m:
            if fence is None:
                fence = m.group(1)
            elif m.group(1) == fence:
                fence = None
            continue
        if fence is not None:
            continue
        m = _heading_re.match(line)
        if not m:
            continue
        level, text = len(m.group(2)), _strip_closing(m.group(3))
        km = _trailing_key_re.match(text)
        key = None
        if km:
            text, key = _strip_closing(km.group(1)), km.group(2)
        res.append( Heading( i, level, text, key ) )
    return res

def section_links( source ):
    """The keys in links to sections of the same notebook, [text](#key)."""
    return re.findall( r'\]\(#([^)\s]*)\)', source )

def replace_keys_with_anchors( source, target, shortkey ):
    """The markdown source with the keys removed from the headings, and an
    anchor for each key added before its heading: {#id} for the website
    (where it becomes the id of the section, used e.g. by its table of
    contents), and an HTML anchor for the notebooks. Links to sections,
    [text](#key), are changed to use the ids of the anchors."""
    source = re.sub( r'\]\(#([a-z][a-z0-9]*)\)',
                     lambda m: f'](#{anchor_id(shortkey,m.group(1))})', source )
    lines = source.split('\n')
    for h in reversed( find_headings(source) ):
        if h.key is None:
            continue
        hashes = '#' * h.level
        aid = anchor_id( shortkey, h.key )
        anchor = ( [ f'{{#{aid}}}' ] if target == 'site'
                   else [ f'<a id="{aid}"></a>', '' ] )
        if h.lineno > 0 and lines[h.lineno-1].strip():
            anchor = [''] + anchor
        lines[h.lineno:h.lineno+1] = anchor + [ f'{hashes} {h.text}' ]
    return '\n'.join(lines)
