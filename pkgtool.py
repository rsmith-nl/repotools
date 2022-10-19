#!/usr/bin/env python
# file: pkgtool.py
# vim:fileencoding=utf-8:fdm=marker:ft=python
#
# Copyright © 2022 R.F. Smith <rsmith@xs4all.nl>
# SPDX-License-Identifier: MIT
# Created: 2022-10-09T23:14:51+0200
# Last modified: 2022-10-19T11:38:08+0200

import functools
import os
import sqlite3
import subprocess as sp
import sys
import time

# Configuration
ABI = "FreeBSD:13:amd64"
REL = "quarterly"
PKGDIR = "packages/"  # must end with path separator.

# Supported commands
cmds = ["list", "show", "contains", "get", "info", "leaves"]


def main():  # noqa
    start = time.monotonic()
    # Handle arguments
    args = sys.argv[1:]
    if len(args) == 0 or args[0] not in cmds:
        print(f"usage: {sys.argv[0]} {'|'.join(cmds)} pkgname")
        sys.exit(0)
    cmd = args[0]
    pkgname = args[1] if len(args) > 1 else ""

    # Load database
    db = sqlite3.connect("packagesite.db")
    cur = db.cursor()

    # Process commands.
    if cmd == "list":
        cmd_list(cur, start)
    elif cmd == "contains":
        cmd_contains(cur, start, pkgname)
    elif cmd == "info":
        cmd_info(cur, start, pkgname)
    elif cmd == "show":
        cmd_show(cur, start, pkgname)
    elif cmd == "get":
        cmd_get(cur, start, pkgname)
    elif cmd == "leaves":
        cmd_leaves(cur, start)


def cmd_list(cur, start):
    cur.execute("SELECT repopath FROM packages ORDER BY repopath ASC")
    for j in cur.fetchall():
        print(j[0][4:])
    duration = time.monotonic() - start
    print(f"duration: {duration:.3f} s")


def cmd_contains(cur, start, pkgname):
    """Show packages whose name contains pkgname"""
    for p in contains(cur, pkgname):
        print(p)
    duration = time.monotonic() - start
    print(f"# duration: {duration:.3f} s")


def cmd_info(cur, start, pkgname):
    """Print package information for pkgname"""
    cur.execute(
        "SELECT origin, version, repopath, comment FROM packages WHERE name IS ?",
        (pkgname,),
    )
    try:
        origin, version, repopath, comment = cur.fetchone()
        print(f"Name: {pkgname}")
        print(f"Version: {version}")
        print(f"Location in repository: {repopath}")
        print(f"Origin: {origin}")
        print(f"Comment: {comment}")
    except TypeError:
        print(f"# package “{pkgname}” does not exist.")
    duration = time.monotonic() - start
    print(f"# duration: {duration:.3f} s")


def cmd_show(cur, start, pkgname):
    """Print package information and dependencies for pkgname"""
    cur.execute(
        "SELECT origin, version, repopath, comment FROM packages WHERE name IS ?",
        (pkgname,),
    )
    try:
        origin, version, repopath, comment = cur.fetchone()
        print(f"Name: {pkgname}")
        print(f"Version: {version}")
        print(f"Location in repository: {repopath}")
        print(f"Origin: {origin}")
        print(f"Comment: {comment}")
        print("---------------------")
        print("Packages to retrieve:")
        rps = deps(cur, pkgname)
        alldeps = [
            cur.execute("SELECT repopath FROM packages WHERE rowid IS ?", d).fetchone()
            for d in rps
        ]
        for rp in alldeps:
            pkgname = rp[0].split("/")[-1]
            if not os.path.exists(PKGDIR + pkgname):
                print(rp[0])
            else:
                print(f"# skipping {pkgname}, already exists.")
    except TypeError:
        print(f"# package “{pkgname}” does not exist.")
    duration = time.monotonic() - start
    print(f"# duration: {duration:.3f} s")


def cmd_get(cur, start, pkgname):
    """Retrieve package and dependencies for pkgname"""
    print("Retrieving packages:")
    rps = deps(cur, pkgname)
    alldeps = [
        cur.execute("SELECT repopath FROM packages WHERE rowid IS ?", d).fetchone()
        for d in rps
        if d != (-1,)
    ]
    for rp in alldeps:
        pkgname = rp[0].split("/")[-1]
        if not os.path.exists(PKGDIR + pkgname):
            download(rp[0])
        else:
            print(f"# skipping {pkgname}, already exists.")
    duration = time.monotonic() - start
    print(f"# duration: {duration:.3f} s")


def cmd_leaves(cur, start):
    """Print those names from PKGDIR which are not depended on."""
    allpkgs = set(cur.execute("SELECT rowid FROM packages").fetchall())
    are_deps = set(cur.execute("SELECT depid FROM deps"))
    leaves = allpkgs - are_deps
    leafnames = sorted(
        cur.execute("SELECT repopath FROM packages WHERE rowid IS ?", p)
        .fetchone()[0]
        .split("/")[-1]
        for p in leaves
    )
    for p in leafnames:
        if os.path.exists(PKGDIR + p):
            print(p)
    duration = time.monotonic() - start
    print(f"# duration: {duration:.3f} s")


def contains(cur, s):
    """Return a list of package names that contain s."""
    cur.execute(f"SELECT name FROM packages WHERE name LIKE '%{s}%'")
    return [j[0] for j in cur.fetchall()]


def deps(cur, name):
    """
    Find all the dependencies of a package.

    Arguments:
        cur (Cursor): database cursor
        name (str): name of the package

    Returns: a list of rowids of dependencies.
    """

    @functools.cache
    def depbyrowid(cur, rowid):
        if rowid == -1:
            return set()
        depids = cur.execute(
            "SELECT depid FROM deps WHERE pkgid is ?", rowid
        ).fetchall()
        if not depids:
            return set()
        rv = set(depids)
        for di in depids:
            rv |= depbyrowid(cur, di)
        return rv

    cur.execute("SELECT rowid FROM packages WHERE name IS ?", (name,))
    pkgid = cur.fetchone()
    alldeps = list(depbyrowid(cur, pkgid))
    alldeps.insert(0, pkgid)
    return alldeps


def download(repopath):
    """Download the package named via the repopath"""
    args = [
        "curl",
        "-s",
        "--output-dir",
        "packages",
        "-O",
        f"http://pkg.freebsd.org/{ABI}/{REL}/" + repopath,
    ]
    print(f"Downloading “{repopath}”... ", end="")
    cp = sp.run(args)
    if cp.returncode != 0:
        print(f"failed, code {cp.returncode}")
    print("done")


if __name__ == "__main__":
    main()
