#!/usr/bin/env python
# file: repotool.py
# vim:fileencoding=utf-8:fdm=marker:ft=python
#
# Copyright © 2022 R.F. Smith <rsmith@xs4all.nl>
# SPDX-License-Identifier: MIT
# Created: 2022-10-09T23:14:51+0200
# Last modified: 2023-07-22T12:06:27+0200

import functools
import glob
import os
import sqlite3
import subprocess as sp
import sys
import time

# Configuration
ABI = "FreeBSD:13:amd64"
REL = "quarterly"
PKGDIR = "repo/All/"  # must end with path separator.

# Supported commands
cmds = [
    "list",
    "show",
    "contains",
    "get",
    "info",
    "leaves",
    "upgrade",
    "show-upgrade",
    "refresh",
]
help = [
    "show all available packages",
    "show what would be downloaded for a given package name",
    "print the names of packages that contain the given string",
    "download the given package, plus any required dependencies",
    "show information about a named package",
    "show all packages that are not depended on",
    "download any packages where the version or package size has changed",
    "for every packages test if the requirements are met and get missing packages",
]

def main():  # noqa
    start = time.monotonic()
    # Handle arguments
    args = sys.argv[1:]
    if len(args) == 0 or args[0] not in cmds:
        print(f"usage: {sys.argv[0]} {'|'.join(cmds)} pkgname")
        for a, b in zip(cmds, help):
            print(f"* {a:8}: {b}.")
        sys.exit(0)
    if not os.path.isdir(PKGDIR):
        print(f"Error: “{PKGDIR}” not found in the current working directory.")
        sys.exit(1)
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
    elif cmd == "upgrade":
        cmd_upgrade(cur, start)
    elif cmd == "show-upgrade":
        cmd_show_upgrade(cur, start)
    elif cmd == "refresh":
        cmd_refresh(cur, start)


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


def cmd_refresh(cur, start):
    """Refresh all existing packages."""
    presentnames = [
        j.replace(PKGDIR, "").rsplit("-", maxsplit=1)[0]
        for j in glob.glob(PKGDIR + "*.pkg")
    ]
    for pkgname in presentnames:
        print(f"Refreshing {pkgname}")
        try:
            rps = deps(cur, pkgname)
        except ValueError:
            print(f"# skipping {pkgname}, not in database")
            continue
        alldeps = [
            cur.execute("SELECT repopath FROM packages WHERE rowid IS ?", d).fetchone()
            for d in rps
            if d != (-1,)
        ]
        for rp in alldeps:
            rpkgname = rp[0].split("/")[-1]
            if not os.path.exists(PKGDIR + rpkgname):
                download(rp[0])
            # else:
            # print(f"# skipping {rpkgname}, already exists.")
    duration = time.monotonic() - start
    print(f"# duration: {duration:.3f} s")


def cmd_leaves(cur, start):
    """Print those names from PKGDIR which are not depended on."""
    pkgdict = dict(cur.execute("SELECT repopath, rowid FROM packages"))
    presentnames = [j.replace(PKGDIR, "All/") for j in glob.glob(PKGDIR + "*.pkg")]
    presentpkgs = set((pkgdict.get(n),) for n in presentnames)
    presentpkgs.remove((None,))
    leaves = set()
    for p in presentpkgs:
        pdeps = set(
            j
            for j in cur.execute("SELECT pkgid FROM deps WHERE depid IS ?", p)
            if j in presentpkgs
        )
        if len(pdeps) == 0:
            leaves.add(p)
    leafnames = sorted(
        cur.execute("SELECT repopath FROM packages WHERE rowid IS ?", p)
        .fetchone()[0]
        .split("/")[-1]
        for p in leaves
    )
    for p in leafnames:
        print(p)
    duration = time.monotonic() - start
    print(f"# duration: {duration:.3f} s")


def cmd_upgrade(cur, start):
    """Upgrade existing packages."""
    for pkgname in glob.glob(PKGDIR + "*.pkg"):
        cursize = os.path.getsize(pkgname)
        name, curver = pkgname[9:-4].rsplit("-", maxsplit=1)
        try:
            dbver, repopath, dbsize = cur.execute(
                "SELECT version, repopath, pkgsize FROM packages WHERE name==?", (name,)
            ).fetchone()
        except TypeError:
            print(f"# package {name} not in database.")
            continue
        if dbver != curver or dbsize != cursize:
            print(f"# Removing old package “{pkgname}”")
            os.remove(pkgname)
            download(repopath)
    duration = time.monotonic() - start
    print(f"# duration: {duration:.3f} s")


def cmd_show_upgrade(cur, start):
    """Show which existing packages would be upgraded."""
    for pkgname in glob.glob(PKGDIR + "*.pkg"):
        cursize = os.path.getsize(pkgname)
        name, curver = pkgname[9:-4].rsplit("-", maxsplit=1)
        try:
            dbver, repopath, dbsize = cur.execute(
                "SELECT version, repopath, pkgsize FROM packages WHERE name==?", (name,)
            ).fetchone()
        except TypeError:
            print(f"# package {name} not in database.")
            continue
        if dbver != curver:
            print(f"# VERSION package “{name}”; {curver} → {dbver}")
        elif dbsize != cursize:
            print(f"# SIZE package “{name}”; {cursize} → {dbsize}")
    duration = time.monotonic() - start
    print(f"# duration: {duration:.3f} s")


def contains(cur, s):
    """Return a list of package names that contain s."""
    cur.execute(f"SELECT name FROM packages WHERE name LIKE '%{s}%'")
    return [j[0] for j in cur]


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
        PKGDIR,
        "-O",
        f"http://pkg.freebsd.org/{ABI}/{REL}/" + repopath,
    ]
    print(f"Downloading “{repopath}”... ", end="")
    cp = sp.run(args)
    if cp.returncode != 0:
        print(f"failed, code {cp.returncode}")
    # Make packages readable for everyone.
    os.chmod(PKGDIR[:-4] + repopath, 0o0644)
    print("done")


if __name__ == "__main__":
    main()
