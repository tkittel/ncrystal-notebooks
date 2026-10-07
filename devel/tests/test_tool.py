"""Tests of devel/bin/ncnotebookdevtool (which do not run notebooks)."""

import json

import pytest

from conftest import REPO, make_nb, run_tool, SETTINGS

def test_repository_notebooks_pass_check( monkeypatch ):
    monkeypatch.delenv( 'NCNOTEBOOKDEVTOOL_REPOROOT', raising = False )
    p = run_tool( 'check' )
    assert 'notebooks OK' in p.stdout

def test_usage():
    p = run_tool()
    for mode in ('check','precommit','list','launch','test','site','expand'):
        assert f' {mode} ' in p.stdout

def test_canonical_form_is_idempotent( fakerepo ):
    from ncnb_devtools.nbfile import load, canonical_text
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

@pytest.mark.parametrize( 'settings, error', [
    ( 'x = 1', 'must start with' ),
    ( '# NCrystal notebook settings\n# title: T\n# shortkey: one', 'missing "section"' ),
    ( '# NCrystal notebook settings\n# title: T\n# shortkey: Bad_Key\n# section: basics',
      'invalid shortkey' ),
    ( '# NCrystal notebook settings\n# title: T\n# shortkey: abcdefghijklmno\n# section: basics',
      'invalid shortkey' ),
    ( '# NCrystal notebook settings\n# title: T\n# shortkey: k\n# section: basics\n# foo: bar',
      'unknown key' ),
    ( '# NCrystal notebook settings\n# title: T\n# shortkey: k\n# section: nosuch',
      'unknown section' ),
    ( '# NCrystal notebook settings\n# title: T\n# shortkey: k\n# section: basics\n# requires: nosuch',
      'unknown requirement' ),
    ( '# NCrystal notebook settings\n# title: T\n# shortkey: k\n# section: basics\n# plugins: Nosuch',
      'unknown plugin' ),
    ( '# NCrystal notebook settings\n# title: T\n# shortkey: one\n# section: basics',
      'shortkey "one" is also used' ),
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

def test_list( fakerepo ):
    p = run_tool( 'list' )
    assert 'Basics [basics]' in p.stdout
    assert 'one            Notebook one  [plot]' in p.stdout

def test_expand_and_collapse( fakerepo ):
    from ncnb_devtools.config import load_config
    from ncnb_devtools.nbsettings import find_notebooks, select_notebooks
    from ncnb_devtools.expand import expand, collapse
    from ncnb_devtools.nbfile import canonical_text, source_str
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
        assert source_str( e['cells'][0] ) == '# Notebook one'
        code = source_str( e['cells'][1] )
        assert 'NCrystal notebook settings' not in code
        assert 'NC.test()' in code
    assert 'pip install ncrystal matplotlib' in source_str(
        expand( nb, cfg, 'pip' )['cells'][1] )
    assert '%pip -q install ncrystal matplotlib' in source_str(
        expand( nb, cfg, 'colab' )['cells'][1] )

def _write_params_nb( fakerepo, settings_extra, tags ):
    f = fakerepo / 'notebooks' / 'one.ipynb'
    nb = make_nb( [ ('code', SETTINGS.format( title = 'Notebook one',
                                              key = 'one' ) + settings_extra ),
                    ('code', 'n = 1000000'),
                    ('code', 'print(n)') ] )
    nb['cells'][1]['metadata']['tags'] = tags
    f.write_text( json.dumps(nb) )
    run_tool( 'precommit', check = False )

def test_test_parameters( fakerepo ):
    from ncnb_devtools.config import load_config
    from ncnb_devtools.nbsettings import find_notebooks, select_notebooks
    from ncnb_devtools.expand import expand
    from ncnb_devtools.nbfile import source_str
    _write_params_nb( fakerepo, '\n# test-parameters: n = 1000', ['parameters'] )
    assert 'notebooks OK' in run_tool( 'check' ).stdout
    nb = select_notebooks( ['one'], find_notebooks() )[0]
    assert nb.settings.test_parameters == [ ('n','1000') ]
    cfg = load_config()
    e = expand( nb, cfg, 'test' )
    assert [ source_str(c) for c in e['cells'][1:] ] == [
        'n = 1000000',
        '#Parameters for tests (generated by ncnotebookdevtool):\nn = 1000',
        'print(n)' ]
    for target in ('launch','pip','site'):
        assert not any( 'Parameters for tests' in source_str(c)
                        for c in expand( nb, cfg, target )['cells'] )

@pytest.mark.parametrize( 'extra, tags, error', [
    ( '\n# test-parameters: n = 1000', [], 'exactly one code cell tagged' ),
    ( '\n# test-parameters: m = 1000', ['parameters'], '"m" is not assigned' ),
    ( '\n# test-parameters: 1000', ['parameters'], 'invalid test parameter' ),
] )
def test_test_parameters_errors( fakerepo, extra, tags, error ):
    _write_params_nb( fakerepo, extra, tags )
    p = run_tool( 'check', check = False )
    assert p.returncode != 0 and error in p.stdout

def test_conda_only_requirement( fakerepo ):
    from ncnb_devtools.config import load_config
    from ncnb_devtools.nbsettings import NotebookSettings
    from ncnb_devtools.expand import Requirements
    cfg = load_config()
    s = NotebookSettings( SETTINGS.format( title = 'T', key = 'k' )
                          + ', openmc\n# plugins: Dummy' )
    reqs = Requirements( s, cfg )
    assert reqs.needs_conda
    assert reqs.conda_packages == ['ncrystal','matplotlib-base','openmc']
    assert reqs.plugins == ['ncrystal-plugin-Dummy']

def test_select_by_shortkey_and_path( fakerepo ):
    from ncnb_devtools.nbsettings import find_notebooks, select_notebooks
    nbs = find_notebooks()
    assert [ nb.shortkey for nb in select_notebooks( ['two'], nbs ) ] == ['two']
    p = fakerepo / 'notebooks' / 'one.ipynb'
    assert [ nb.shortkey for nb in select_notebooks( [str(p)], nbs ) ] == ['one']
    with pytest.raises(SystemExit):
        select_notebooks( ['nosuch'], nbs )

def test_expand_mode( fakerepo, tmp_path ):
    out = tmp_path / 'out.ipynb'
    run_tool( 'expand', 'one', '--target', 'colab', '-o', str(out) )
    nb = json.loads( out.read_text() )
    assert ''.join(nb['cells'][0]['source']) == '# Notebook one'

def test_repo_settings_file_loads():
    from ncnb_devtools.config import Config
    cfg = Config( REPO / 'notebook_settings.toml' )
    assert cfg.section('basics') and 'ncrystal' in cfg.requirements
