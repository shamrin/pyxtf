**Note: if you are looking for Python XTF library, you may also want to check out https://github.com/oysstu/pyxtf**

## XTF Surveyor: eXtended Triton Format viewer and converter

![XTF Surveyor screenshot](doc/screenshot.png)

**[Download XTF Surveyor for Windows][download]**

[download]: http://sourceforge.net/projects/pyxtf/files/XTF_Surveyor_v0.7.0.msi/download

**Features:**

* view [XTF (eXtended Triton Format)][XTF] files with subbottom seismic data
* convert selected channels to [SEG-Y][] or (another) XTF file

*Limitation:* side-scan data wasn't tested. It could work, though converting side-scan to SEG-Y doesn't make sense, because SEG-Y is designed for subbottom seismic data.

[XTF]: http://en.wikipedia.org/wiki/EXtended_Triton_Format
[SEG-Y]: http://en.wikipedia.org/wiki/SEG_Y

### Python modules for XTF and SEG-Y

Underneath there are couple Python modules that could be helpful:

* [xtf](xtf.py) - read and write XTF files, convert to SEG-Y;
* [segy](segy.py) - read and write SEG-Y files;
* [sacker](sacker.py) - wrapper around Python `struct` module (used by the modules above).

**Note:** another Python XTF library, by [@oysstu](https://github.com/oysstu): https://github.com/oysstu/pyxtf

### How to build installer (for Windows)

**Note:** The following is neccessary only if you want to create your own `XTF Surveyor-<version>.msi` installer file.

1. Download dependencies – including Python – to `windeps` directory (Make sure you have `curl` and `make` commands. It could be easier to do this step under Unix, then copy files to Windows machine.):

    ```
    make windeps
    ```

2. Install everything from `windeps` directory, starting from Python. All files, except PyGUI, are standard next-next-next installers. Don't run the installers from network drives: it could cause problems. To install PyGUI, unzip it and run inside:

    ```
    c:\Python27\python setup.py install
    ```

3. Download and install [Wix 3.7](http://wix.codeplex.com/downloads/get/582218) (direct link, you may want to install newer version if this page gets too old). Add `"C:\Program Files (x86)\WiX Toolset v3.7\bin\"` to Windows `PATH` variable.

4. Increase version number in `version.py` (if necessary).

5. Build installer:

    ```
    build.cmd
    ```

That's all! Installer should appear in `wix\` directory.
