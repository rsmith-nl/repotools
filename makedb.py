#!/usr/bin/env python
# file: makedb.py
# vim:fileencoding=utf-8:fdm=marker:ft=python
#
# Copyright © 2022 R.F. Smith <rsmith@xs4all.nl>
# SPDX-License-Identifier: MIT
# Created: 2022-10-10T23:13:41+0200
# Last modified: 2024-08-24T09:34:31+0200

import glob
import hashlib
import json
import os
import sqlite3
import subprocess as sp
import time

# Configuration
REPO = "repo/"
PKGDIR = REPO + "All/"  # must end with path separator.


def get_manifest(repopath):
    """
    Get the manifest from a package.

    Arguments:
        repopath (str): Name of the package, including PKGDIR.

    Note that the manifest is missing some keys that are present in the database:
    * sum: SHA256 checksum of the contents package.
    * repopath: location in the repo relative to REPO
    * path: see repopath
    * pkgsize: size on disk of the package.

    Returns: a dictionary containing the manifest.
    """
    args = ("tar", "xOf", repopath, "+COMPACT_MANIFEST")
    rv = sp.run(args, stdout=sp.PIPE, stderr=sp.DEVNULL)
    if rv.returncode != 0:
        raise ValueError("extracting manifest failed")
    return json.loads(rv.stdout)


def insert_pkg(cur, pkg):
    """
    Insert a package into the database from its manifest.

    Arguments:
        cur (Cursor): database cursor
        pkg (dict): manifest for the package
    """
    cur.execute(
        "INSERT INTO packages VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            pkg["name"],
            pkg["origin"],
            pkg["version"],
            pkg["comment"],
            pkg["maintainer"],
            pkg["www"],
            pkg["abi"],
            pkg["arch"],
            pkg["prefix"],
            pkg["sum"],  # has to be added to file manifest
            pkg["flatsize"],
            pkg["path"],  # has to be added to file manifest
            pkg["repopath"],  # has to be added to file manifest
            pkg["licenselogic"],
            pkg["pkgsize"],  # has to be added to file manifest
            pkg["desc"],
        ),
    )
    pkgid = cur.lastrowid
    if "licenses" in pkg:
        for lic in pkg["licenses"]:
            cur.execute("INSERT INTO licenses VALUES (?, ?)", (pkgid, lic))
    if "categories" in pkg:
        for cat in pkg["categories"]:
            cur.execute("INSERT INTO categories VALUES (?, ?)", (pkgid, cat))
    if "shlibs_required" in pkg:
        for req in pkg["shlibs_required"]:
            cur.execute("INSERT INTO shlibs_required VALUES (?, ?)", (pkgid, req))
    if "shlibs_provided" in pkg:
        for prov in pkg["shlibs_provided"]:
            cur.execute("INSERT INTO shlibs_provided VALUES (?, ?)", (pkgid, prov))
    if "options" in pkg:
        for k, v in pkg["options"].items():
            cur.execute("INSERT INTO options VALUES (?, ?, ?)", (pkgid, k, v))
    if "annotations" in pkg:
        for k, v in pkg["annotations"].items():
            cur.execute("INSERT INTO annotations VALUES (?, ?, ?)", (pkgid, k, v))


# Main program starts here
if __name__ == "__main__":
    start = time.monotonic()
    print("Loading package info from yaml file... ", end="")
    with open("packagesite.yaml") as yf:
        lines = [ln.strip() for ln in yf.readlines()]
    jsondata = "[" + ", ".join(lines) + "]"
    packages = json.loads(jsondata)
    print("done")
    print(f"Found {len(packages)} packages.")

    # Remove existing database
    if os.path.exists("packagesite.db"):
        os.remove("packagesite.db")
        print("Old database removed.")

    # Create database
    db = sqlite3.connect("packagesite.db")
    print("Database created")
    cur = db.cursor()

    # Create tables
    tbls = """CREATE TABLE packages (name TEXT, origin TEXT,
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
    """
    cur.executescript(tbls)
    db.commit()
    print("Tables created.")

    print("Inserting data into tables... ", end="")
    for pkg in packages:  # noqa
        insert_pkg(cur, pkg)
    db.commit()
    print("done.")

    # Insert packages from repo that are not in the database,
    # and fix size/checksum mismatches
    print("Inserting packages not in database... ")
    for completename in glob.glob(PKGDIR + "*.pkg"):
        repopath = completename.removeprefix(REPO)
        cursize = os.path.getsize(completename)
        with open(completename, "rb") as filecontents:
            data = filecontents.read()
            cursum = hashlib.sha256(data).hexdigest()
            del data
        pkgname = completename[9:-4].rsplit("-", maxsplit=1)[0]
        try:
            pkgid, dbsum, dbsize = cur.execute(
                "SELECT rowid, sum, pkgsize FROM packages WHERE name==?", (pkgname,)
            ).fetchone()
        except (ValueError, TypeError):
            print(f"# adding {pkgname} to database... ", end="")
            try:
                manifest = get_manifest(completename)
                # Add missing data.
                manifest["sum"] = cursum
                manifest["repopath"] = repopath
                manifest["path"] = repopath
                manifest["pkgsize"] = cursize
                insert_pkg(cur, manifest)
                packages.append(manifest)
            except ValueError:
                print(f"# skipping {pkgname}, could not get manifest")
            print("done")
            continue
        reason = []
        if dbsum != cursum:
            reason.append("checksum")
        if dbsize != cursize:
            reason.append("size")
        if reason:
            reason = "(" + ", ".join(reason) + ")"
            print(f"# updating {pkgname} {reason}... ", end="")
            cur.execute(
                "UPDATE packages SET sum = ?, pkgsize = ? WHERE rowid == ?",
                (cursum, cursize, pkgid),
            )
            print("done")
    db.commit()

    # Only after all packages have been ID'd can we resolve deps.
    print("Resolving dependencies... ", end="")
    idbyname = dict(cur.execute("SELECT name, rowid FROM packages").fetchall())
    for pkg in packages:
        if "deps" in pkg:
            for depname, depdata in pkg["deps"].items():
                deporig, depver = depdata.values()
                depid = idbyname.get(depname, -1)
                cur.execute(
                    "INSERT INTO deps VALUES (?, ?, ?, ?, ?)",
                    (idbyname[pkg["name"]], depname, deporig, depver, depid),
                )
    print("done.")
    db.commit()
    db.close()
    runtime = time.monotonic() - start
    print(f"# duration: {runtime:.3f} s")
