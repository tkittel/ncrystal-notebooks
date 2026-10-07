"""Locations in the repository."""

import os
import pathlib

def reporoot():
    #Can be overridden, e.g. when testing the tool itself:
    override = os.environ.get('NCNOTEBOOKDEVTOOL_REPOROOT')
    if override:
        return pathlib.Path(override).absolute()
    return pathlib.Path(__file__).resolve().parent.parent.parent.parent

def notebooks_dir():
    return reporoot() / 'notebooks'

def settings_file():
    return reporoot() / 'notebook_settings.toml'

def codcache_dir():
    #Cached files from the Crystallography Open Database, so notebooks do not
    #depend on downloads from it when tested:
    return reporoot() / 'devel' / 'codcache'

def cache_dir():
    #Cache of environments etc., outside the repository:
    d = os.environ.get('NCNOTEBOOKDEVTOOL_CACHEDIR')
    if d:
        return pathlib.Path(d).absolute()
    base = os.environ.get('XDG_CACHE_HOME') or pathlib.Path.home() / '.cache'
    return pathlib.Path(base) / 'ncnotebookdevtool'
