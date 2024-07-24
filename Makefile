# file: Makefile
# vim:fileencoding=utf-8:fdm=marker:ft=make
#
# NOTE: This Makefile is mainly intended for developers.
#       It is only meant for UNIX-like operating systems.
#       Most of the commands require extra software.
#
# Author: R.F. Smith <rsmith@xs4all.nl>
# Created: 2018-01-21 22:44:51 +0100
# Last modified: 2024-07-24T22:50:38+0200
.POSIX:
.PHONY: help clean check format uninstall zip
.SUFFIXES:

PROJECT:=repotools
REPODIR:=${HOME}/freebsd-quarterly

.if make(zip)
TAGCOMMIT!=git rev-list --tags --max-count=1
TAG!=git describe --tags ${TAGCOMMIT}
.endif

help:
	@echo "Command  Meaning"
	@echo "-------  -------"
	@sed -n -e '/##/s/:.*\#\#/\t/p' -e '/@sed/d' Makefile

clean::  ## Remove generated files.
	rm -f backup-*.tar* ${PROJECT}-*.zip
	find . -type f -name '*.pyc' -delete
	find . -type d -name __pycache__ -delete

check:: .IGNORE ## Run the pylama code checker
	pylama makedb.py repotool.py

format:: ## Reformat all source code using black
	black makedb.py repotool.py

install: ${REPODIR} ${REPODIR}/repotool ${REPODIR}/makedb ${REPODIR}/newdb  ## Install the programs

${REPODIR}:
	install -d ${REPODIR}

${REPODIR}/makedb: makedb.py
	install -m 700 makedb.py ${REPODIR}/makedb

${REPODIR}/newdb: newdb.sh
	install -m 700 newdb.sh ${REPODIR}/newdb

${REPODIR}/repotool: repotool.py
	install -m 700 repotool.py ${REPODIR}/repotool

uninstall::  ## Remove the programs
	rm -f ${REPODIR}/repotool
	rm -f ${REPODIR}/makedb
	rm -f ${REPODIR}/newdb

# Run the test suite
#test::
#	py.test -v

zip:: clean  ## Create a zip-file from the most recent tagged state of the repository.
	cd doc && make clean
	git checkout ${TAG}
	cd .. && zip -r ${PROJECT}-${TAG}.zip ${PROJECT} \
		-x '*/.git/*' '*/.pytest_cache/*' '*/__pycache__/*' '*/.cache/*'
	git checkout main
	mv ../${PROJECT}-${TAG}.zip .
