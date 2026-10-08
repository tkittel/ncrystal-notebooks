"""Expansion of the settings cell into installation and setup code.

The expansion depends on the target:

  test   : For running the notebook in an environment prepared by the tool.
  launch : For editing the notebook in an environment prepared by the tool.
  site   : For running the notebook when building the website.
  colab  : Version of the notebook for Google Colab.
  colabtest : The "colab" version with the test parameters, for running the
           notebook in Google's Colab runtime image.
  pip    : Version of the notebook for users installing with pip.
  conda  : Version of the notebook for users installing with conda.

For "test" and "launch", the settings lines are kept, followed by the MARKER
line and the generated code, so the settings cell can be restored afterwards.
The other targets give notebooks for users, starting with a title cell.
"""

import copy

from .nbfile import make_cell, source_str
from .nbsettings import MARKER

TARGETS = ( 'test', 'launch', 'site', 'colab', 'colabtest', 'pip', 'conda' )

#The NCrystal logo, shown on its own line above the title of the notebooks for
#users (except on the website, which shows it in the sidebar). It is not
#floated to the right of the title, where Google Colab's cell toolbar covers
#it. It is referred to by URL, since the notebooks are also opened on their own
#(e.g. in Google Colab), and the HTML <img> tag works in all common notebook
#viewers. The 316x64 px image is shown at half the size, to be sharp on
#high-resolution screens. The size is given as a width, since JupyterLab
#ignores the height attribute. Without internet access, the alt text is shown
#instead:
LOGO_URL = ( 'https://raw.githubusercontent.com/mctools/ncrystal-logo/main/png/'
             'logo-compact/ncrystal-logo-compact-64h.png' )
LOGO_HTML = f'<img src="{LOGO_URL}" alt="NCrystal" width="158">'

def _combine_extras( pkgs, name ):
    """Combine e.g. "name", "name[a]" and "name[b]" into "name[a,b]" (at the
    place of the first of them)."""
    import re
    pat = re.compile(r'^%s(\[([^\]]*)\])?$'%re.escape(name))
    extras, res, pos = [], [], None
    for p in pkgs:
        m = pat.match(p)
        if not m:
            res.append(p)
            continue
        if pos is None:
            pos = len(res)
            res.append(None)
        for e in ( m.group(2) or '' ).split(','):
            if e.strip() and e.strip() not in extras:
                extras.append(e.strip())
    if pos is not None:
        res[pos] = name + ( '[%s]'%','.join(sorted(extras)) if extras else '' )
    return res

class Requirements:
    """The resolved requirements of a notebook."""

    def __init__( self, settings, cfg ):
        keys = ['ncrystal'] + [ r for r in settings.requires
                                if r != 'ncrystal' ]
        self.reqs = [ cfg.requirements[k] for k in keys ]
        self.plugin_names = list(settings.plugins)
        self.plugins = [ cfg.plugins[p] for p in settings.plugins ]
        self.needs_conda = any( not r.pip_available for r in self.reqs )
        self.has_plot = any( r.key == 'plot' for r in self.reqs )
        self.has_widgets = any( r.key == 'widgets' for r in self.reqs )

    def source_plugins( self ):
        """Names of plugins installed from git (i.e. built from source)."""
        return [ n for n, spec in zip( self.plugin_names, self.plugins )
                 if 'git+' in spec ]

    def unavailable_with_conda( self, platform ):
        """Keys of requirements not available with conda on the platform."""
        return [ r.key for r in self.reqs
                 if r.conda_platforms and platform not in r.conda_platforms ]

    def _collect( self, attr ):
        res = []
        for r in self.reqs:
            for p in getattr(r,attr):
                if p not in res:
                    res.append(p)
        return res

    @property
    def pip_packages( self ):
        """Packages for pip installations (only if not needs_conda), with all
        extras of the ncrystal package combined (e.g. "ncrystal[cif,plot]")."""
        return _combine_extras( self._collect('pip'), 'ncrystal' )

    @property
    def conda_packages( self ):
        """The conda packages for installation instructions (those for Linux
        and macOS, the most common platforms)."""
        return self.conda_packages_for( 'linux-64' )

    def conda_packages_for( self, platform ):
        """The conda packages needed on the conda platform."""
        from .config import conda_package_name
        res = []
        for e in self._collect('conda'):
            n = conda_package_name( e, platform )
            if n and n not in res:
                res.append(n)
        #ncrystal-all includes ncrystal-extra, which includes ncrystal:
        if 'ncrystal-all' in res and 'ncrystal-extra' in res:
            res.remove('ncrystal-extra')
        if 'ncrystal' in res and ( 'ncrystal-extra' in res
                                   or 'ncrystal-all' in res ):
            res.remove('ncrystal')
        return res

    @property
    def conda_pip_packages( self ):
        return self._collect('conda_pip')

    @property
    def local_packages( self ):
        """Dict of package name -> directory in the repository."""
        res = {}
        for r in self.reqs:
            res.update(r.local)
        return res

    @property
    def descriptions( self ):
        res = [ r.description for r in self.reqs ]
        res += [ f'the {p} plugin' for p in self.plugin_names ]
        return res

def _quote( pkgs ):
    #Quote requirements with special characters for shells:
    return ' '.join( ( f'"{p}"' if any( c in p for c in ' @<>[];' ) else p )
                     for p in pkgs )

def pip_install_cmd( reqs ):
    return 'pip install ' + _quote( reqs.pip_packages + reqs.plugins )

def conda_install_cmds( reqs ):
    pkgs = reqs.conda_packages
    #Only conda-forge (never mixed with the "defaults" channel):
    res = [ 'conda install --override-channels -c conda-forge '
            + _quote(pkgs) ]
    extra = reqs.conda_pip_packages + reqs.plugins
    if extra:
        res.append( 'pip install ' + _quote(extra) )
    return res

def setup_code( settings, reqs, cfg, target ):
    """The setup code (after any installation), as a list of lines."""
    lines = []
    if target == 'colab' and ( reqs.has_plot or reqs.has_widgets ):
        lines += [ '#Enable widgets on Google Colab:',
                   'from google.colab import output as _google_colab_output',
                   '_google_colab_output.enable_custom_widget_manager()' ]
    if reqs.has_plot:
        interactive = target in ('launch','pip','conda')
        lines += [ '#Matplotlib plots%s:' % ( ' (interactive)' if interactive
                                              else '' ),
                   '%matplotlib ' + ( 'ipympl' if interactive else 'inline' ),
                   'import matplotlib',
                   'matplotlib.rcParams.update({"figure.autolayout": True})' ]
    for r in reqs.reqs:
        if r.setup:
            lines += r.setup.split('\n')
        if target == 'colab' and r.colab_setup:
            lines += r.colab_setup.split('\n')
    if settings.import_ncrystal:
        v = cfg.ncrystal_min_version
        lines += [ '#Import NCrystal:',
                   'import NCrystal as NC',
                   f'assert NC.version_num >= {cfg.ncrystal_min_version_num},'
                   f' "NCrystal version {v} or later is needed"',
                   'NC.test() #< quick test that the installation works' ]
    return lines

def install_comment( reqs, target ):
    """Comment lines describing the requirements and how to install them."""
    import textwrap
    what = reqs.descriptions
    text = ( 'This notebook needs ' + ', '.join(what[:-1])
             + ( ' and ' if len(what) > 1 else '' ) + what[-1] + '.' )
    lines = [ '#' + e for e in textwrap.wrap( text, 78 ) ]
    if target == 'pip':
        lines += [ '#Install them for instance with:', '#',
                   '#   ' + pip_install_cmd(reqs) ]
    elif target == 'conda':
        lines += [ '#Install them for instance with:', '#' ]
        lines += [ '#   ' + c for c in conda_install_cmds(reqs) ]
    else:
        lines += [ '#They can be installed for instance with:', '#' ]
        if not reqs.needs_conda:
            lines += [ '#   ' + pip_install_cmd(reqs), '#', '#or with conda:',
                       '#' ]
        lines += [ '#   ' + c for c in conda_install_cmds(reqs) ]
    return lines

def colab_install_cells( reqs ):
    """Installation cells for Google Colab, as lists of lines."""
    if not reqs.needs_conda:
        return [ [ '#Install software on Google Colab:',
                   '%pip -q install ' + _quote(reqs.pip_packages+reqs.plugins) ] ]
    first = [ '#Install conda on Google Colab. This restarts the kernel, so the',
              '#notebook will say that it crashed. This is expected!',
              '%pip -q install condacolab',
              'import condacolab',
              'condacolab.install_miniforge()' ]
    second = [ '#Install software on Google Colab:',
               '!mamba install -y -q --override-channels -c conda-forge '
               + _quote(reqs.conda_packages) ]
    extra = reqs.conda_pip_packages + reqs.plugins
    if extra:
        second.append( '%pip -q install ' + _quote(extra) )
    return [ first, second ]

def expand( nb, cfg, target, links_markdown = None ):
    """Expanded copy of the notebook (a Notebook object, see nbsettings.py) as a
    dict, for the given target. For user-facing targets, links_markdown can
    give extra markdown shown after the title."""
    assert target in TARGETS
    if target == 'colabtest':
        out = expand( nb, cfg, 'colab', links_markdown )
        insert_test_parameters( out['cells'], nb.settings )
        return out
    s = nb.settings
    assert s is not None
    reqs = Requirements( s, cfg )
    out = copy.deepcopy(nb.nb)
    cells = out['cells']
    first_id = cells[0].get('id')
    rest = cells[1:]
    code = setup_code( s, reqs, cfg, target )
    if target in ('test','launch'):
        cells[0]['source'] = '\n'.join( [ s.source, MARKER ] + code )
        if target == 'test':
            insert_test_parameters( cells, s )
        return out
    title = f'# {s.title}'
    if target != 'site':
        title = LOGO_HTML + '\n\n' + title
    new = [ make_cell( 'markdown', title, 'ncnb-title' ) ]
    if links_markdown:
        new.append( make_cell( 'markdown', links_markdown, 'ncnb-links' ) )
    if target == 'colab':
        icells = colab_install_cells( reqs )
        for i, lines in enumerate(icells[:-1]):
            new.append( make_cell( 'code', '\n'.join(lines),
                                   f'ncnb-install{i}' ) )
        last = icells[-1] + code
    else:
        last = install_comment( reqs, target ) + [''] + code
    new.append( make_cell( 'code', '\n'.join(last), first_id or 'ncnb-setup' ) )
    for c in rest:
        if is_input_hidden( c, cfg ):
            hide_input( c )
    out['cells'] = new + rest
    return out

def insert_test_parameters( cells, settings ):
    """Insert a cell assigning the test values of the parameters (if any) after
    the cell tagged "parameters"."""
    if not settings.test_parameters:
        return
    pidx = [ i for i, c in enumerate(cells) if c['cell_type'] == 'code'
             and 'parameters' in c.get('metadata',{}).get('tags',[]) ][0]
    lines = [ '#Parameters for tests (generated by ncnotebookdevtool):' ]
    lines += [ f'{k} = {v}' for k, v in settings.test_parameters ]
    cells.insert( pidx + 1, make_cell( 'code', '\n'.join(lines),
                                       'ncnb-test-parameters' ) )

def is_input_hidden( cell, cfg ):
    """Whether the code of a cell is hidden (collapsed) for users: if it is
    tagged "hide-input", or is longer than hide_input_lines (unless tagged
    "show-input")."""
    if cell['cell_type'] != 'code':
        return False
    tags = cell.get('metadata',{}).get('tags',[])
    if 'hide-input' in tags:
        return True
    return ( 'show-input' not in tags
             and len(source_str(cell).splitlines()) > cfg.hide_input_lines )

def hide_input( cell ):
    #The "hide-input" tag is used by the website (myst-nb), and the metadata by
    #Jupyter Lab and Notebook:
    md = cell.setdefault('metadata',{})
    tags = md.setdefault('tags',[])
    if 'hide-input' not in tags:
        tags.append('hide-input')
    md.setdefault('jupyter',{})['source_hidden'] = True

def collapse( nbdict ):
    """Remove generated code from the settings cell of a notebook dict (e.g.
    after editing an expanded notebook). Returns True if anything was
    removed."""
    from .nbsettings import split_settings_source
    cells = nbdict['cells']
    if not cells or cells[0]['cell_type'] != 'code':
        return False
    settings_src, generated = split_settings_source( source_str(cells[0]) )
    if not generated and MARKER not in source_str(cells[0]).splitlines():
        return False
    cells[0]['source'] = settings_src
    return True
