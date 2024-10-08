#!/usr/bin/env python
# file: repotool.py
# vim:fileencoding=utf-8:fdm=marker:ft=python
#
# Copyright © 2022 R.F. Smith <rsmith@xs4all.nl>
# SPDX-License-Identifier: MIT
# Created: 2022-10-09T23:14:51+0200
# Last modified: 2024-09-15T11:15:01+0200

import glob
import hashlib
import json
import os
import sqlite3
import subprocess as sp
import sys
import time

# Configuration
ABI = "FreeBSD:14:amd64"
REL = "quarterly"
REPODIR = f"/home/{os.getenv('USER')}/freebsd-quarterly"
REPO = "repo/"
PKGDIR = REPO + "All/"  # must end with path separator.

# Colors
BOLD_WHITE = "\033[1;37m"
CYAN = "\033[0;36m"
GREEN = "\033[0;32m"
PURPLE = "\033[0;35m"
BOLD_RED = "\033[1;31m"
RED = "\033[0;31m"
YELLOW = "\033[0;33m"
BOLD_YELLOW = "\033[1;33m"
RESET = "\033[0m"  # No Color

# Supported commands
cmds = [
    "list",
    "show",
    "contains",
    "get",
    "delete",
    "info",
    "leaves",
    "refresh",
    "unused",
    "check",
]
help = [
    "show all available packages",
    "show what would be downloaded for a given package name",
    "print the names of packages that contain the given string",
    "download the given package, plus any required dependencies",
    "delete a package if it is unused, plus any unused dependencies",
    "show information about a named package",
    "show all packages that are not depended on",
    "for every package, check and update the requirements",
    "show packages in the repo that are not installed",
    "for every package, check size and checksum",
]


def main():  # noqa
    start = time.monotonic()
    # Change directory
    try:
        os.chdir(REPODIR)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)
    # Handle arguments
    args = sys.argv[1:]
    if len(args) == 0 or args[0] not in cmds:
        print(f"usage: {sys.argv[0]} {'|'.join(cmds)} pkgname")
        for a, b in zip(cmds, help):
            print(f"* {BOLD_WHITE}{a:8}{RESET}: {b}.")
        sys.exit(0)
    if not os.path.isdir(PKGDIR):
        print(f"{RED}Error: “{PKGDIR}” not found in “{REPODIR}”.{RESET}")
        sys.exit(2)
    cmd = args[0]
    pkgname = args[1] if len(args) > 1 else ""

    # Check if other important repotool jobs are running.
    check_running()

    # Load database.
    # See makedb.py for the database definition.
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
    elif cmd == "delete":
        cmd_delete(cur, start, pkgname)
    elif cmd == "leaves":
        cmd_leaves(cur, start)
    elif cmd == "refresh":
        cmd_refresh(cur, start)
    elif cmd == "unused":
        cmd_unused(cur, start)
    elif cmd == "check":
        cmd_check(cur, start)


def cmd_list(cur, start):
    """
    List all available packages.

    Arguments:
        cur (Cursor): Sqlite database cursor.
        start (float): Start time.
    """
    cur.execute("SELECT repopath FROM packages ORDER BY repopath ASC")
    for j in cur.fetchall():
        print(j[0][4:])
    duration = time.monotonic() - start
    print(f"{YELLOW}# duration: {duration:.3f} s{RESET}")


def cmd_contains(cur, start, pkgname):
    """
    Show packages whose name contains pkgname

    Arguments:
        cur (Cursor): Sqlite database cursor.
        start (float): Start time.
        pkgname (str): Fragment to search for in the package name.
    """
    for p in contains(cur, pkgname):
        print(p)
    duration = time.monotonic() - start
    print(f"{YELLOW}# duration: {duration:.3f} s{RESET}")


def cmd_info(cur, start, pkgname):
    """
    Print package information for pkgname

    Arguments:
        cur (Cursor): Sqlite database cursor.
        start (float): Start time.
        pkgname (str): Fragment to search for in the package name.
    """
    cur.execute(
        "SELECT origin, version, repopath, comment, www FROM packages WHERE name IS ?",
        (pkgname,),
    )
    try:
        origin, version, repopath, comment, www = cur.fetchone()
        print(f"Name: {BOLD_WHITE}{pkgname}{RESET}")
        print(f"Version: {version}")
        print(f"Location in repository: {repopath}")
        print(f"Origin: {origin}")
        print(f"WWW: {BOLD_WHITE}{www}{RESET}")
        print(f"Comment: {comment}")
    except TypeError:
        print(f"# package “{pkgname}” does not exist.")
    duration = time.monotonic() - start
    print(f"{YELLOW}# duration: {duration:.3f} s{RESET}")


def cmd_show(cur, start, pkgname):
    """
    Print package information and dependencies for pkgname

    Arguments:
        cur (Cursor): Sqlite database cursor.
        start (float): Start time.
        pkgname (str): Name of the package.
    """
    cur.execute(
        "SELECT origin, version, repopath, comment FROM packages WHERE name IS ?",
        (pkgname,),
    )
    try:
        origin, version, repopath, comment = cur.fetchone()
        print(f"Name: {BOLD_WHITE}{pkgname}{RESET}")
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
                print(BOLD_WHITE + rp[0] + RESET)
            else:
                print(f"# skipping {pkgname}, already exists.")
    except TypeError:
        print(f"# package “{pkgname}” does not exist.")
    duration = time.monotonic() - start
    print(f"{YELLOW}# duration: {duration:.3f} s{RESET}")


def cmd_get(cur, start, pkgname):
    """
    Retrieve package and dependencies for pkgname

    Arguments:
        cur (Cursor): Sqlite database cursor.
        start (float): Start time.
        pkgname (str): Name of the package.
    """
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
            print(f"{PURPLE}# skipping {pkgname}, already exists.{RESET}")
    duration = time.monotonic() - start
    print(f"{YELLOW}# duration: {duration:.3f} s{RESET}")


def cmd_delete(cur, start, pkgname):
    """
    Delete a package if it is not depended on.
    Also delete all requirements that are not depended on by others.

    Arguments:
        cur (Cursor): Sqlite database cursor.
        start (float): Start time.
        pkgname (str): Name of the package.
    """

    def duration():
        duration = time.monotonic() - start
        print(f"{YELLOW}# duration: {duration:.3f} s{RESET}")

    # Get the row id and path in the repo of the package
    rv = cur.execute(
        "SELECT rowid, repopath FROM packages WHERE name is ?", (pkgname,)
    ).fetchone()
    if rv is None:
        print(f"# package “{pkgname}” is not in the database")
        duration()
        return
    rowid, repopath = rv
    if not os.path.exists(REPO + repopath):
        print(f"# package “{pkgname}” is not in the repo")
        duration()
        return
    # Get all the rowids that depend on this package.
    # Note that those packages might or might not actually be there!
    dependers = cur.execute(
        "SELECT name, repopath, rowid FROM packages WHERE rowid IN "
        "(SELECT pkgid FROM deps WHERE depid IS ?)",
        (rowid,),
    ).fetchall()
    # Narrow the selection down to other packages that actually exist
    existing_dependers = [
        (name, rowid)
        for name, repopath, rowid in dependers
        if os.path.exists(REPO + repopath)
    ]
    if existing_dependers:
        print(
            f"# package “{pkgname}” cannot be deleted, following packages require it:"
        )
        for name, _ in existing_dependers:
            print(f"#  {name}")
        duration()
        return
    else:
        print(f"# package “{pkgname}” is not depended on, so it can be deleted.")
    dependencies = deps(cur, pkgname)
    print(f"# found {len(dependencies)} dependencies.")
    # TODO: Delete the package.
    # TODO: Recursively delete dependencies if they have no other packages
    # that depend on them.
    duration()


def cmd_refresh(cur, start):
    """
    Refresh (update all dependencies) of existing packages.

    Arguments:
        cur (Cursor): Sqlite database cursor.
        start (float): Start time.
    """
    presentnames = [
        j.replace(PKGDIR, "").rsplit("-", maxsplit=1)[0]
        for j in glob.glob(PKGDIR + "*.pkg")
    ]
    for pkgname in presentnames:
        print(f"Refreshing {pkgname}")
        try:
            rps = deps(cur, pkgname)
        except (ValueError, TypeError):
            print(f"{PURPLE}# skipping {pkgname}, not in database{RESET}")
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
    duration = time.monotonic() - start
    print(f"{YELLOW}# duration: {duration:.3f} s{RESET}")


def cmd_leaves(cur, start):
    """
    Print those names from PKGDIR which are not depended on.

    Arguments:
        cur (Cursor): Sqlite database cursor.
        start (float): Start time.
    """
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
    print(f"{YELLOW}# duration: {duration:.3f} s{RESET}")


def cmd_unused(cur, start):
    """
    Print those names from PKGDIR which are not depended on.

    Arguments:
        cur (Cursor): Sqlite database cursor.
        start (float): Start time.
    """
    duration = time.monotonic() - start
    pkgdata = sp.check_output(["pkg", "info"]).decode("utf-8")
    installedpkgs = set(ln.split()[0] for ln in pkgdata.splitlines())
    repopkgs = set(pkgname[9:-4] for pkgname in glob.glob(PKGDIR + "*.pkg"))
    uninstalled = sorted(repopkgs - installedpkgs)
    for pkg in uninstalled:
        print(pkg)
    print(f"{YELLOW}# duration: {duration:.3f} s{RESET}")


def cmd_check(cur, start):
    """
    Check size and checksum of existing packages.

    Arguments:
        cur (Cursor): Sqlite database cursor.
        start (float): Start time.
    """
    for completename in glob.glob(PKGDIR + "*.pkg"):
        cursize = os.path.getsize(completename)
        with open(completename, "rb") as filecontents:
            data = filecontents.read()
        cursum = hashlib.sha256(data).hexdigest()
        pkgname = completename[9:-4].rsplit("-", maxsplit=1)[0]
        try:
            dbsum, dbsize = cur.execute(
                "SELECT sum, pkgsize FROM packages WHERE name==?", (pkgname,)
            ).fetchone()
        except (ValueError, TypeError):
            print(f"{PURPLE}# skipping {pkgname}, not in database{RESET}")
            continue
        # print(f"Checking {pkgname}", end="")
        if dbsum != cursum:
            print(f"\n{CYAN}# CHECKSUM package “{pkgname}” differs{RESET}")
            print(f"{CYAN}# current package: {cursum}{RESET}")
            print(f"{CYAN}# database: {dbsum}{RESET}")
        elif dbsize != cursize:
            print(f"\n{CYAN}# SIZE package “{pkgname}”; {cursize} → {dbsize}{RESET}")
    duration = time.monotonic() - start
    print(f"{YELLOW}# duration: {duration:.3f} s{RESET}")


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
    cur.execute("SELECT rowid FROM packages WHERE name IS ?", (name,))
    pkgid = cur.fetchone()
    alldeps = []
    newdeps = [pkgid]
    while len(newdeps) >= len(alldeps):
        alldeps += [j for j in newdeps if j not in alldeps]
        newdeps = cur.execute(
            "SELECT DISTINCT depid FROM deps WHERE pkgid IN "
            + "("
            + ", ".join(str(j[0]) for j in alldeps)
            + ")"
        ).fetchall()
    rv = [pkgid]
    rv += [j for j in alldeps if j not in rv]
    return rv


def download(repopath):
    """
    Download package.

    Arguments:
        repopath (str): Name of the package to download.
    """
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
        print(f"{RED}failed, code {cp.returncode}.{RESET}")
    else:
        # Make packages readable for everyone.
        os.chmod(PKGDIR[:-4] + repopath, 0o0644)
        print(f"{GREEN}done.{RESET}")


def check_running():
    """Check if an important command is already running. If so, exit."""
    ourpid = str(os.getpid())
    psdata = sp.check_output(["ps", "--libxo=json"]).decode("utf-8")
    procs = json.loads(psdata)["process-information"]["process"]
    del psdata
    for pid, terminal_name, state, cpu_time, command in procs:
        if pid == ourpid:
            continue
        if "repotool" not in command:
            continue
        if any(j in command for j in ("upgrade", "refresh", "delete")):
            print(f"{RED}Upgrade, refresh or delete in progress.{RESET}", end=" ")
            print(f"Process {pid}, terminal {terminal_name}; exiting.")
            sys.exit(3)


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
        raise ValueError(f"{RED}extracting manifest failed{RESET}")
    return json.loads(rv.stdout)


if __name__ == "__main__":
    main()
