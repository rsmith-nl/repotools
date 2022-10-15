Scripts for interacting with FreeBSD package repositories
#########################################################

:date: 2022-10-15
:tags: 
:author: Roland Smith

.. Last modified: 2022-10-15T12:22:34+0200
.. vim:spelllang=en

For updating several machines to FreeBSD 13.1 I wanted to download all the
packages I need beforehand without installing them.

Since I could not find a way to do that using ``pkg``, I wrote my own tools.

.. PELICAN_END_SUMMARY

makedb
------

Every package site contains a file ``packagesite.txz``, which contains the
file ``packagesite.yaml``.
The script ``makedb.py`` reads the YAML file, converts it to JSON and then to
Python native data structures.

From those data structures it fills a couple of SQL tables and saves them in
``packagesite.db`` for later use by ``pkgtool``.
These tables have the following definitions.

.. code-block:: sqlite3

    CREATE TABLE packages (name TEXT, origin TEXT,
    version TEXT, comment TEXT, maintainer TEXT, www TEXT, abi TEXT, arch TEXT,
    prefix TEXT, sum TEXT, flatsize INT, path TEXT, repopath TEXT,
    licenselogic TEXT, pkgsize INT, desc TEXT);
    CREATE TABLE licenses (pkgid INT, name txt);
    CREATE TABLE deps (pkgid INT, name TEXT, origin TEXT, version TEXT, depid INT);
    CREATE TABLE categories (pkgid INT, name txt);
    CREATE TABLE shlibs_required (pkgid INT, name txt);
    CREATE TABLE shlibs_provided (pkgid INT, name txt);
    CREATE TABLE options (pkgid INT, key TEXT, value TEXT);
    CREATE TABLE annotations (pkgid INT, key TEXT, value TEXT);


pkgtool
-------

This script can download packages from ``pkg.freebsd.org`` using ``curl``.
Downloaded packages are placed in the ``packages`` directory.

It reads ``packagesite.db`` and then carries out one of the following
commands:

* ``list``: List all the packages in ``packagesite.db``.
* ``contains <string>``: List all the packages that have the given string in
  their name.
* ``info <pkgname>``: When given a valid package name (without version), it
  produces information about this package
* ``show <pkgname>``: When given a valid package name (without version), it
  produces information about this package and shows the package and all its
  dependencies that would be downloaded if they weren't already in the
  ``packages/`` directory.
* ``get <pkgname>``: When given a valid package name (without version),
  download the package and *all* its dependencies unless they already exist in
  in the ``packages/`` directory.
