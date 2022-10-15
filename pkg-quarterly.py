#!/usr/bin/env python
# file: pkg-quarterly.py
# vim:fileencoding=utf-8:fdm=marker:ft=python
#
# Copyright © 2022 R.F. Smith <rsmith@xs4all.nl>
# Created: 2022-10-09T23:14:51+0200
# Last modified: 2022-10-14T22:13:40+0200

import functools
import os
import sqlite3
import subprocess as sp
import sys
import time


ABI = "FreeBSD:13:amd64"
REL = "quarterly"
PKGDIR = "packages/"

cmds = ["list", "show", "contains", "get", "info"]


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
        cur.execute("SELECT repopath FROM packages ORDER BY repopath ASC")
        for j in cur.fetchall():
            print(j[0][4:])
        duration = time.monotonic() - start
        print(f"duration: {duration:.3f} s")
    elif cmd == "contains":
        for p in contains(cur, pkgname):
            print(p)
        duration = time.monotonic() - start
        print(f"# duration: {duration:.3f} s")
    elif cmd == "info":
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
    elif cmd == "show":
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
                cur.execute(
                    "SELECT repopath FROM packages WHERE rowid IS ?", d
                ).fetchone()
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
    elif cmd == "get":
        print("Retrieving packages:")
        rps = deps(cur, pkgname)
        alldeps = [
            cur.execute("SELECT repopath FROM packages WHERE rowid IS ?", d).fetchone()
            for d in rps if d != (-1,)
        ]
        for rp in alldeps:
            pkgname = rp[0].split("/")[-1]
            if not os.path.exists("packages/" + pkgname):
                download(rp[0])
            else:
                print(f"# skipping {pkgname}, already exists.")
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
