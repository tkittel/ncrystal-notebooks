# ncrystal-notebooks

Jupyter notebooks with examples, documentation and tutorials for
[NCrystal](https://github.com/mctools/ncrystal).

The notebooks are best browsed on the website, where each of them can also be
downloaded (in versions for installations with pip or conda) or opened
directly in Google Colab:

**https://mctools.github.io/ncrystal-notebooks**

## For developers

Contributions of new notebooks are very welcome. The notebooks are maintained
with the `devel/bin/ncnotebookdevtool` command (run it without arguments for
usage). In short:

```
. devel/setup.sh                     # add ncnotebookdevtool to your PATH
ncnotebookdevtool list               # list the notebooks
ncnotebookdevtool launch SHORTKEY    # edit a notebook in Jupyter Lab
ncnotebookdevtool precommit          # run before each commit
ncnotebookdevtool test [SHORTKEY]    # run notebooks as in CI
```

See the [developer section](https://mctools.github.io/ncrystal-notebooks/developers.html)
of the website (or [devel/site/developers.md](devel/site/developers.md)) for
details, including how notebooks declare their requirements in their first
cell, and how to test them with a local clone of the NCrystal repository.
