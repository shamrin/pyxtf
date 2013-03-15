from distutils.core import setup
from subprocess import call

import GUI.py2exe
import py2exe

execfile('version.py')

print 'Building docs via GitHub API...'
call(["c:/Python27/python" , "doc/build_docs", "doc/README_ru.markdown",
                                               "doc/README_ru.html"])

setup(console = ['xtfgui.py'],
      #windows = [ {'script': 'xtfgui.py', 'version': __version__ }],
      options = { 'py2exe': { 'excludes': ['Tkinter', '_ssl'] }},
      data_files = [('.', ['doc/README_ru.html', 'doc/screenshot.png'])])
