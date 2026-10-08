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

## Editing a notebook

Editing a notebook is much like editing any other notebook in Jupyter Lab. Just
a few things are special: the first cell of every notebook is a
[settings cell](#the-settings-cell), with information about the notebook (like
its title and what it needs), section headings end with a short key in
brackets (see [Section headings](#section-headings)), and before committing
anything you must always run a command which cleans up the notebooks (see
[Before committing](#before-committing)).

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

To add a new notebook, run:

```
ncnotebookdevtool createnew
```

This asks for the title, menu title, shortkey, section, requirements and
plugins of the notebook, creates it with its settings cell (by default as
`notebooks/SHORTKEY/SHORTKEY.ipynb`), and tells you how to `launch` it for
editing.

## The settings cell

Every notebook starts with a *settings cell*: a code cell with only comments,
declaring what the notebook is and what it needs. For example:

```python
# NCrystal notebook settings
# title: Compose materials from structures in CIF files and databases
# menutitle: Materials from CIF files
# shortkey: cif
# section: materials
# requires: plot, cif
```

The keys are:

* `title`: The title of the notebook (do not add another title heading in the
  notebook). The notebooks for users show it with the NCrystal logo above
  it.
* `menutitle`: A short version of the title (at most 30 characters), shown in
  the menu of the website, where long titles take up too much space.
* `shortkey`: A short unique key, of at most 14 lowercase letters or digits.
  It is used in URLs (so it should never change) and on the command line.
* `section`: The section of the website in which the notebook is listed (one
  of the [available sections](#available-requirements-and-plugins)).
* `requires`: What the notebook needs besides NCrystal, e.g. `plot` for
  matplotlib or `openmc` for OpenMC. These are names of requirements defined
  for all notebooks, not package names, and never with versions: see the
  [available requirements](#available-requirements-and-plugins).
* `plugins`: NCrystal plugins needed by the notebook, likewise by names
  defined for all notebooks (see the [available plugins](#available-requirements-and-plugins)).
* `import-ncrystal`: Set to `no` if the notebook should not have NCrystal
  imported for it, e.g. because it installs plugins before importing NCrystal.
* `max-line-length`: Maximum length of lines in code cells, if the default (120
  characters) is not suitable, e.g. for embedded data.
* `slow`: Set to `yes` for notebooks which take long to run, even with their
  test parameters. They can be skipped with `--skip-slow` (e.g. while
  debugging), or run alone with `test --only-slow`. In CI, they are run by a
  separate workflow (`tests_slow`), and for now not on the website, where
  their pages show a warning instead.
* `test-parameters`: Values used when testing, e.g. to reduce statistics in
  notebooks which take a long time to run (`# test-parameters: n = 1000; m = 2`).
  The notebook must then put these numbers in a single code cell, tagged
  `parameters` (in Jupyter Lab: the cog icon in the right sidebar, "Add Tag"),
  and use the variables in the rest of the notebook. When testing, the test
  values are assigned in a new cell right after the tagged one, while users and
  the website see the original values.

Long code cells which most readers do not need to see (embedded data, or long
code for an interactive widget) are shown collapsed on the website and in the
notebooks downloaded by users, with a button to expand them. This happens
automatically for code cells with more than `hide_input_lines` lines (set in
`notebook_settings.toml`), and can be requested for other cells by tagging them
`hide-input` (in Jupyter Lab: the cog icon in the right sidebar, "Add Tag").
Tag a long cell `show-input` to always show it.
On the website, long text outputs are shown in boxes with a scrollbar.

Notebooks must run reasonably fast, both for a good experience for users and
to keep testing practical. There are therefore time limits (in
`notebook_settings.toml`) for running a notebook in tests (with its test
parameters) and as users run it (when building the website). Notebooks taking
longer fail. Notebooks should run in less than 20 seconds. Those taking more
than 25 seconds should be marked as slow (see above), and then get more time,
but fail if they turn out to run (as users run them) in less than 10
seconds. On Windows, where e.g. compilation is slower, notebooks not marked
as slow get twice the time. The time of each notebook is
shown in the summary at the end of `ncnotebookdevtool test`.

Do not add code for installing software, setting up plots, or importing
NCrystal: the tool generates this from the settings cell, in different
versions for different purposes (running the notebook in tests, the website,
the downloadable notebooks for pip and conda, and Google Colab). So when a
better way of installing something on Google Colab is found, only the tool
needs to change, not every notebook.

## Section headings

The title of a notebook comes from its settings cell, so the notebook itself
has no headings with a single `#`. Its sections have headings with `##` (and
subsections `###`), which must end with a key in brackets:

```
## Interactive results [results]
### Changing the temperature [temp]
```

Keys consist of lowercase letters (a-z) and digits, start with a letter, have
at most 10 characters, and must be unique within the notebook. Readers do not
see them: on the website and in the notebooks for download and for Google
Colab, the key is removed from the heading, and the section gets a permanent
anchor named after the shortkey of the notebook and the key, e.g.
`sapphire-results`. Links to the section (like
`.../notebooks/sapphire.html#sapphire-results` on the website) therefore keep
working when the heading is reworded. So choose keys which will not need to
change, and do not change existing keys. Deeper headings (`####` and below)
have no keys.

To link to a section of the same notebook from a markdown cell, use its key:

```
See [the results](#results) below.
```

Such links work on the website and in the notebooks for download and for
Google Colab (not while editing the notebook, where the keys are still part of
the headings). The quick checks (e.g. `ncnotebookdevtool precommit`) report
missing, invalid or duplicate keys, and links to keys which do not exist.

## Available requirements and plugins

The names used for `requires`, `plugins` and `section` in the settings cell
are not package names. They are defined in `notebook_settings.toml` at the top
of the repository, which says which packages (and if needed which versions)
each requirement and plugin installs, with pip and with conda, and any setup
code it needs. So versions are never given in the settings cell: if a notebook
needs a newer version of a package, or a requirement or plugin which is not
defined yet, change or add it in `notebook_settings.toml` (all notebooks using
it then get the change). Requirements which can not be installed with pip
(like `openmc`) are only available with conda, and notebooks needing them are
tested in conda environments only.

These are the current definitions:

<!-- ncnotebookdevtool: settings tables -->

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
run if none are given (notebooks are given by their shortkeys or paths, which
also works with the `site`, `check`, `precommit` and `list` modes). Useful
options are `-j N` to run notebooks in parallel, `--env` to choose the kind of
environments, and `--select pip` or `--select conda`.

To test notebooks with the NCrystal code in a local clone of the NCrystal
repository (instead of the released NCrystal), add
`--ncrystal-src /path/to/ncrystal` (this also works with `launch`). NCrystal is
then built from that clone, and the tool verifies that the notebooks really use
it.

The `colab` workflow also runs the Google Colab versions of the notebooks, with
their installation cells, in Google's Colab runtime image (which has the same
Python and preinstalled packages as Google Colab). Each notebook runs in its
own fresh container, as on Colab, where every notebook starts in a fresh
runtime (so what one notebook installs can not hide a missing requirement of
another). It uses `ncnotebookdevtool test --colab`, which only works in that
image. Notebooks
marked as slow only run in its weekly (and manually started) runs, and
notebooks needing conda are not yet tested there.

## The website

The website is built in CI from the main branch and published on GitHub
Pages. The notebooks are run for it (for now except those marked as slow), and
the versions of the notebooks for download and for Google Colab are generated
at the same time. To build it locally:

```
ncnotebookdevtool site -o /some/dir
```

(add `--no-execute` for a quick build without running the notebooks). To
quickly see how your own notebook will look on the website, build a website
with just that notebook, by giving its shortkey:

```
ncnotebookdevtool site -o /some/dir SHORTKEY
```

and open `/some/dir/html/index.html` in a browser.
