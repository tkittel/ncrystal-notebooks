"""The quick checks of all notebooks (no execution)."""

from .nbfile import canonical_text, source_str
from .nbsettings import MARKER

PRECOMMIT_HINT = ('run "devel/bin/ncnotebookdevtool precommit" to bring the'
                  ' notebooks into canonical form')

def check_notebook( nb, cfg ):
    """Problems with a single notebook, as a list of strings."""
    if nb.nb is None or nb.settings is None:
        return [ nb.error ]
    problems = []
    s = nb.settings
    if nb.path.read_text(encoding='utf-8') != canonical_text(nb.nb):
        problems.append('not in canonical form (e.g. it has outputs or'
                        f' non-standard metadata): {PRECOMMIT_HINT}')
    if MARKER in source_str(nb.nb['cells'][0]).splitlines():
        problems.append('the settings cell contains generated code:'
                        f' {PRECOMMIT_HINT}')
    if not cfg.section(s.section):
        problems.append(f'unknown section "{s.section}" (sections are defined'
                        ' in notebook_settings.toml)')
    for r in s.requires:
        if r not in cfg.requirements:
            problems.append(f'unknown requirement "{r}" (requirements are'
                            ' defined in notebook_settings.toml)')
    for p in s.plugins:
        if p not in cfg.plugins:
            problems.append(f'unknown plugin "{p}" (plugins are defined in'
                            ' notebook_settings.toml)')
    pidx = nb.parameters_cell_indices()
    if s.test_parameters:
        if len(pidx) != 1:
            problems.append('test-parameters need exactly one code cell tagged'
                            f' "parameters" (found {len(pidx)})')
        else:
            import re
            psrc = source_str(nb.nb['cells'][pidx[0]])
            for name, _ in s.test_parameters:
                if not re.search(r'^%s\s*='%re.escape(name), psrc, re.M):
                    problems.append(f'test parameter "{name}" is not assigned'
                                    ' in the cell tagged "parameters"')
    elif len(pidx) > 1:
        problems.append('more than one cell tagged "parameters"')
    maxlen = s.max_line_length or cfg.max_line_length
    nlong = 0
    for i, c in enumerate(nb.nb['cells']):
        if c['cell_type'] != 'code':
            continue
        for j, line in enumerate(source_str(c).splitlines()):
            if len(line) > maxlen:
                nlong += 1
                if nlong <= 3:
                    problems.append(f'line {j+1} of cell {i+1} is longer than'
                                    f' {maxlen} characters ({len(line)})')
    if nlong > 3:
        problems.append(f'... and {nlong-3} more lines longer than {maxlen}'
                        ' characters (the limit can be changed with'
                        ' "max-line-length" in the settings cell)')
    problems += heading_problems( nb )
    return problems

def heading_problems( nb ):
    """Problems with the section headings and their keys (see headings.py),
    and with links to sections."""
    from .headings import find_headings, section_links, KEY_RE, KEY_RULE
    problems = []
    keys = {}
    links = []
    for i, c in enumerate(nb.nb['cells']):
        if c['cell_type'] != 'markdown':
            continue
        src = source_str(c)
        links += [ ( i, k ) for k in section_links(src) ]
        for h in find_headings(src):
            where = f'heading "{h.text}" (cell {i+1})'
            if h.level == 1:
                problems.append(f'{where}: headings with a single # are not'
                                ' allowed, since the title is generated from'
                                ' the settings cell (use ## and ### for'
                                ' sections)')
            elif h.level > 3:
                if h.key is not None:
                    problems.append(f'{where}: only ## and ### headings have'
                                    f' keys (remove "[{h.key}]")')
            elif h.key is None:
                problems.append(f'{where}: no key at the end of the heading,'
                                f' e.g. "{"#"*h.level} {h.text} [mykey]" (keys'
                                f' are {KEY_RULE})')
            elif not KEY_RE.match(h.key):
                problems.append(f'{where}: invalid key "{h.key}" (keys are'
                                f' {KEY_RULE})')
            elif h.key in keys:
                problems.append(f'{where}: the key "{h.key}" is also used for'
                                f' a heading in cell {keys[h.key]+1}')
            else:
                keys[h.key] = i
    for i, k in links:
        if k not in keys:
            problems.append(f'link to "#{k}" in cell {i+1}, but no heading has'
                            f' the key "{k}"')
    return problems

def check_all( notebooks, cfg ):
    """All problems, as a list of (relpath, problem) pairs."""
    res = []
    for nb in notebooks:
        for p in check_notebook( nb, cfg ):
            res.append( ( nb.relpath, p ) )
    #Uniqueness of shortkeys and (menu) titles:
    for attr in ('shortkey','title','menutitle'):
        seen = {}
        for nb in notebooks:
            if nb.settings:
                v = getattr(nb.settings,attr)
                if v in seen:
                    res.append( ( nb.relpath, f'{attr} "{v}" is also used by'
                                  f' {seen[v]}' ) )
                else:
                    seen[v] = nb.relpath
    return res

def report( problems ):
    """Print the problems, and return True if there were none."""
    for relpath, p in problems:
        print(f'{relpath}: {p}')
    return not problems
