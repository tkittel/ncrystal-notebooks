_nndc_source = 'https://anl.box.com/shared/static/teaup95cqv8s9nn56hfn7ku8mmelr95p.xz'

def download_and_prepare_nndc_data():
    """Download and extract the NNDC nuclear data library for OpenMC into
    ./nndc_hdf5, and return the path to its cross_sections.xml file.

    If the environment variable NCRYSTAL_NOTEBOOK_DATA_CACHE is set to a
    directory, the extracted library is kept there and reused (hardlinked if
    possible) on later calls, avoiding repeated downloads (used when testing
    the notebooks)."""
    import pathlib
    import os
    print( 'Getting NNDX data for OpenMC from source:')
    print(f'  {_nndc_source}')
    openmc_xsfile = pathlib.Path('./nndc_hdf5/cross_sections.xml')
    cachedir = os.environ.get('NCRYSTAL_NOTEBOOK_DATA_CACHE')
    if openmc_xsfile.is_file():
        print("... Already downloaded and extracted!")
    elif cachedir:
        cached = _cached_nndc_data( pathlib.Path(cachedir) / 'nndc' )
        print(f"... Using cached copy in {cached}")
        _link_tree( cached, openmc_xsfile.parent )
    else:
        _download_and_extract( pathlib.Path('.') )
    if not openmc_xsfile.is_file():
        raise RuntimeError(f"Did not find expected file: {openmc_xsfile}")
    print(f"OpenMC cross section file prepared in {openmc_xsfile}")
    return openmc_xsfile

def _download_and_extract( destdir ):
    from .download import extract_archive, download_file
    print("... Downloading (this might take a minute)...")
    f = download_file( _nndc_source,
                       tgt_path = destdir / _nndc_source.split('/')[-1],
                       skip_if_exists = True, quiet = True )
    print("... Extracting (this might take a minute)...")
    extract_archive( f, destdir, quiet = True )
    return f

def _cached_nndc_data( cachedir ):
    #Extract into a temporary directory which is then renamed, so concurrent
    #processes never see an incomplete cache:
    import os
    import pathlib
    import shutil
    import tempfile
    tgt = cachedir / 'nndc_hdf5'
    if not ( tgt / 'cross_sections.xml' ).is_file():
        cachedir.mkdir( parents = True, exist_ok = True )
        tmpdir = pathlib.Path( tempfile.mkdtemp( dir = cachedir ) )
        try:
            f = _download_and_extract( tmpdir )
            f.unlink()
            try:
                os.rename( tmpdir / 'nndc_hdf5', tgt )
            except OSError:
                if not ( tgt / 'cross_sections.xml' ).is_file():
                    raise
        finally:
            shutil.rmtree( tmpdir, ignore_errors = True )
    return tgt

def _link_tree( src, dest ):
    #Hardlink files (copying if not possible). The cross_sections.xml file is
    #always copied, since notebooks might modify it in place:
    import os
    import shutil
    for root, dirs, files in os.walk(src):
        d = dest / os.path.relpath( root, src )
        d.mkdir( parents = True, exist_ok = True )
        for fn in files:
            if fn.endswith('.xml'):
                shutil.copy2( os.path.join(root,fn), d / fn )
                continue
            try:
                os.link( os.path.join(root,fn), d / fn )
            except OSError:
                shutil.copy2( os.path.join(root,fn), d / fn )
