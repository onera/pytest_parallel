================
pytest-mpi-check
================

.. image:: https://img.shields.io/pypi/v/pytest-mpi-check.svg
    :target: https://pypi.org/project/pytest-mpi-check
    :alt: PyPI version

.. image:: https://img.shields.io/pypi/pyversions/pytest-mpi-check.svg
    :target: https://pypi.org/project/pytest-mpi-check
    :alt: Python versions

.. image:: https://travis-ci.org/maugarsb/pytest-mpi-check.svg?branch=master
    :target: https://travis-ci.org/maugarsb/pytest-mpi-check
    :alt: See Build Status on Travis CI

.. image:: https://ci.appveyor.com/api/projects/status/github/maugarsb/pytest-mpi-check?branch=master
    :target: https://ci.appveyor.com/project/maugarsb/pytest-mpi-check/branch/master
    :alt: See Build Status on AppVeyor

Plugin to manage test in distributed way with MPI Standard

----

This `pytest`_ plugin was generated with `Cookiecutter`_ along with `@hackebrot`_'s `cookiecutter-pytest-plugin`_ template.


Features
--------

1. Cloisonner c'est très bien => on fait ça pour la base de test sonics
  Mais c'est lourd => pas pour Maia
2. il existe un mécanisme de "fault handler" qui peut permettre de gérer les segfault par autre chose que par un crash -> à investiguer
3. Pour PyTest il nous faut sans doute plusieurs schedulers en fait :
  1. au moins un pseudo-seq facile à débugger => c'est le plus important
  2. un statique (celui actuel) 
  3. un dynamique


Requirements
------------

* TODO


Installation
------------

You can install "pytest-mpi-check" via `pip`_ from `PyPI`_::

    $ pip install pytest-mpi-check


Usage
-----

* TODO

Contributing
------------
Contributions are very welcome. Tests can be run with `tox`_, please ensure
the coverage at least stays the same before you submit a pull request.

License
-------

Distributed under the terms of the `Mozilla Public License 2.0`_ license, "pytest-mpi-check" is free and open source software


Issues
------

If you encounter any problems, please `file an issue`_ along with a detailed description.

.. _`Cookiecutter`: https://github.com/audreyr/cookiecutter
.. _`@hackebrot`: https://github.com/hackebrot
.. _`MIT`: http://opensource.org/licenses/MIT
.. _`BSD-3`: http://opensource.org/licenses/BSD-3-Clause
.. _`GNU GPL v3.0`: http://www.gnu.org/licenses/gpl-3.0.txt
.. _`Apache Software License 2.0`: http://www.apache.org/licenses/LICENSE-2.0
.. _`cookiecutter-pytest-plugin`: https://github.com/pytest-dev/cookiecutter-pytest-plugin
.. _`file an issue`: https://github.com/maugarsb/pytest-mpi-check/issues
.. _`pytest`: https://github.com/pytest-dev/pytest
.. _`tox`: https://tox.readthedocs.io/en/latest/
.. _`pip`: https://pypi.org/project/pip/
.. _`PyPI`: https://pypi.org/project
