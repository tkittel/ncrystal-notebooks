#!/usr/bin/env bash

# Kept for the notebooks workflow of the NCrystal repository, which runs this
# script with NCNOTEBOOKS_USE_NCRYSTAL_REPO set to its NCrystal clone. It runs
# the notebooks which can be installed with pip, with NCrystal built from that
# clone (see devel/bin/ncnotebookdevtool for the full set of options).

set -eu
REPOROOT="$( cd -P "$( dirname "${BASH_SOURCE[0]}" )/../../" && pwd )"
#The tool needs tomllib (Python 3.11) or tomli:
python3 -c 'import tomllib' 2>/dev/null || python3 -m pip install -q tomli
ARGS=( test --select pip --env venv -j 2 )
if [ -n "${NCNOTEBOOKS_USE_NCRYSTAL_REPO:-}" ]; then
    ARGS+=( --ncrystal-src "${NCNOTEBOOKS_USE_NCRYSTAL_REPO}" )
fi
exec python3 "${REPOROOT}/devel/bin/ncnotebookdevtool" "${ARGS[@]}"
