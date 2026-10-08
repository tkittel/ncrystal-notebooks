"""Tests of devel/bin/ncnotebookdevtool (which do not run notebooks)."""

import json
import shutil

import pytest
from conftest import INTRO, REPO, SETTINGS, make_nb, run_tool


def test_repository_notebooks_pass_check( monkeypatch ):
    monkeypatch.delenv( 'NCNOTEBOOKDEVTOOL_REPOROOT', raising = False )
    p = run_tool( 'check' )
    assert 'notebooks OK' in p.stdout

def test_usage():
    p = run_tool()
    for mode in ('check','precommit','list','launch','test','site','expand',
                 'createnew'):
        assert f' {mode} ' in p.stdout

def test_canonical_form_is_idempotent( fakerepo ):
    from ncnb_devtools.nbfile import canonical_text, load
    f = fakerepo / 'notebooks' / 'one.ipynb'
    t1 = f.read_text()
    assert canonical_text( load(f) ) == t1
    nb = json.loads(t1)
    assert nb['metadata']['kernelspec']['name'] == 'python3'
    assert all( 'id' in c for c in nb['cells'] )
    assert nb['cells'][0]['source'][0] == '# NCrystal notebook settings\n'

def test_precommit_strips_outputs_and_metadata( fakerepo ):
    f = fakerepo / 'notebooks' / 'one.ipynb'
    nb = json.loads( f.read_text() )
    canonical = f.read_text()
    nb['cells'][2]['outputs'] = [ { 'output_type' : 'stream', 'name' : 'stdout',
                                    'text' : ['hello\n'] } ]
    nb['cells'][2]['execution_count'] = 3
    nb['cells'][1]['metadata'] = { 'colab' : { 'x' : 1 }, 'tags' : ['keep'] }
    nb['metadata']['colab'] = { 'provenance' : [] }
    f.write_text( json.dumps(nb, indent = 2) )
    p = run_tool( 'check', check = False )
    assert p.returncode != 0 and 'not in canonical form' in p.stdout
    p = run_tool( 'precommit' )
    assert 'Updated notebooks/one.ipynb' in p.stdout
    nb2 = json.loads( f.read_text() )
    assert nb2['cells'][2]['outputs'] == []
    assert nb2['cells'][2]['execution_count'] is None
    assert nb2['cells'][1]['metadata'] == { 'tags' : ['keep'] }
    assert 'colab' not in nb2['metadata']
    del nb2['cells'][1]['metadata']['tags']
    assert json.dumps(nb2,indent=1,sort_keys=True,ensure_ascii=False)+'\n' \
        == canonical

#The start of the settings cells in test_settings_errors:
_HDR = '# NCrystal notebook settings\n# title: T\n# menutitle: M\n'

@pytest.mark.parametrize( 'settings, error', [
    ( 'x = 1', 'must start with' ),
    ( _HDR + '# shortkey: one', 'missing "section"' ),
    ( _HDR + '# shortkey: Bad_Key\n# section: basics',
      'invalid shortkey' ),
    ( _HDR + '# shortkey: abcdefghijklmno\n# section: basics',
      'invalid shortkey' ),
    ( _HDR + '# shortkey: k\n# section: basics\n# foo: bar',
      'unknown key' ),
    ( _HDR + '# shortkey: k\n# section: nosuch',
      'unknown section' ),
    ( _HDR + '# shortkey: k\n# section: basics\n# requires: nosuch',
      'unknown requirement' ),
    ( _HDR + '# shortkey: k\n# section: basics\n# plugins: Nosuch',
      'unknown plugin' ),
    ( _HDR + '# shortkey: one\n# section: basics',
      'shortkey "one" is also used' ),
    ( '# NCrystal notebook settings\n# title: T\n# shortkey: k\n'
      '# section: basics', 'missing "menutitle"' ),
    ( '# NCrystal notebook settings\n# title: T\n# menutitle: ' + 'x'*31
      + '\n# shortkey: k\n# section: basics', 'longer than 30 characters' ),
    ( '# NCrystal notebook settings\n# title: T\n# menutitle: Menu Notebook one'
      '\n# shortkey: k\n# section: basics',
      'menutitle "Menu Notebook one" is also used' ),
] )
def test_settings_errors( fakerepo, settings, error ):
    nb = make_nb( [ ('code', settings), ('markdown','text') ] )
    ( fakerepo / 'notebooks' / 'bad.ipynb' ).write_text( json.dumps(nb) )
    run_tool( 'precommit', check = False )
    p = run_tool( 'check', check = False )
    assert p.returncode != 0
    assert error in p.stdout, p.stdout

def test_missing_settings_cell( fakerepo ):
    nb = make_nb( [ ('markdown','# A title'), ('code','x=1') ] )
    ( fakerepo / 'notebooks' / 'bad.ipynb' ).write_text( json.dumps(nb) )
    p = run_tool( 'check', check = False )
    assert p.returncode != 0 and 'first cell must be a code cell' in p.stdout

def test_line_length( fakerepo ):
    f = fakerepo / 'notebooks' / 'two.ipynb'
    nb = json.loads( f.read_text() )
    nb['cells'][2]['source'] = [ 'y = ' + '1+'*30 + '1' ]
    f.write_text( json.dumps(nb) )
    run_tool( 'precommit', check = False )
    p = run_tool( 'check', check = False )
    assert 'longer than 40 characters' in p.stdout
    #Allowed with max-line-length in the settings cell:
    nb = json.loads( f.read_text() )
    nb['cells'][0]['source'].append('\n# max-line-length: 100')
    f.write_text( json.dumps(nb) )
    run_tool( 'precommit' )

@pytest.mark.usefixtures('fakerepo')
def test_list():
    p = run_tool( 'list' )
    assert 'Basics [basics]' in p.stdout
    assert 'one            Notebook one  [plot]' in p.stdout

@pytest.mark.usefixtures('fakerepo')
def test_expand_and_collapse():
    from ncnb_devtools.config import load_config
    from ncnb_devtools.expand import LOGO_HTML, collapse, expand
    from ncnb_devtools.nbfile import canonical_text, source_str
    from ncnb_devtools.nbsettings import find_notebooks, select_notebooks
    cfg = load_config()
    nb = select_notebooks( ['one'], find_notebooks() )[0]
    original = nb.path.read_text()
    for target in ('test','launch'):
        e = expand( nb, cfg, target )
        src = source_str( e['cells'][0] )
        assert 'import NCrystal as NC' in src
        assert '%matplotlib ' + ( 'ipympl' if target == 'launch'
                                  else 'inline' ) in src
        assert collapse( e )
        assert canonical_text( e ) == original
    for target in ('pip','conda','colab','site'):
        e = expand( nb, cfg, target )
        #The logo is shown next to the title, except on the website (which
        #shows it in the sidebar):
        logo = '' if target == 'site' else LOGO_HTML + '\n\n'
        assert source_str( e['cells'][0] ) == logo + '# Notebook one'
        code = source_str( e['cells'][1] )
        assert 'NCrystal notebook settings' not in code
        assert 'NC.test()' in code
    assert 'pip install ncrystal matplotlib' in source_str(
        expand( nb, cfg, 'pip' )['cells'][1] )
    assert '%pip -q install ncrystal matplotlib' in source_str(
        expand( nb, cfg, 'colab' )['cells'][1] )

def _write_params_nb( fakerepo, settings_extra, tags = (),
                      code = ( 'n = 1000000', 'print(n)' ) ):
    f = fakerepo / 'notebooks' / 'one.ipynb'
    nb = make_nb( [ ('code', SETTINGS.format( title = 'Notebook one',
                                              key = 'one' ) + settings_extra ),
                    ('markdown', INTRO) ] + [ ('code', c) for c in code ] )
    if tags:
        nb['cells'][2]['metadata']['tags'] = list(tags)
    f.write_text( json.dumps(nb) )
    run_tool( 'precommit', check = False )

def test_test_parameters( fakerepo ):
    from ncnb_devtools.config import load_config
    from ncnb_devtools.expand import expand
    from ncnb_devtools.nbfile import source_str
    from ncnb_devtools.nbsettings import find_notebooks, select_notebooks
    _write_params_nb( fakerepo, '\n# test-parameters: n = 1000' )
    assert 'notebooks OK' in run_tool( 'check' ).stdout
    nb = select_notebooks( ['one'], find_notebooks() )[0]
    assert nb.settings.test_parameters == [ ('n','1000') ]
    cfg = load_config()
    e = expand( nb, cfg, 'test' )
    assert [ source_str(c) for c in e['cells'][1:] ] == [
        INTRO,
        'n = 1000000',
        '#Parameters for tests (generated by ncnotebookdevtool):\nn = 1000',
        'print(n)' ]
    for target in ('launch','pip','site','colab'):
        assert not any( 'Parameters for tests' in source_str(c)
                        for c in expand( nb, cfg, target )['cells'] )
    #The version for tests in Google's Colab runtime image: the Colab version
    #with the test parameters:
    e = expand( nb, cfg, 'colabtest' )
    srcs = [ source_str(c) for c in e['cells'] ]
    assert '%pip -q install' in srcs[1]
    assert srcs[2:] == [
        '<a id="one-intro"></a>\n\n## Introduction\nSome text.',
        'n = 1000000',
        '#Parameters for tests (generated by ncnotebookdevtool):\nn = 1000',
        'print(n)' ]

@pytest.mark.parametrize( 'extra, tags, error', [
    ( '\n# test-parameters: n = 1000', ['parameters'], 'no longer used' ),
    ( '\n# test-parameters: m = 1000', [], '"m" is not assigned' ),
    ( '\n# test-parameters: 1000', [], 'invalid test parameter' ),
] )
def test_test_parameters_errors( fakerepo, extra, tags, error ):
    _write_params_nb( fakerepo, extra, tags )
    p = run_tool( 'check', check = False )
    assert p.returncode != 0 and error in p.stdout

@pytest.mark.usefixtures('fakerepo')
def test_conda_only_requirement():
    from ncnb_devtools.config import load_config
    from ncnb_devtools.expand import Requirements
    from ncnb_devtools.nbsettings import NotebookSettings
    cfg = load_config()
    s = NotebookSettings( SETTINGS.format( title = 'T', key = 'k' )
                          + ', openmc\n# plugins: Dummy' )
    reqs = Requirements( s, cfg )
    assert reqs.needs_conda
    assert reqs.conda_packages == ['ncrystal','matplotlib','openmc']
    assert reqs.plugins == ['ncrystal-plugin-Dummy']

def test_select_by_shortkey_and_path( fakerepo ):
    from ncnb_devtools.nbsettings import find_notebooks, select_notebooks
    nbs = find_notebooks()
    assert [ nb.shortkey for nb in select_notebooks( ['two'], nbs ) ] == ['two']
    p = fakerepo / 'notebooks' / 'one.ipynb'
    assert ( [ nb.shortkey for nb in select_notebooks( [str(p)], nbs ) ]
             == ['one'] )
    with pytest.raises(SystemExit):
        select_notebooks( ['nosuch'], nbs )

@pytest.mark.usefixtures('fakerepo')
def test_expand_mode( tmp_path ):
    from ncnb_devtools.expand import LOGO_HTML
    out = tmp_path / 'out.ipynb'
    run_tool( 'expand', 'one', '--target', 'colab', '-o', str(out) )
    nb = json.loads( out.read_text() )
    assert ''.join(nb['cells'][0]['source']) == ( LOGO_HTML + '\n\n'
                                                  + '# Notebook one' )

def test_repo_settings_file_loads():
    from ncnb_devtools.config import Config
    cfg = Config( REPO / 'notebook_settings.toml' )
    assert cfg.section('basics') and 'ncrystal' in cfg.requirements

def test_conda_platforms():
    import types

    from ncnb_devtools.config import Requirement
    from ncnb_devtools.envsetup import conda_platform
    from ncnb_devtools.expand import Requirements
    assert conda_platform().split('-')[0] in ('linux','osx','win')
    cfg = types.SimpleNamespace(
        requirements = { 'ncrystal' : Requirement( 'ncrystal',
                                                   { 'pip' : ['ncrystal'] } ),
                         'x' : Requirement( 'x', { 'conda' : ['x'],
                                                   'conda_platforms' :
                                                   ['linux-64'] } ) },
        plugins = {} )
    s = types.SimpleNamespace( requires = ['x'], plugins = [] )
    r = Requirements( s, cfg )
    assert r.unavailable_with_conda('linux-64') == []
    assert r.unavailable_with_conda('osx-arm64') == ['x']

def test_hidden_input( fakerepo ):
    from ncnb_devtools.config import load_config
    from ncnb_devtools.expand import expand
    from ncnb_devtools.nbsettings import find_notebooks, select_notebooks
    f = fakerepo / 'notebooks' / 'one.ipynb'
    nb = make_nb( [ ('code', SETTINGS.format( title = 'Notebook one',
                                              key = 'one' ) ),
                    ('markdown', INTRO),
                    ('code', 'x = 1'),
                    ('code', 'y = 2'),
                    ('code', '\n'.join( f'a{i} = {i}' for i in range(100) ) ),
                    ('code', '\n'.join( f'b{i} = {i}' for i in range(100) ) ) ]
                  )
    nb['cells'][3]['metadata']['tags'] = ['hide-input']
    nb['cells'][5]['metadata']['tags'] = ['show-input']
    f.write_text( json.dumps(nb) )
    run_tool( 'precommit' )
    cfg = load_config()
    nbobj = select_notebooks( ['one'], find_notebooks() )[0]
    for target in ('site','pip','conda','colab'):
        cells = [ c for c in expand( nbobj, cfg, target )['cells']
                  if ''.join(c['source']) == 'x = 1'
                  or ''.join(c['source']).startswith(('y =','a0 =','b0 =')) ]
        hidden = [ c['metadata'].get('jupyter',{}).get('source_hidden',False)
                   and 'hide-input' in c['metadata'].get('tags',[])
                   for c in cells ]
        assert hidden == [ False, True, True, False ]
    for target in ('test','launch'):
        assert not any( c['metadata'].get('jupyter')
                        for c in expand( nbobj, cfg, target )['cells'] )

def test_createnew( fakerepo ):
    args = [ 'createnew', '--title', 'A new notebook', '--menutitle', 'New',
             '--shortkey', 'newnb',
             '--section', 'basics', '--requires', 'plot', '--plugins', 'none' ]
    p = run_tool( *args )
    assert 'launch newnb' in p.stdout
    f = fakerepo / 'notebooks' / 'newnb' / 'newnb.ipynb'
    assert f.is_file()
    assert 'notebooks OK' in run_tool( 'check' ).stdout
    assert 'newnb          A new notebook' in run_tool( 'list' ).stdout
    #Errors: existing shortkey, unknown section, missing option:
    for change, err in [ ( {}, 'already used' ),
                         ( { '--shortkey' : 'other', '--title' : 'Other',
                             '--menutitle' : 'Other',
                             '--section' : 'nosuch' }, 'Unknown section' ),
                         ( { '--shortkey' : 'other', '--title' : None },
                           'provide the --title option' ),
                         ( { '--shortkey' : 'other', '--title' : 'Other' },
                           'menu title is already used' ),
                         ( { '--shortkey' : 'other', '--title' : 'Other',
                             '--menutitle' : None },
                           'provide the --menutitle option' ) ]:
        a = list(args)
        for k, v in change.items():
            i = a.index(k)
            if v is None:
                del a[i:i+2]
            else:
                a[i+1] = v
        p = run_tool( *a, check = False )
        assert p.returncode != 0 and err in ( p.stdout + p.stderr )

def test_slow_setting( fakerepo ):
    f = fakerepo / 'notebooks' / 'one.ipynb'
    nb = json.loads( f.read_text() )
    nb['cells'][0]['source'].append('\n# slow: yes')
    f.write_text( json.dumps(nb) )
    run_tool( 'precommit' )
    assert 'Notebook one  [plot, slow]' in run_tool( 'list' ).stdout
    nb['cells'][0]['source'][-1] = '\n# slow: maybe'
    f.write_text( json.dumps(nb) )
    p = run_tool( 'check', check = False )
    assert p.returncode != 0 and 'slow must be "yes" or "no"' in p.stdout

@pytest.mark.usefixtures('fakerepo')
def test_only_slow_and_skip_slow_conflict():
    p = run_tool( 'test', '--only-slow', '--skip-slow', check = False )
    assert p.returncode != 0 and 'can not be combined' in p.stderr

@pytest.mark.usefixtures('fakerepo')
def test_notebook_selection_in_quick_modes():
    assert 'All 1 notebook OK' in run_tool( 'check', 'one' ).stdout
    assert 'All 1 notebook OK' in run_tool( 'precommit', 'two' ).stdout
    out = run_tool( 'list', 'two' ).stdout
    assert 'Notebook two' in out and 'Notebook one' not in out
    p = run_tool( 'check', 'nosuchkey', check = False )
    assert p.returncode != 0 and 'Unknown notebook' in ( p.stdout + p.stderr )

def test_settings_tables_in_developer_docs():
    from ncnb_devtools.config import Config
    from ncnb_devtools.site import (
        SETTINGS_TABLES_MARKER,
        settings_tables_markdown,
    )
    doc = ( REPO / 'devel' / 'site' / 'developers.md' ).read_text()
    assert doc.count( SETTINGS_TABLES_MARKER ) == 1
    cfg = Config( REPO / 'notebook_settings.toml' )
    md = settings_tables_markdown( cfg )
    for key in list(cfg.requirements) + list(cfg.plugins):
        if key != 'ncrystal':
            assert f'| `{key}` |' in md

def _write_md_nb( fakerepo, md ):
    f = fakerepo / 'notebooks' / 'one.ipynb'
    nb = make_nb( [ ('code', SETTINGS.format( title = 'Notebook one',
                                              key = 'one' ) ),
                    ('markdown', INTRO),
                    ('markdown', md) ] )
    f.write_text( json.dumps(nb) )
    run_tool( 'precommit', check = False )

@pytest.mark.parametrize( 'md, error', [
    ( '## Results', 'no key at the end' ),
    ( '## Results [Results]', 'invalid key "Results"' ),
    ( '## Results [r123456789x]', 'invalid key "r123456789x"' ),
    ( '## Results [1abc]', 'invalid key "1abc"' ),
    ( '## Results [re-s]', 'invalid key "re-s"' ),
    ( '## A [a]\n\n### B [a]', 'the key "a" is also used' ),
    ( '# Results [res]', 'single #' ),
    ( '#### Details [det]', 'only ## and ### headings have keys' ),
    ( 'See [here](#nosuch).\n\n## Results [res]', 'link to "#nosuch"' ),
] )
def test_heading_key_errors( fakerepo, md, error ):
    _write_md_nb( fakerepo, md )
    p = run_tool( 'check', check = False )
    assert p.returncode != 0 and error in p.stdout

def test_heading_keys( fakerepo ):
    from ncnb_devtools.config import load_config
    from ncnb_devtools.expand import expand
    from ncnb_devtools.nbfile import source_str
    from ncnb_devtools.nbsettings import find_notebooks, select_notebooks
    md = ( 'See [the results](#res).\n## Results [res] ##\n\n#### Details\n\n'
           '```\n## code [x]\n```' )
    _write_md_nb( fakerepo, md )
    assert 'notebooks OK' in run_tool( 'check' ).stdout
    nb = select_notebooks( ['one'], find_notebooks() )[0]
    cfg = load_config()
    def last( target ):
        return source_str( expand( nb, cfg, target )['cells'][-1] )
    #Unchanged for running and editing:
    assert last('test') == md
    assert last('launch') == md
    #In the versions for users, the keys become anchors with ids (with the
    #shortkey of the notebook), which links to sections use:
    rest = '## Results\n\n#### Details\n\n```\n## code [x]\n```'
    assert last('site') == ( 'See [the results](#one-res).\n\n{#one-res}\n'
                             + rest )
    for target in ('pip','conda','colab','colabtest'):
        assert last(target) == ( 'See [the results](#one-res).\n\n'
                                 '<a id="one-res"></a>\n\n' + rest )

@pytest.mark.usefixtures('fakerepo')
def test_time_limits_are_whole_seconds( monkeypatch ):
    #The time limits are passed to _nbexec.py, which needs whole seconds (also
    #on Windows, where they are multiplied by windows_time_factor):
    import sys
    import types

    from ncnb_devtools.batch import time_limits
    from ncnb_devtools.config import load_config
    cfg = load_config()
    args = types.SimpleNamespace( time_limit = None )
    for platform in ('linux','win32'):
        monkeypatch.setattr( sys, 'platform', platform )
        for target in ('test','colabtest','site'):
            for slow in (False,True):
                limit, _ = time_limits( args, cfg, target, slow )
                assert isinstance( limit, int ), (platform,target,slow,limit)
    monkeypatch.setattr( sys, 'platform', 'win32' )
    cfg.windows_time_factor = 1.5
    assert time_limits( args, cfg, 'test', False )[0] == 60

def test_test_parameters_in_several_cells( fakerepo ):
    from ncnb_devtools.config import load_config
    from ncnb_devtools.expand import expand
    from ncnb_devtools.nbfile import source_str
    from ncnb_devtools.nbsettings import find_notebooks, select_notebooks
    #Assigned in more than one cell:
    _write_params_nb( fakerepo, '\n# test-parameters: n = 1000',
                      code = ( 'n = 1000000', 'n = 2000000', 'print(n)' ) )
    p = run_tool( 'check', check = False )
    assert p.returncode != 0
    assert 'assigned in more than one code cell' in p.stdout
    #Different parameters in different cells (not "n == 1", a comparison), get
    #their test values after their own cells:
    _write_params_nb( fakerepo, '\n# test-parameters: n = 10; m = 20',
                      code = ( 'n = 1000\nprint(n == 1)', 'm = 2000',
                               'print(n,m)' ) )
    assert 'notebooks OK' in run_tool( 'check' ).stdout
    nb = select_notebooks( ['one'], find_notebooks() )[0]
    e = expand( nb, load_config(), 'test' )
    head = '#Parameters for tests (generated by ncnotebookdevtool):\n'
    assert [ source_str(c) for c in e['cells'][2:] ] == [
        'n = 1000\nprint(n == 1)', head + 'n = 10', 'm = 2000', head + 'm = 20',
        'print(n,m)' ]
    assert len( { c['id'] for c in e['cells'] } ) == len( e['cells'] )

@pytest.mark.skipif( shutil.which('ruff') is None, reason = 'needs ruff' )
def test_lint( fakerepo ):
    #The generated setup code is included (no "undefined name NC"):
    assert 'Lint OK' in run_tool( 'lint' ).stdout
    #A problem in a notebook is reported for its path in the repository:
    _write_md_nb( fakerepo, 'Text' )
    f = fakerepo / 'notebooks' / 'one.ipynb'
    nb = json.loads( f.read_text() )
    nb['cells'].append( make_nb( [ ('code', 'x = None\nprint(x == None)') ]
                                 )['cells'][0] )
    f.write_text( json.dumps(nb) )
    run_tool( 'precommit', check = False )
    p = run_tool( 'lint', check = False )
    assert p.returncode != 0
    assert 'notebooks/one.ipynb:cell 4:2:12: E711' in p.stdout
    #Packages imported but not used are fine in notebooks:
    nb['cells'][-1] = make_nb( [ ('code', 'import os') ] )['cells'][0]
    f.write_text( json.dumps(nb) )
    run_tool( 'precommit', check = False )
    assert 'Lint OK' in run_tool( 'lint' ).stdout
