#!/bin/sh
# file: newdb.sh
# vim:fileencoding=utf-8:fdm=marker:ft=sh
#
# Copyright © 2022 R.F. Smith <rsmith@xs4all.nl>
# SPDX-License-Identifier: MIT
# Created: 2022-11-06T11:02:30+0100
# Last modified: 2024-09-14T11:09:31+0200

BOLD_WHITE='\033[1;37m'
CYAN='\033[0;36m'
GREEN='\033[0;32m'
PURPLE='\033[0;35m'
BOLD_RED='\033[1;31m'
RED='\033[0;31m'
BOLD_YELLOW='\033[1;33m'
RESET='\033[0m' # No Color

echo -n "Downloading new package database... "
curl --silent -O http://pkg.freebsd.org/freebsd:14:x86:64/quarterly/packagesite.txz
tar -xOf packagesite.txz packagesite.yaml > new.yaml
echo "${GREEN}done.${RESET}"

echo "Verifying public key..."
tar -xOf packagesite.txz packagesite.yaml.pub > new.pub
openssl pkey -pubcheck -pubin -in new.pub -noout
CHECKRESULT=$?
if [ $CHECKRESULT -ne 0 ]; then
    echo "${BOLD_RED}An error occurred. Public key is not valid. Exiting!${RESET}"
    rm -f new.yaml new.pub
    exit 1
else
    echo "${GREEN}done.${RESET}"
fi
echo "Verifying digest..."
tar -xOf packagesite.txz packagesite.yaml.sig > new.sig
sha256 -q new.yaml | tr -d '\n' | \
    openssl dgst -verify new.pub -signature new.sig
CHECKRESULT=$?
if [ $CHECKRESULT -ne 0 ]; then
    echo "${BOLD_RED}An error occurred. Verification failed. Exiting!${RESET}"
    rm -f new.yaml new.pub new.sig
    exit 1
else
    echo "${GREEN}done.${RESET}"
fi
rm -f new.pub new.sig

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
    echo "${GREEN}done.${RESET}"
    chmod 400 packagesite.yaml
    ./makedb
elif [ $DIFFRESULT -gt 1 ]; then
    echo "${BOLD_RED}An error occurred. diff returned $DIFFRESULT${RESET}"
    rm -f new.yaml
else
    echo "${CYAN}No changes in package database.${RESET}"
    rm -f new.yaml
fi

