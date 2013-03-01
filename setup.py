from distutils.core import setup
import GUI.py2exe
import py2exe

setup(console = ['xtfgui.py'],
      options = { 'py2exe': { 'excludes': ['Tkinter', '_ssl'] }})
