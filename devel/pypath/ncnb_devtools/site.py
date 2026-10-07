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
from .expand import expand, Requirements

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
myst_enable_extensions = [ 'dollarmath', 'amsmath', 'colon_fence' ]
html_theme = 'sphinx_book_theme'
html_theme_options = {{
    'repository_url' : {repo_url!r},
    'use_repository_button' : True,
    'path_to_docs' : '',
    'show_toc_level' : 2,
    #No table of contents to the right of the front page:
    'secondary_sidebar_items' : {{ '**' : [ 'page-toc' ], 'index' : [] }},
}}
html_extra_path = [ '_extra' ]
html_static_path = [ '_static' ]
html_css_files = [ 'ncnb.css' ]
exclude_patterns = [ '_build', '_extra', '_static', '**.ipynb_checkpoints' ]
suppress_warnings = [ 'myst.header', 'mystnb.unknown_mime_type',
                     'misc.highlighting_failure' ]
'''

#Compact layout of the lists of notebooks on the front page, and long text
#outputs of cells in scrollable boxes:
CSS = '''
.cell_output .output.stream pre, .cell_output .output.stderr pre,
.cell_output .output.text_plain pre { max-height: 25em; overflow-y: auto; }
.bd-article section:has(> ul.ncnb-list) > h2 {
  font-size: 1.45rem; margin-top: 1.1em !important;
  margin-bottom: 0.15em !important; }
.bd-article section:has(> ul.ncnb-list) > .toctree-wrapper { display: none; }
p.ncnb-section-desc { margin: 0 0 0.25em 0 !important; font-size: 0.9em;
                      opacity: 0.8; }
ul.ncnb-list { margin: 0 !important; padding-left: 1.3em; }
ul.ncnb-list li { margin: 0.05em 0 !important; }
'''

def write_sources( notebooks, executed, cfg, srcdir, colabdir ):
    """Write the Sphinx sources. executed maps shortkeys to executed notebooks
    (dicts); notebooks which are not in it are included unexecuted."""
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
    shutil.copy( reporoot() / 'devel' / 'site' / 'developers.md',
                 srcdir / 'developers.md' )

    for nb in notebooks:
        sk = nb.settings.shortkey
        page = executed.get(sk)
        if page is None:
            page = expand( nb, cfg, 'site', links_markdown(nb,cfg) )
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

    #The index page, with the notebooks by section:
    lines = [ '# NCrystal notebooks', '',
              ( reporoot() / 'devel' / 'site' / 'index_intro.md'
                ).read_text( encoding = 'utf-8' ).strip(), '' ]
    for section in cfg.sections:
        nbs = [ nb for nb in notebooks if nb.settings.section == section.key ]
        if not nbs:
            continue
        lines += [ f'## {section.title}', '' ]
        #Raw HTML, for a compact layout (see CSS above):
        html = []
        if section.description:
            html.append( '<p class="ncnb-section-desc">'
                         + htmllib.escape(section.description) + '</p>' )
        html.append( '<ul class="ncnb-list">' )
        for nb in nbs:
            html.append( f'<li><a href="notebooks/{nb.settings.shortkey}.html">'
                         + htmllib.escape(nb.settings.title) + '</a></li>' )
        html.append( '</ul>' )
        lines += [ '\n'.join(html), '' ]
        lines += [ '```{toctree}', ':hidden:', f':caption: {section.title}',
                   '' ]
        lines += [ f'notebooks/{nb.settings.shortkey}' for nb in nbs ]
        lines += [ '```', '' ]
    lines += [ '```{toctree}', ':hidden:', ':caption: Development', '',
               'developers', '```', '' ]
    ( srcdir / 'index.md' ).write_text( '\n'.join(lines), encoding = 'utf-8' )

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
