"""Expansion of the settings cell into installation and setup code.

The expansion depends on the target:

  test   : For running the notebook in an environment prepared by the tool.
  launch : For editing the notebook in an environment prepared by the tool.
  site   : For running the notebook when building the website.
  colab  : Version of the notebook for Google Colab.
  pip    : Version of the notebook for users installing with pip.
  conda  : Version of the notebook for users installing with conda.

For "test" and "launch", the settings lines are kept, followed by the MARKER
line and the generated code, so the settings cell can be restored afterwards.
The other targets give notebooks for users, starting with a title cell.
"""

import copy

from .nbfile import make_cell, source_str
from .nbsettings import MARKER

TARGETS = ( 'test', 'launch', 'site', 'colab', 'pip', 'conda' )

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

    def _collect( self, attr ):
        res = []
        for r in self.reqs:
            for p in getattr(r,attr):
                if p not in res:
                    res.append(p)
        return res

    @property
    def pip_packages( self ):
        """Packages for pip installations (only if not needs_conda)."""
        return self._collect('pip')

    @property
    def conda_packages( self ):
        return self._collect('conda')

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
    res = [ 'conda install -c conda-forge ' + _quote(reqs.conda_packages) ]
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
               '!mamba install -y -q -c conda-forge '
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
        return out
    new = [ make_cell( 'markdown', f'# {s.title}', 'ncnb-title' ) ]
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
    out['cells'] = new + rest
    return out

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
