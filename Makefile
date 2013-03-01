PYMAC = python-2.7.3-macosx10.6.dmg
MPLMAC = matplotlib-1.2.0-py2.7-python.org-macosx10.6.dmg
NPMAC = numpy-1.6.2-py2.7-python.org-macosx10.6.dmg

PYWIN = python-2.7.3.msi
NPWIN = numpy-1.7.0-win32-superpack-python2.7.exe
PY2EXE = py2exe-0.6.9.win32-py2.7.exe
PYGUI = PyGUI-2.5.3.tar.gz
WIN32 = pywin32-218.win32-py2.7.exe

macdeps:
	mkdir -p macdeps
	cd macdeps; if ! [ -f $(MPLMAC) ]; then curl -O -C - "https://github.com/downloads/matplotlib/matplotlib/$(MPLMAC)"; fi
	cd macdeps; if ! [ -f $(PYMAC) ]; then curl -O "http://python.org/ftp/python/2.7.3/$(PYMAC)"; fi
	cd macdeps; if ! [ -f $(NPMAC) ]; then curl -L -o $(NPMAC) "http://sourceforge.net/projects/numpy/files/NumPy/1.6.2/$(NPMAC)/download"; fi

windeps:
	mkdir -p windeps
	cd windeps; if ! [ -f $(PYWIN) ]; then curl -O "http://python.org/ftp/python/2.7.3/$(PYWIN)"; fi
	cd windeps; if ! [ -f $(NPWIN) ]; then curl -L -o $(NPWIN) "http://sourceforge.net/projects/numpy/files/NumPy/1.7.0/$(NPWIN)/download"; fi
	cd windeps; if ! [ -f $(WIN32) ]; then curl -L -o $(WIN32) "http://sourceforge.net/projects/pywin32/files/pywin32/Build%20218/$(WIN32)/download"; fi
	cd windeps; if ! [ -f $(PY2EXE) ]; then curl -L -o $(PY2EXE) "http://sourceforge.net/projects/py2exe/files/py2exe/0.6.9/$(PY2EXE)/download"; fi
	cd windeps; if ! [ -f $(PYGUI) ]; then curl -O "http://www.cosc.canterbury.ac.nz/greg.ewing/python_gui/$(PYGUI)"; fi

.PHONY: macdeps windeps
