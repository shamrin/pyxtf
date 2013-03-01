@echo off
C:\Python27\python preprocess.py installer_template.wxs installer.wxs ..\dist
"C:\Program Files (x86)\WiX Toolset v3.7\bin\candle" -nologo -ext "C:\Program Files (x86)\WiX Toolset v3.7\bin\WixUIExtension.dll" installer.wxs
"C:\Program Files (x86)\WiX Toolset v3.7\bin\light" -nologo -sw1032 -spdb -out "XTF_Surveyor" -ext "C:\Program Files (x86)\WiX Toolset v3.7\bin\WixUIExtension.dll" installer.wixobj
