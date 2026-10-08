"""The settings in notebook_settings.toml."""

from .dirs import settings_file


class ConfigError(RuntimeError):
    pass

_marker_re = __import__('re').compile(
    r'''^\s*sys_platform\s*(==|!=)\s*['"]([a-z0-9]+)['"]\s*$''' )

def conda_package_name( entry, platform ):
    """The package name of a conda package entry, which can have a marker
    (e.g. "openmpi; sys_platform != 'win32'"). Returns None if the marker
    excludes the conda platform (e.g. "win-64"), and the name without marker if
    platform is None."""
    name, _, marker = entry.partition(';')
    name = name.strip()
    if not marker.strip() or platform is None:
        return name
    m = _marker_re.match(marker)
    if not m:
        raise ConfigError(f'unsupported marker in conda package "{entry}"'
                          ' (supported: sys_platform == or != a value)')
    sys_platform = { 'linux' : 'linux', 'osx' : 'darwin',
                     'win' : 'win32' }.get( platform.split('-')[0] )
    return name if ( ( sys_platform == m.group(2) )
                     == ( m.group(1) == '==' ) ) else None

class Requirement:
    def __init__( self, key, data ):
        known = { 'description', 'pip', 'conda', 'conda_pip', 'local',
                  'setup', 'colab_setup', 'conda_platforms' }
        unknown = set(data) - known
        if unknown:
            raise ConfigError(f'requirement "{key}": unknown fields'
                              f' {sorted(unknown)}')
        self.key = key
        self.description = data.get('description',key)
        self.pip = list(data.get('pip',[]))
        self.conda = list(data.get('conda',[]))
        for e in self.conda:
            conda_package_name( e, 'linux-64' )#check syntax
        self.conda_pip = list(data.get('conda_pip',[]))
        self.local = dict(data.get('local',{}))
        #Conda platforms (e.g. "linux-64") on which the conda packages exist (an
        #empty list means all platforms):
        self.conda_platforms = list(data.get('conda_platforms',[]))
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
        import pathlib
        path = path or settings_file()
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib
        with pathlib.Path(path).open('rb') as fh:
            data = tomllib.load(fh)
        unknown = set(data) - {'general','sections','requirements','plugins'}
        if unknown:
            raise ConfigError(f'{path.name}: unknown tables {sorted(unknown)}')
        g = data.get('general',{})
        self.ncrystal_min_version = g.get('ncrystal_min_version','4.0.0')
        self.max_line_length = int(g.get('max_line_length',120))
        self.hide_input_lines = int(g.get('hide_input_lines',60))
        self.max_test_time = int(g.get('max_test_time',40))
        self.max_full_time = int(g.get('max_full_time',40))
        self.max_test_time_slow = int(g.get('max_test_time_slow',500))
        self.max_full_time_slow = int(g.get('max_full_time_slow',900))
        self.min_full_time_slow = int(g.get('min_full_time_slow',10))
        self.windows_time_factor = float(g.get('windows_time_factor',2))
        self.colab_install_time = int(g.get('colab_install_time',180))
        #The repository can be overridden (e.g. for website builds in forks):
        import os
        self.github_repo = ( os.environ.get('NCNOTEBOOKDEVTOOL_GITHUB_REPO')
                             or g.get('github_repo',
                                      'mctools/ncrystal-notebooks') )
        self.colab_branch = g.get('colab_branch','googlecolab')
        self.colab_condacolab = g.get('colab_condacolab','condacolab')
        self.colab_conda_extra = list(g.get('colab_conda_extra',[]))
        #(Forks have their website at https://OWNER.github.io/REPO:)
        if os.environ.get('NCNOTEBOOKDEVTOOL_GITHUB_REPO'):
            owner, repo = self.github_repo.split('/')
            self.website_url = f'https://{owner}.github.io/{repo}'
        else:
            self.website_url = g.get('website_url',
                                     'https://mctools.github.io/ncrystal-notebooks')
        self.website_url = self.website_url.rstrip('/')
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
        return None

    @property
    def ncrystal_min_version_num( self ):
        a,b,c = ( int(e) for e in self.ncrystal_min_version.split('.') )
        return a*1000000 + b*1000 + c

_cache = [None]
def load_config():
    if _cache[0] is None:
        _cache[0] = Config()
    return _cache[0]
