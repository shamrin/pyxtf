@echo off
del /s /q dist
c:\Python27\python setup.py py2exe
del /q wix\XTF_Surveyor.msi
cd wix
build_msi.cmd
cd ..
