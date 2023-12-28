#!/bin/sh
# file: newdb.sh
# vim:fileencoding=utf-8:fdm=marker:ft=sh
#
# Copyright © 2022 R.F. Smith <rsmith@xs4all.nl>
# SPDX-License-Identifier: MIT
# Created: 2022-11-06T11:02:30+0100
# Last modified: 2023-12-11T20:54:47+0100

echo -n "Downloading new package database... "
curl --silent http://pkg.freebsd.org/freebsd:14:x86:64/quarterly/packagesite.txz | \
tar -xOf - packagesite.yaml > new.yaml
echo "done."

diff -q packagesite.yaml new.yaml >/dev/null
DIFFRESULT=$?
if [ $DIFFRESULT -eq 1 ]; then
    NEWNAME=`ls -l -D '%Y%m%d' packagesite.yaml | awk '{printf "%s-%s", $6, $7}'`
    mv -f packagesite.yaml $NEWNAME
    mv new.yaml packagesite.yaml
    echo -n "Updating package files... "
    curl --silent -O --output-dir repo http://pkg.freebsd.org/freebsd:14:x86:64/quarterly/packagesite.txz
    curl --silent -O --output-dir repo http://pkg.freebsd.org/freebsd:14:x86:64/quarterly/packagesite.pkg
    curl --silent -O --output-dir repo http://pkg.freebsd.org/freebsd:14:x86:64/quarterly/meta.txz
    echo "done."
    chmod 400 packagesite.yaml
    ./makedb
elif [ $DIFFRESULT -gt 1 ]; then
    echo "An error occurred. diff returned $DIFFRESULT"
    rm -f new.yaml
else
    echo "No changes in package database."
    rm -f new.yaml
fi

