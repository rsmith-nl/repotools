#!/usr/bin/env python
# file: makedb.py
# vim:fileencoding=utf-8:fdm=marker:ft=python
#
# Copyright © 2022 R.F. Smith <rsmith@xs4all.nl>
# SPDX-License-Identifier: MIT
# Created: 2022-10-10T23:13:41+0200
# Last modified: 2024-08-16T11:14:37+0200

import json
import os
import sqlite3
import time

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


idbyname = {}
print("Inserting data into tables... ", end="")
for pkg in packages:  # noqa
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
            pkg["sum"],
            pkg["flatsize"],
            pkg["path"],
            pkg["repopath"],
            pkg["licenselogic"],
            pkg["pkgsize"],
            pkg["desc"],
        ),
    )
    pkgid = cur.lastrowid
    idbyname[pkg["name"]] = pkgid
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
print("done.")

# Only after all packages have been ID'd can we resolve deps.
print("Resolving dependencies... ", end="")
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
