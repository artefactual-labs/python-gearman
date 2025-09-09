python-gearman
==============

This is a Gearman API written in Python -- client, worker and admin client interfaces.

For information about Gearman and a C-based Gearman server, see `<http://gearman.org/>`_.

This is a fork of the original `Yelp/python-gearman <https://github.com/Yelp/python-gearman>`_ project.
The `Wellcome Collection <https://github.com/wellcomecollection/python-gearman>`_ previously forked that project to add Python 3 support; that repository has since been archived.
We forked the Wellcome Collection repository so we could continue maintenance and apply bugfixes as needed.
You can use this library if you have an existing project that uses python-gearman and you want to upgrade to Python 3, but you probably shouldn't use it for a new project.

Installation
************

This library is not published on PyPI yet.

The library is tested with Python 3.9 and newer.


Usage
*****

This is a drop-in replacement for the 2.x python-gearman library.
There are docs at `<https://pythonhosted.org/gearman/>`_.


Development
***********

We created this fork so we'd have a Python 3-compatible version of Gearman to use in `Archivematica <https://github.com/artefactual/archivematica>`_.

We'll accept bugfixes for improving compatibility with Python 3 and for increasing overall stability, but we're unlikely to accept new features or changes to the library's behaviour.
If you want to make big changes, we suggest creating your own fork.

New patches should come with tests.

See `<developers.rst>`_ for more notes on development, and in particular instructions for creating pull requests.


Further links
*************

* Changelog for gearman3: see `<changes.rst>`_.

* 2.x source: `<https://github.com/Yelp/python-gearman/>`_
* 2.x documentation: `<https://packages.python.org/gearman/>`_

* 1.x source `<https://github.com/samuel/python-gearman/>`_
* 1.x documentation `<https://github.com/samuel/python-gearman/tree/master/docs/>`_
