#!/bin/sh
# file: newdb.sh
# vim:fileencoding=utf-8:fdm=marker:ft=sh
#
# Copyright © 2022 R.F. Smith <rsmith@xs4all.nl>
# SPDX-License-Identifier: MIT
# Created: 2022-11-06T11:02:30+0100
# Last modified: 2024-07-25T09:00:25+0200

echo -n "Downloading new package database... "
curl --silent -O http://pkg.freebsd.org/freebsd:14:x86:64/quarterly/packagesite.txz
tar -xOf packagesite.txz packagesite.yaml > new.yaml
echo "done."

echo "Verifying public key..."
tar -xOf packagesite.txz packagesite.yaml.pub > new.pub
openssl pkey -pubcheck -pubin -in new.pub -noout
CHECKRESULT=$?
if [ $CHECKRESULT -ne 0 ]; then
    echo "An error occurred. Public key is not valid. Exiting!"
    rm -f new.yaml new.pub
    exit 1
fi
echo "done."
echo "Verifying digest..."
tar -xOf packagesite.txz packagesite.yaml.sig > new.sig
sha256 -q packagesite.yaml | tr -d '\n' | \
    openssl dgst -verify new.pub -signature new.sig
CHECKRESULT=$?
if [ $CHECKRESULT -ne 0 ]; then
    echo "An error occurred. Verification failed. Exiting!"
    rm -f new.yaml new.pub new.sig
    exit 1
fi
rm -f new.pub new.sig
echo "done."

diff -q packagesite.yaml new.yaml >/dev/null
DIFFRESULT=$?
if [ $DIFFRESULT -eq 1 ]; then
    NEWNAME=`ls -l -D '%Y%m%d' packagesite.yaml | awk '{printf "%s-%s", $6, $7}'`
    mv -f packagesite.yaml $NEWNAME
    mv new.yaml packagesite.yaml
    echo -n "Updating package files... "
    curl --silent -O --output-dir repo http://pkg.freebsd.org/freebsd:14:x86:64/quarterly/packagesite.txz
    cp -p repo/packagesite.txz repo/packagesite.pkg
    curl --silent -O --output-dir repo http://pkg.freebsd.org/freebsd:14:x86:64/quarterly/data.txz
    cp -p repo/data.txz repo/data.pkg
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

