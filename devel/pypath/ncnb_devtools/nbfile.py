"""Reading and writing notebooks in the canonical form used in the repository.

The canonical form is what Jupyter itself writes (JSON with sorted keys and an
indentation of 1, and cell sources as lists of lines), with outputs, execution
counts and non-essential metadata removed. Only the standard library is used,
so this works without Jupyter being installed.
"""

import copy
import hashlib
import json
import re

#The notebook metadata in the canonical form:
CANONICAL_NB_METADATA = {
    'kernelspec' : { 'display_name' : 'Python 3 (ipykernel)',
                     'language' : 'python',
                     'name' : 'python3' },
    'language_info' : { 'name' : 'python' },
}

#Cell metadata kept in the canonical form (everything else is removed):
KEPT_CELL_METADATA = ('tags',)

_cellid_re = re.compile(r'^[a-zA-Z0-9-_]{1,64}$')

class NotebookFormatError(RuntimeError):
    pass

def load( path ):
    """Load a notebook as a dict (raises NotebookFormatError if the file is not
    a notebook of the supported version)."""
    try:
        nb = json.loads(path.read_text(encoding='utf-8'))
    except (UnicodeDecodeError,json.JSONDecodeError) as e:
        raise NotebookFormatError(f'invalid JSON ({e})')
    if not isinstance(nb,dict) or nb.get('nbformat') != 4:
        raise NotebookFormatError('not a notebook in format version 4')
    if not isinstance(nb.get('cells'),list):
        raise NotebookFormatError('no list of cells')
    for c in nb['cells']:
        if c.get('cell_type') not in ('code','markdown','raw'):
            raise NotebookFormatError(f'unknown cell type: {c.get("cell_type")}')
    return nb

def source_str( cell ):
    """The source of a cell as a string."""
    s = cell.get('source','')
    return s if isinstance(s,str) else ''.join(s)

def split_source( s ):
    """A string as a list of lines, as stored in notebook files."""
    return s.splitlines(keepends=True)

def make_cell( cell_type, source, cellid = None ):
    c = { 'cell_type' : cell_type, 'metadata' : {}, 'source' : source }
    if cell_type == 'code':
        c['execution_count'] = None
        c['outputs'] = []
    if cellid:
        c['id'] = cellid
    return c

def canonicalize( nb ):
    """A canonical copy of the notebook (outputs and non-essential metadata
    stripped). Missing cell ids are generated deterministically."""
    out_cells = []
    used_ids = set()
    for i, c in enumerate(nb['cells']):
        ct = c['cell_type']
        src = source_str(c)
        md = { k : copy.deepcopy(v) for k,v in c.get('metadata',{}).items()
               if k in KEPT_CELL_METADATA and v }
        nc = { 'cell_type' : ct, 'metadata' : md, 'source' : split_source(src) }
        if ct == 'code':
            nc['execution_count'] = None
            nc['outputs'] = []
        if ct in ('markdown','raw') and c.get('attachments'):
            nc['attachments'] = copy.deepcopy(c['attachments'])
        cid = c.get('id')
        if not ( isinstance(cid,str) and _cellid_re.match(cid) )\
           or cid in used_ids:
            #Deterministic, so the canonical form is reproducible:
            h = hashlib.sha256(f'{i}:{ct}:{src}'.encode()).hexdigest()
            cid = h[:8]
            while cid in used_ids:
                h = hashlib.sha256(h.encode()).hexdigest()
                cid = h[:8]
        used_ids.add(cid)
        nc['id'] = cid
        out_cells.append(nc)
    return { 'cells' : out_cells,
             'metadata' : copy.deepcopy(CANONICAL_NB_METADATA),
             'nbformat' : 4,
             'nbformat_minor' : 5 }

def dumps( nb ):
    """The notebook as JSON text, formatted as Jupyter writes it."""
    return json.dumps( nb, sort_keys = True, indent = 1,
                       ensure_ascii = False ) + '\n'

def canonical_text( nb ):
    return dumps(canonicalize(nb))

def write( path, nb, canonical = True ):
    path.write_text( canonical_text(nb) if canonical else dumps(nb),
                     encoding = 'utf-8' )
