PYMAC = python-2.7.3-macosx10.6.dmg
MPLMAC = matplotlib-1.2.0-py2.7-python.org-macosx10.6.dmg
NPMAC = numpy-1.6.2-py2.7-python.org-macosx10.6.dmg

macdeps:
	mkdir -p macdeps
	cd macdeps; if ! [ -f $(MPLMAC) ]; then curl -O -C - "https://github.com/downloads/matplotlib/matplotlib/$(MPLMAC)"; fi
	cd macdeps; if ! [ -f $(PYMAC) ]; then curl -O "http://python.org/ftp/python/2.7.3/$(PYMAC)"; fi
	cd macdeps; if ! [ -f $(NPMAC) ]; then curl -L -o $(NPMAC) "http://sourceforge.net/projects/numpy/files/NumPy/1.6.2/$(NPMAC)/download"; fi

.PHONY: macdeps
