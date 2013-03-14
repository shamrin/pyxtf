from distutils.core import setup
import GUI.py2exe
import py2exe

execfile('version.py')

setup(console = ['xtfgui.py'],
      #windows = [ {'script': 'xtfgui.py', 'version': __version__ }],
      options = { 'py2exe': { 'excludes': ['Tkinter', '_ssl'] }})
