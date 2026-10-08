#!/bin/bash
# Usage: colab-test.sh IMAGE WORKDIR DATADIR NPARALLEL [TESTARGS...]
#
# Runs the notebooks selected by "ncnotebookdevtool test --colab TESTARGS"
# (e.g. --skip-slow) in Google's Colab runtime image IMAGE, each in its own
# fresh container, so that what one notebook installs (with %pip) can not hide
# a missing requirement of another, as on Google Colab, where every notebook
# starts in a fresh runtime. NPARALLEL containers run at a time.
#
# For each notebook SHORTKEY, the output of the tool is written to
# WORKDIR/SHORTKEY.out and its work directory is WORKDIR/SHORTKEY. Data
# downloaded by the notebooks is cached in DATADIR (shared by the containers).
# Must be run from the top of the repository. Fails if any notebook failed.
set -eu
IMAGE="$1"
WORK="$(realpath "$2")"
DATA="$(realpath "$3")"
NPARALLEL="$4"
shift 4
REPO="$(pwd)"
mkdir -p "$WORK" "$DATA"

python3 devel/bin/ncnotebookdevtool test --colab "$@" \
    --write-selected "$WORK/selected.txt"

run_one() {
    local sk="$1"
    #The packages for running notebooks with nbclient are installed only if
    #the image lacks them:
    if docker run --rm --entrypoint /bin/bash \
        -v "$REPO:/repo" -w /repo \
        -v "$WORK:/work" \
        -v "$DATA:/ncnbdata" -e NCRYSTAL_NOTEBOOK_DATA_CACHE=/ncnbdata \
        "$IMAGE" -c "
          set -eu
          python3 -c 'import nbclient, nbformat, nbconvert, ipykernel' \
            || python3 -m pip install -q nbclient nbformat nbconvert ipykernel
          python3 devel/bin/ncnotebookdevtool test --colab $sk \
            --workdir /work/$sk" > "$WORK/$sk.out" 2>&1; then
        echo OK > "$WORK/$sk.status"
    else
        echo FAILED > "$WORK/$sk.status"
    fi
    echo "  $(cat "$WORK/$sk.status"): $sk"
}
export -f run_one
export IMAGE REPO WORK DATA

n=$(wc -l < "$WORK/selected.txt")
echo "Running $n notebooks, each in a fresh container ($NPARALLEL at a time):"
xargs -P "$NPARALLEL" -I{} bash -c 'run_one "$1"' _ {} < "$WORK/selected.txt"

#Summary, with the times from the output of the tool:
echo
echo "Summary:"
nfail=0
while read -r sk; do
    status=$(cat "$WORK/$sk.status")
    line=$(grep -E "^ncnotebookdevtool:: +(OK|FAILED) +[0-9]+ s +$sk " \
             "$WORK/$sk.out" | sed 's/^ncnotebookdevtool:://' || true)
    echo "${line:-  $status (no time reported)  $sk}"
    [ "$status" = OK ] || nfail=$((nfail+1))
done < "$WORK/selected.txt"
while read -r sk; do
    if [ "$(cat "$WORK/$sk.status")" != OK ]; then
        echo
        echo "===== $sk failed (end of $WORK/$sk.out):"
        tail -n 40 "$WORK/$sk.out"
    fi
done < "$WORK/selected.txt"
if [ "$nfail" -gt 0 ]; then
    echo
    echo "ERROR: $nfail of $n notebooks failed"
    exit 1
fi
echo
echo "All $n notebooks OK"
