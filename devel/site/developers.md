# Developing notebooks

This page is for people who want to edit the notebooks or contribute new ones.
All notebooks live in the `notebooks/` directory of the
[ncrystal-notebooks](https://github.com/mctools/ncrystal-notebooks) repository,
and are maintained with the `ncnotebookdevtool` command in that repository.

## Getting started

Clone the repository, and add the tool to your `PATH` (in bash or zsh):

```
git clone https://github.com/mctools/ncrystal-notebooks.git
cd ncrystal-notebooks
. devel/setup.sh
ncnotebookdevtool
```

Running `ncnotebookdevtool` without arguments lists the available modes, and
`ncnotebookdevtool MODE --help` describes each of them. The tool needs Python
3.10 or later, and (for running notebooks) either pip or conda (mamba,
micromamba or conda).

## The settings cell

Every notebook starts with a *settings cell*: a code cell with only comments,
declaring what the notebook is and what it needs. For example:

```python
# NCrystal notebook settings
# title: Compose materials from structures in CIF files and databases
# shortkey: cif
# section: materials
# requires: plot, cif
```

The keys are:

* `title`: The title of the notebook (do not add another title heading in the
  notebook).
* `shortkey`: A short unique key, of at most 14 lowercase letters or digits.
  It is used in URLs (so it should never change) and on the command line.
* `section`: The section of the website in which the notebook is listed.
* `requires`: What the notebook needs besides NCrystal, e.g. `plot` for
  matplotlib, `cif` for CIF file support, or `openmc` for OpenMC.
* `plugins`: NCrystal plugins needed by the notebook.
* `import-ncrystal`: Set to `no` if the notebook should not have NCrystal
  imported for it, e.g. because it installs plugins before importing NCrystal.
* `max-line-length`: Maximum length of lines in code cells, if the default (120
  characters) is not suitable, e.g. for embedded data.
* `timeout`: Timeout in seconds for running the notebook, if the default is not
  suitable.
* `test-parameters`: Values used when testing, e.g. to reduce statistics in
  notebooks which take a long time to run (`# test-parameters: n = 1000; m = 2`).
  The notebook must then put these numbers in a single code cell, tagged
  `parameters` (in Jupyter Lab: the cog icon in the right sidebar, "Add Tag"),
  and use the variables in the rest of the notebook. When testing, the test
  values are assigned in a new cell right after the tagged one, while users and
  the website see the original values.

The available sections, requirements and plugins are defined in
`notebook_settings.toml` at the top of the repository. A requirement can
provide packages for pip and conda, and setup code. Requirements without pip
packages (like `openmc`) are only available with conda.

Do not add code for installing software, setting up plots, or importing
NCrystal: the tool generates this from the settings cell, in different
versions for different purposes (running the notebook in tests, the website,
the downloadable notebooks for pip and conda, and Google Colab). So when a
better way of installing something on Google Colab is found, only the tool
needs to change, not every notebook.

## Editing a notebook

The easiest way to edit a notebook is:

```
ncnotebookdevtool launch SHORTKEY
```

This opens the notebook in Jupyter Lab, running in a fresh directory and in an
environment with everything the notebook needs, created and cached by the tool
(`--env current` uses your current environment instead, without modifying it).
The settings cell is expanded with the setup code (below a marker line, which
must not be edited). When you are done, stop Jupyter Lab with Ctrl-C in the
terminal. The notebook is then written back into the repository, with the
settings cell restored and outputs removed, and the previous version is kept
as `NOTEBOOK.ipynb.orig`.

To add a new notebook, create it in the right place under `notebooks/` with a
settings cell as its first cell (copy one from another notebook), and use
`launch` to edit it.

## Before committing

Notebooks are committed without outputs, and in a canonical format which keeps
diffs readable. Before each commit, run:

```
ncnotebookdevtool precommit
```

This brings all notebooks into the canonical form and checks them (it is fast,
and does not run them). The same checks run in CI, and fail if a notebook is
not in canonical form.

## Running the notebooks

To run notebooks as in CI:

```
ncnotebookdevtool test [SHORTKEY ...]
```

Each notebook runs in a fresh directory, with a fresh kernel, in an
environment providing its requirements: a venv for notebooks which can be
installed with pip, and a conda environment for the others. All notebooks are
run if none are given. Useful options are `-j N` to run notebooks in parallel,
`--env` to choose the kind of environments, and `--select pip` or
`--select conda`.

To test notebooks with the NCrystal code in a local clone of the NCrystal
repository (instead of the released NCrystal), add
`--ncrystal-src /path/to/ncrystal` (this also works with `launch`). NCrystal is
then built from that clone, and the tool verifies that the notebooks really use
it.

## The website

The website is built in CI from the main branch and published on GitHub
Pages. All notebooks are run for it, and the versions of the notebooks for
download and for Google Colab are generated at the same time. To build it
locally:

```
ncnotebookdevtool site -o /some/dir
```

(add `--no-execute` for a quick build without running the notebooks).
