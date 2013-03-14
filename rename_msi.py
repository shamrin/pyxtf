import os
import sys

execfile('version.py'); ver = __version__

dst = 'wix/XTF_Surveyor_v%s.msi' % ver
if os.path.exists(dst):
    sys.exit("Can't rename MSI, version %s already exists" % ver)
os.rename('wix/XTF_Surveyor.msi', dst)
