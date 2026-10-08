"""Building the website with Sphinx (myst-nb and sphinx-book-theme).

Layout of the output directory:

  src/                  Generated Sphinx sources.
  src/notebooks/        Executed notebooks (one page per notebook, named by
                        shortkey).
  src/_extra/downloads/ Notebook versions for pip and conda users (copied as-is
                        to the website).
  html/                 The website.
  colab/                Notebook versions for Google Colab (for the colab
                        branch, which Colab links point to).
"""

import html as htmllib
import json
import pathlib
import shutil

from .dirs import reporoot
from .expand import Requirements, expand
from .nbsettings import section_notebooks

SPHINX_PACKAGES = [ 'sphinx', 'myst-nb', 'sphinx-book-theme' ]

def colab_url( cfg, shortkey ):
    return ( 'https://colab.research.google.com/github/'
             f'{cfg.github_repo}/blob/{cfg.colab_branch}/{shortkey}.ipynb' )

def links_markdown( nb, cfg ):
    """Links shown at the top of each notebook page (raw HTML, so Sphinx does
    not try to resolve them)."""
    reqs = Requirements( nb.settings, cfg )
    sk = nb.settings.shortkey
    links = []
    if not reqs.needs_conda:
        links.append( f'<a href="../downloads/pip/{sk}.ipynb" download>'
                      'Download notebook (for pip)</a>' )
    links.append( f'<a href="../downloads/conda/{sk}.ipynb" download>'
                  'Download notebook (for conda)</a>' )
    links.append( f'<a href="{colab_url(cfg,sk)}" target="_blank">'
                  'Open in Google Colab</a>' )
    return '<p>' + ' &nbsp;|&nbsp; '.join(links) + '</p>'

CONF_PY = '''
project = {project!r}
html_title = {project!r}
author = 'The NCrystal developers'
extensions = [ 'myst_nb' ]
nb_execution_mode = 'off'
#(attrs_block for the ids of the sections, which the notebooks have as {{#id}}
#before the headings, see headings.py):
myst_enable_extensions = [ 'dollarmath', 'amsmath', 'colon_fence',
                           'attrs_block' ]
myst_heading_anchors = 3
html_theme = 'sphinx_book_theme'
html_theme_options = {{
    'repository_url' : {repo_url!r},
    'use_repository_button' : True,
    'path_to_docs' : '',
    'show_toc_level' : 2,
    #The notebooks of the sections are shown in the menu:
    'show_navbar_depth' : 2,
    #No table of contents to the right of the front page:
    'secondary_sidebar_items' : {{ '**' : [ 'page-toc' ], 'index' : [] }},
    #(The search field is in the sidebar, so the header should not have
    #another one, which it otherwise has by default:)
    'navbar_persistent' : [],
    'logo' : {{ 'image_light' : '_static/ncrystal-logo.svg',
               'image_dark' : '_static/ncrystal-logo-dark.svg',
               'alt_text' : {project!r} }},
}}
html_favicon = '_static/favicon.svg'
html_extra_path = [ '_extra' ]
html_static_path = [ '_static' ]
html_css_files = [ 'ncnb.css' ]
exclude_patterns = [ '_build', '_extra', '_static', '**.ipynb_checkpoints' ]
suppress_warnings = [ 'myst.header', 'mystnb.unknown_mime_type',
                     'misc.highlighting_failure' ]

'''

#Compact layout of the lists of notebooks on the front page, text outputs of
#cells in scrollable boxes, with a background (in light and dark mode)
#different from both the page and the code cells, and the logo always visible
#at the top of the sidebar (which the theme scrolls to show the current page),
#where the sections stand out from their notebooks:
CSS = '''
:root { --ncnb-output-bg: #fbf8ec; --ncnb-output-bar: #d9c98f; }
html[data-theme=dark] { --ncnb-output-bg: #2a2619; --ncnb-output-bar: #6b5f35; }
.cell_output .output.stream pre, .cell_output .output.stderr pre,
.cell_output .output.text_plain pre { max-height: 25em; overflow-y: auto; }
.cell_output .output .highlight, .cell_output .output pre {
  background: var(--ncnb-output-bg) !important; }
.cell_output .output.stream, .cell_output .output.stderr,
.cell_output .output.text_plain {
  border-left: 4px solid var(--ncnb-output-bar); border-radius: 2px; }
.bd-article section:has(> ul.ncnb-list) > h2 {
  font-size: 1.45rem; margin-top: 1.1em !important;
  margin-bottom: 0.15em !important; }
.bd-article section:has(> ul.ncnb-list) > .toctree-wrapper { display: none; }
ul.ncnb-list { margin: 0 !important; padding-left: 1.3em; }
ul.ncnb-list li { margin: 0.05em 0 !important; }
nav.bd-links li.toctree-l1 > a {
  font-weight: 600; margin-top: 0.4em;
  background: var(--pst-color-surface); border-radius: 4px; }
.bd-sidebar-primary .sidebar-primary-item:has(> .navbar-brand.logo) {
  position: sticky; top: -1rem; z-index: 2;
  margin-top: -1rem; padding: 1rem 0 0.5rem 0;
  background: var(--pst-color-background);
  box-shadow: 0 6px 6px -6px var(--pst-color-shadow); }
'''

#Line in developers.md replaced by tables of what notebook_settings.toml
#defines:
SETTINGS_TABLES_MARKER = '<!-- ncnotebookdevtool: settings tables -->'

_platform_names = { 'win-64' : 'Windows',
                    'osx-arm64' : 'macOS with Apple Silicon',
                    'osx-64' : 'macOS with Intel',
                    'linux-aarch64' : 'Linux on ARM',
                    'linux-64' : 'Linux on x86-64' }

def _conda_entry_markdown( entry ):
    #A conda package entry, with a platform marker (if any) in words:
    name, _, marker = entry.partition(';')
    marker = ' '.join( marker.split() ).replace('"',"'")
    words = { "sys_platform != 'win32'" : ' (not on Windows)',
              "sys_platform == 'win32'" : ' (on Windows)' }
    note = words.get( marker, f' ({marker})' if marker else '' )
    return f'`{name.strip()}`{note}'

def settings_tables_markdown( cfg ):
    """Markdown tables of the sections, requirements and plugins available
    in notebook_settings.toml."""
    def code( items ):
        return ', '.join( f'`{e}`' for e in items ) or '–'  # noqa: RUF001
    out = [ '**Requirements** (for `requires`):', '',
            '| Name | Provides | With pip | With conda |',
            '|---|---|---|---|' ]
    for key, r in cfg.requirements.items():
        if key == 'ncrystal':
            continue#always included
        pip = code( r.pip ) if r.pip_available else 'no'
        conda = ', '.join( [ _conda_entry_markdown( e ) for e in r.conda ]
                           + [ f'`{e}` (with pip)' for e in r.conda_pip ] )
        if r.conda_platforms:
            missing = [ name for p, name in _platform_names.items()
                        if p not in r.conda_platforms ]
            if missing:
                conda += ' (not on ' + ', '.join( missing ) + ')'
        out.append( f'| `{key}` | {r.description} | {pip} | {conda} |' )
    note = ( 'On Google Colab, notebooks needing conda install it with'
             f' {code([cfg.colab_condacolab])} (with pip)' )
    if cfg.colab_conda_extra:
        note += ( ', and also install '
                  + code( cfg.colab_conda_extra ) + ' (with conda)' )
    out += [ '', note + '.' ]
    out += [ '', '**Plugins** (for `plugins`):', '',
             '| Name | Installed from |', '|---|---|' ]
    for key, spec in cfg.plugins.items():
        note = ( ' (built from source, which currently fails on Windows)'
                 if 'git+' in spec else '' )
        out.append( f'| `{key}` | `{spec}`{note} |' )
    out += [ '', '**Sections** (for `section`):', '',
             '| Name | Section on the website |', '|---|---|' ]
    for s in cfg.sections:
        out.append( f'| `{s.key}` | {s.title} |' )
    return '\n'.join(out)

def write_sources( notebooks, executed, cfg, srcdir, colabdir,
                   warnings = None ):
    """Write the Sphinx sources. executed maps shortkeys to executed notebooks
    (dicts); notebooks which are not in it are included unexecuted. warnings
    maps shortkeys to texts shown in a warning box at the top of the page."""
    if srcdir.exists():
        shutil.rmtree(srcdir)
    nbdir = srcdir / 'notebooks'
    nbdir.mkdir( parents = True )
    for sub in ('pip','conda'):
        ( srcdir / '_extra' / 'downloads' / sub ).mkdir( parents = True )
    if colabdir.exists():
        shutil.rmtree(colabdir)
    colabdir.mkdir( parents = True )
    ( srcdir / 'conf.py' ).write_text( CONF_PY.format(
        project = 'NCrystal notebooks',
        repo_url = f'https://github.com/{cfg.github_repo}' ),
        encoding = 'utf-8' )
    ( srcdir / '_static' ).mkdir()
    ( srcdir / '_static' / 'ncnb.css' ).write_text( CSS, encoding = 'utf-8' )
    for f in ( reporoot() / 'devel' / 'site' / 'logo' ).glob('*.svg'):
        shutil.copy( f, srcdir / '_static' / f.name )
    devdoc = ( reporoot() / 'devel' / 'site' / 'developers.md'
               ).read_text( encoding = 'utf-8' )
    ( srcdir / 'developers.md' ).write_text(
        devdoc.replace( SETTINGS_TABLES_MARKER, settings_tables_markdown(cfg) ),
        encoding = 'utf-8' )

    for nb in notebooks:
        sk = nb.settings.shortkey
        page = executed.get(sk)
        if page is None:
            page = expand( nb, cfg, 'site', links_markdown(nb,cfg) )
        if warnings and sk in warnings:
            #After the title and the links:
            page['cells'].insert( 2, { 'cell_type' : 'markdown',
                                       'id' : 'ncnb-warning', 'metadata' : {},
                                       'source' : ( ':::{warning}\n'
                                                    + warnings[sk]
                                                    + '\n:::' ) } )
        #Highlight code as IPython (with magics and shell commands):
        page['metadata']['language_info'] = { 'name' : 'python',
                                              'pygments_lexer' : 'ipython3' }
        ( nbdir / f'{sk}.ipynb' ).write_text( json.dumps(page,indent=1),
                                                encoding = 'utf-8' )
        reqs = Requirements( nb.settings, cfg )
        variants = [ ('conda','conda') ]
        if not reqs.needs_conda:
            variants.append( ('pip','pip') )
        for target, sub in variants:
            ( srcdir / '_extra' / 'downloads' / sub / f'{sk}.ipynb'
              ).write_text( json.dumps( expand( nb, cfg, target ), indent = 1 ),
                            encoding = 'utf-8' )
        ( colabdir / f'{sk}.ipynb' ).write_text(
            json.dumps( expand( nb, cfg, 'colab' ), indent = 1 ),
            encoding = 'utf-8' )

    #A page for each section, with its description and its notebooks, and the
    #index page, with the notebooks of all sections:
    ( srcdir / 'sections' ).mkdir()
    lines = [ '# NCrystal notebooks', '',
              ( reporoot() / 'devel' / 'site' / 'index_intro.md'
                ).read_text( encoding = 'utf-8' ).strip(), '' ]
    shown = []
    for section in cfg.sections:
        nbs = section_notebooks( notebooks, section.key )
        if not nbs:
            continue
        shown.append( section )
        page = [ f'# {section.title}', '' ]
        if section.description:
            page += [ section.description, '' ]
        page += [ notebook_list( nbs, '../notebooks' ), '',
                  '```{toctree}', ':hidden:', '' ]
        #(The menu shows the short menu titles of the notebooks:)
        page += [ f'{nb.settings.menutitle}'
                  f' <../notebooks/{nb.settings.shortkey}>' for nb in nbs ]
        page += [ '```', '' ]
        ( srcdir / 'sections' / f'{section.key}.md' ).write_text(
            '\n'.join(page), encoding = 'utf-8' )
        lines += [ f'## [{section.title}](sections/{section.key}.md)', '',
                   notebook_list( nbs, 'notebooks' ), '' ]
    lines += [ '```{toctree}', ':hidden:', '' ]
    lines += [ f'sections/{section.key}' for section in shown ]
    lines += [ '```', '' ]
    lines += [ '```{toctree}', ':hidden:', ':caption: Development', '',
               'developers', '```', '' ]
    ( srcdir / 'index.md' ).write_text( '\n'.join(lines), encoding = 'utf-8' )

def notebook_list( notebooks, nbdir ):
    """List of links to the notebooks (with their titles), as raw HTML for a
    compact layout (see CSS above)."""
    html = [ '<ul class="ncnb-list">' ]
    for nb in notebooks:
        html.append( f'<li><a href="{nbdir}/{nb.settings.shortkey}.html">'
                     + htmllib.escape(nb.settings.title) + '</a></li>' )
    html.append( '</ul>' )
    return '\n'.join(html)

def finalize_executed( nbdict ):
    """Clean up an executed notebook for the website."""
    for c in nbdict['cells']:
        c.get('metadata',{}).pop('execution',None)
    return nbdict

def build_html( env, srcdir, htmldir, log ):
    if htmldir.exists():
        shutil.rmtree(htmldir)
    pathlib.Path(log).unlink( missing_ok = True )
    env.run( [ env.python, '-m', 'sphinx', '-b', 'html', '-q', srcdir,
               htmldir ], log = log )
