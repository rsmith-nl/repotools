Scripts for maintaining a FreeBSD package repository
####################################################

:date: 2022-10-15
:tags: FreeBSD
:author: Roland Smith

.. Last modified: 2024-07-25T21:29:29+0200
.. vim:spelllang=en

For updating several machines to a new version of FreeBSD I wanted to download
the packages I need *and all their dependencies* beforehand without installing
them.

Since I could not find a way to do that using ``pkg``, I wrote my own tools.

It can be used for other versions, architectures and releases by editing the
configuration variables at the begin of ``repotool.py`` and changing the
``curl`` invocation at the beginning of ``newdb.sh`` accordingly.

Note that these tools follow the quarterly branch of the ports tree.
For me, this strikes a good balance between availability and time spent on
maintenance.

It is now used as an offline cache for all the packages that I use on my
machines. For me this cache is just above 2 GiB, so it's easy to distribute on
a USB thumb drive.

.. PELICAN_END_SUMMARY

Requirements
============

* FreeBSD operating system,
* ``pkg``,
* ``curl``,
* ``python`` version 3 (FreeBSD default version),
* ``sqlite3`` package for python.


Installation
============

Invoking ``make install`` creates the directory ``$HOME/freebsd-quarterly``,
and places the programs ``newdb``, ``makedb`` and ``repotool`` in there.

Note that these programs can be run as a normal user and do not require root
privileges.


Filling the repository
======================

To fill the repository, start by running::

    pkg query -e "%#r == 0" "%n-%v" > leaf-packages.txt

The file ``leaf-packages.txt`` then contains a list of packages that are not
required by others.

Go to ``$HOME/freebsd-quarterly``.
For each of the packages in ``leaf-packages.txt``, issue the following
command::

    ./repotool get <packagname-version>

This will download the package *and all its dependencies* and store them in
``$HOME/freebsd-quarterly/repo/All``.


Using the repository
====================

To *use* the repository to install packages from, you should create
a configuration file for it; ``/usr/local/etc/pkg/repos/myrepo.conf`` for example.

This should contain::

  FreeBSD: { enabled: NO }

  myrepo: {
    url: "file:///home/<USER>/freebsd-quarterly/repo",
    mirror_type: "none",
    signature_type: "none",
    enabled: YES
  }

Where ``<USER>`` should be replaced by the username of the user that has the
repo.
When this is done, running ``pkg install`` will use packages from your cache.

The quarterly branch of the ports tree does not move as fast as the main
branch, so it is not necessary to check for updates every day.
Generally, I keep an eye on the relevant branch of the `git server for ports`_
to check for interesting updates.
And I also check the `package server`_ for whenever the latest build of the
quarterly branch was published.

.. _git server for ports: https://cgit.freebsd.org/ports/
.. _package server: http://pkg.freebsd.org/freebsd:14:x86:64/

Whenever an update is warranted, I change to the ``$HOME/freebsd-quarterly``
directory and run ``./newdb``.
After that I run ``./repotool show-upgrade``. If there are useful updates (not
just package size changes) I run ``./repotool upgrade`` and then
``doas pkg upgrade`` to install upgraded packages.

Every month or so, I run ``./repotool refresh`` to pick up any changes in
dependencies.


The programs
============

newdb
-----

This shell-script downloads ``packagesite.txz`` for the quarterly branch of
the ports tree for the built-in version and architecture, e.g. ``freebsd:14:x86:64``.

.. note:: This should match the ``ABI`` constant in ``repotool.py``!

Every package site contains a file ``packagesite.txz``, which contains the
file ``packagesite.yaml``, ``packagesite.yaml.pub`` and ``packagesite.yaml.sig``.
We are interested in the YAML file.

The script verifies the public key using::

    openssl pkey -pubcheck -pubin -in packagesite.yaml.pub -noout

This should produce the output ``Key is valid``.

It then also verifies the signature as follows::

    sha256 -q packagesite.yaml | tr -d '\n' | \
    openssl dgst -verify packagesite.yaml.pub -signature packagesite.yaml.sig

This should output ``Verified OK``.

It then invokes ``makedb`` to convert the information in the
``packagesite.yaml`` into an sqlite3 database.


makedb
------

The script ``makedb.py`` reads the YAML file, and converts the contents to
Python native data structures.

From those data structures it fills a couple of SQL tables and saves them in
``packagesite.db`` for later use by ``repotool``.
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

Note that these table have an automatic row-id that is the primary
identification for each row.

The ``packages`` table speaks for itself. It is the primary source of
information about packages.
The other tables are basically to provide multiple pieces of information about
each row in the packages table.
That is why they all have an integer named ``pkgid`` as the first item in the
row; that is the row-id in the ``packages`` table that they belong to.


repotool
--------

This script can download packages from ``pkg.freebsd.org`` using ``curl``.
Downloaded packages are placed in the ``packages`` directory.

It reads ``packagesite.db`` and then carries out one of the following
commands:

* ``list``: List all the packages in ``packagesite.db``.
* ``show <pkgname>``: When given a valid package name (without version), it
  produces information about this package and shows the package and all its
  dependencies that would be downloaded if they weren't already in the
  packages directory.
* ``contains <string>``: List all the packages that have the given string in
  their name.
* ``get <pkgname>``: When given a valid package name (without version),
  download the package and *all* its dependencies unless they already exist in
  in the packages directory.
* ``delete <pkgname>``: Delete a package when no other package depends on it.
* ``info <pkgname>``: When given a valid package name (without version), it
  produces information about this package
* ``leaves``: show all the packages that are not depended on.
* ``upgrade``: Brings the contents of the repo up-to-date with the database.
  Retrieves packages whose size or version has changed.
* ``show-upgrade``: Show what would be done if ``upgrade`` was used.
* ``refresh``: For every package, check and update the requirements.
* ``unused``: Shows the packages in the repo that are not installed.
