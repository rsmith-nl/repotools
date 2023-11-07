# file: Makefile
# vim:fileencoding=utf-8:fdm=marker:ft=make
#
# NOTE: This Makefile is only intended for developers.
#       It is only meant for UNIX-like operating systems.
#       Most of the commands require extra software.
#
# Author: R.F. Smith <rsmith@xs4all.nl>
# Created: 2018-01-21 22:44:51 +0100
# Last modified: 2023-11-07T22:36:13+0100
.POSIX:
.PHONY: help clean check format uninstall zip
.SUFFIXES:

PROJECT:=repotools
REPODIR:=${HOME}/freebsd-quarterly
BINDIR!=python -c 'import sysconfig; print(sysconfig.get_path("scripts", "posix_user"))'

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

install: ${BINDIR}/repotool ${REPODIR}/makedb ${REPODIR}/newdb  ## Install the programs

${REPODIR}/makedb: makedb.py
	install -m 700 makedb.py ${REPODIR}/makedb

${REPODIR}/newdb: newdb.sh
	install -m 700 newdb.sh ${REPODIR}/newdb

${BINDIR}/repotool: repotool.py
	install -m 700 repotool.py ${BINDIR}/repotool

uninstall::  ## Remove the programs
	rm -f ${BINDIR}/repotool
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
