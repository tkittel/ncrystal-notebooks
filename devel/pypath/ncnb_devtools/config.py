"""The settings in notebook_settings.toml."""

from .dirs import settings_file

class ConfigError(RuntimeError):
    pass

class Requirement:
    def __init__( self, key, data ):
        known = { 'description', 'pip', 'conda', 'conda_pip', 'local',
                  'setup', 'colab_setup' }
        unknown = set(data) - known
        if unknown:
            raise ConfigError(f'requirement "{key}": unknown fields'
                              f' {sorted(unknown)}')
        self.key = key
        self.description = data.get('description',key)
        self.pip = list(data.get('pip',[]))
        self.conda = list(data.get('conda',[]))
        self.conda_pip = list(data.get('conda_pip',[]))
        self.local = dict(data.get('local',{}))
        self.setup = data.get('setup','').strip('\n')
        self.colab_setup = data.get('colab_setup','').strip('\n')

    @property
    def pip_available( self ):
        #Requirements without pip packages are only available with conda:
        return bool(self.pip)

class Section:
    def __init__( self, data ):
        for k in ('key','title'):
            if k not in data:
                raise ConfigError(f'section without "{k}": {data}')
        self.key = data['key']
        self.title = data['title']
        self.description = ' '.join(data.get('description','').split())

class Config:
    def __init__( self, path = None ):
        path = path or settings_file()
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib
        with open(path,'rb') as fh:
            data = tomllib.load(fh)
        unknown = set(data) - {'general','sections','requirements','plugins'}
        if unknown:
            raise ConfigError(f'{path.name}: unknown tables {sorted(unknown)}')
        g = data.get('general',{})
        self.ncrystal_min_version = g.get('ncrystal_min_version','4.0.0')
        self.max_line_length = int(g.get('max_line_length',120))
        self.max_test_time = int(g.get('max_test_time',500))
        self.max_full_time = int(g.get('max_full_time',900))
        #The repository can be overridden (e.g. for website builds in forks):
        import os
        self.github_repo = ( os.environ.get('NCNOTEBOOKDEVTOOL_GITHUB_REPO')
                             or g.get('github_repo','mctools/ncrystal-notebooks') )
        self.colab_branch = g.get('colab_branch','googlecolab')
        self.website_url = g.get('website_url','')
        self.sections = [ Section(s) for s in data.get('sections',[]) ]
        keys = [ s.key for s in self.sections ]
        if len(set(keys)) != len(keys):
            raise ConfigError('duplicate section keys')
        self.requirements = { k : Requirement(k,v) for k,v
                              in data.get('requirements',{}).items() }
        if 'ncrystal' not in self.requirements:
            raise ConfigError('requirement "ncrystal" must be defined')
        self.plugins = dict(data.get('plugins',{}))

    def section( self, key ):
        for s in self.sections:
            if s.key == key:
                return s

    @property
    def ncrystal_min_version_num( self ):
        a,b,c = ( int(e) for e in self.ncrystal_min_version.split('.') )
        return a*1000000 + b*1000 + c

_cache = [None]
def load_config():
    if _cache[0] is None:
        _cache[0] = Config()
    return _cache[0]
