"""XTF viewer (and converter)"""

import os
import csv

import numpy
from GUI import Application, ScrollableView, Document, Window, Button, rgb
from GUI import Image, Frame, Font, Model, Label, Menu, Column, CheckBox
from GUI.Files import FileType
from GUI.FileDialogs import request_old_files, request_new_file
from GUI.Geometry import (pt_in_rect, offset_rect, rects_intersect,
                          rect_sized, rect_height, rect_size)
from GUI.StdColors import black, red, light_grey, white
from GUI.StdFonts import system_font
from GUI.StdMenus import basic_menus, edit_cmds, pref_cmds, print_cmds
from GUI.Numerical import image_from_ndarray

import xtf

def app_menu(profiles = None):
    menus = basic_menus(
        exclude = edit_cmds + pref_cmds + print_cmds + 'revert_cmd',
        substitutions = {
            'new_cmd': 'New Project',
            'open_cmd': 'Open Project...',
            'save_cmd': 'Save Project',
            'save_as_cmd': 'Save Project As...'})
    menus.append(Menu("Profiles", [("Import XTF files...", 'import_cmd'),
                                    '-',
                                    (profiles or [], 'profiles_cmd')]))
    menus.append(Menu("Export", [("Export to CSV...", 'export_csv_cmd')]))
    return menus

class XTFApp(Application):

    def __init__(self):
        Application.__init__(self)
        self.proj_type = FileType(name = "XTF Project", suffix = "project")
        self.file_type = self.proj_type
        self.menus = []

    def open_app(self):
        self.new_cmd()

    def make_document(self, fileref):
        return Project(file_type = self.proj_type)

    def make_window(self, document):
        ProjectWindow(document).show()


class ProjectWindow(Window):
    def __init__(self, document):
        self.current_file = None
        Window.__init__(self, size = (500, 400), document = document)
        self.project_changed(document)

    def setup_menus(self, m):
        Window.setup_menus(self, m)
        m.import_cmd.enabled = True
        if self.current_file is not None:
            m.export_csv_cmd.enabled = True
        m.profiles_cmd.enabled = True
        m.profiles_cmd.checked = False
        if self.current_file is not None:
            m.profiles_cmd[self.current_file].checked = True

    def import_cmd(self):
        refs = request_old_files('Import XTF files')
        if refs is not None:
            self.document.add_files([os.path.join(r.dir.path, r.name)
                                     for r in refs])

    def profiles_cmd(self, i):
        self.current_file = i
        self.project_changed(self.document)

    def export_csv_cmd(self):
        self.xtf_file.export_csv()

    def save_xtf_cmd(self):
        numbers = [i for i, cb in enumerate(self.checkboxes) if cb.value]
        self.xtf_file.save_xtf(numbers)

    def project_changed(self, model, recent_filename = None):
        doc = self.document
        self.menus = app_menu([f.replace('/', '\\')
                               for f in sorted(doc.files)])

        for c in list(self.contents):
            self.remove(c)

        if doc.files:
            if self.current_file is None:
                self.current_file = 0
            if recent_filename is not None:
                self.current_file = doc.files.index(recent_filename)

            filename = doc.abspaths()[self.current_file]
            try:
                self.xtf_file = XTFFile(filename)
            except xtf.BadDataError, e:
                self.place(Label(text = 'Error in %s (%s)' % (filename, e),
                                 font = Font(system_font.family, 15, 'normal')),
                           top = 20, left = 20)
            else:
                panel = Frame()
                checks = [CheckBox(', '.join(w for w in
                                             ['channel %d' % (c+1),
                                              self.xtf_file.types.get(c),
                                              'traces: %d' % n] if w),
                                   enabled = n > 0, value = n > 0,
                                   action = 'select_channel')
                          for c, n in enumerate(self.xtf_file.ntraces)]
                button = Button('Save to XTF...', action = 'save_xtf_cmd')
                panel.place_column(checks + [button], top = 10, left = 10)
                panel.shrink_wrap(padding = (40, 40))
                self.place(panel, top = 0, bottom = 0, right = 0,
                           sticky = 'nse')
                self.checkboxes = checks
                self.save_xtf_btn = button

                file_view = FileView(self.xtf_file)
                self.place(file_view, top = 0, bottom = 0, left = 0,
                                      right = panel, sticky = 'nesw')
        else:
            self.place(Label(text = 'Open project or import XTF files.',
                             font = Font(system_font.family, 30, 'normal')),
                       top = 20, left = 20)

        self.update_title()

        # make sure .setup_menus() gets called
        # (it usually does, except after toggle-some-control-then-change-file)
        self.become_target()

    def select_channel(self):
        self.save_xtf_btn.enabled = any(cb.value for cb in self.checkboxes)

    def update_title(self):
        doc = self.document
        if self.current_file is None:
            self.set_title(doc.title)
        else:
            self.set_title('%s - %s' %
                           (doc.files[self.current_file], doc.title))


def normalize(a):
    """Normalize array values to 0.0...255.0 range"""
    a = a.astype(float)
    lo, hi = a.min(), a.max()
    a -= lo
    a *= 255.0 / (hi - lo)
    return a.round()

def rgb_array(gray):
    a = normalize(gray)

    # make grayscale RGB image: [x, y, ...] => [[x, x, x], [y, y, y], ...]
    g = numpy.empty(a.shape + (3,), dtype=numpy.uint8)
    g[...] = a[..., numpy.newaxis]

    return g

def image_from_rgb_array(array):
    # based on image_from_ndarray and (buggy) GDIPlus.Bitmap.from_data

    from GUI import GDIPlus as gdi
    from ctypes import c_void_p, byref

    height, width, bytes_per_pixel = array.shape
    assert bytes_per_pixel == 3
    assert array.dtype == numpy.uint8
    format = gdi.PixelFormat24bppRGB

    # make sure that image width is divisable by 4
    pad = -width % 4
    stride = (width + pad) * bytes_per_pixel
    if pad:
        p = numpy.empty((height, pad, bytes_per_pixel), dtype = numpy.uint8)
        array = numpy.hstack((array, p))

    # create and fill GDI+ bitmap
    bitmap = gdi.Bitmap.__new__(gdi.Bitmap)
    ptr = c_void_p()
    data = array.tostring() # FIXME works only for gray images...
    if gdi.wg.GdipCreateBitmapFromScan0(width, height, stride, format, data,
                                        byref(ptr)) != 0:
        raise Exception('GDI+ Error')
    bitmap.ptr = ptr

    # create Image object
    image = Image.__new__(Image)
    image._win_image = bitmap
    image._data = data # is it really needed? (image_from_ndarray does it too)

    return image


class XTFFile(object):
    def __init__(self, filename):
        self.filename = filename

        header, nchannels, arrays = xtf.read_XTF_as_grayscale_arrays(filename)
        print 'File %r, header:' % (filename,)
        print '  ' + '\n  '.join('%s: %r' % (k.replace('_', ' '), v)
                                 for k, v in header.items())

        self.headers = []
        self.channels = []
        self.ntraces = [0] * nchannels
        self.types = {}

        for num, type, headers, a in arrays:
            a = rgb_array(a)
            self.ntraces[num] = len(headers)
            self.types[num] = type
            self.headers.extend(headers)
            image = image_from_rgb_array(a)
            self.channels.append(Channel(image, num))

    csv_type = FileType(name = 'CSV file', suffix = 'csv')
    xtf_type = FileType(name = 'XTF file', suffix = 'xtf')

    def export_csv(self):
        ref = request_new_file('Export CSV file', file_type = self.csv_type)
        if ref is not None:
            outfile = csv.writer(ref.open('wb'), delimiter = ';')
            outfile.writerow([n.replace('_', ' ').capitalize()
                              for n in xtf.TraceHeader._fields])
            for header in self.headers:
                outfile.writerow(header)

    def save_xtf(self, channel_numbers):
        ref = request_new_file('Save XTF file', file_type = self.xtf_type)
        if ref is not None:
            xtf.copy_XTF(self.filename, os.path.join(ref.dir.path, ref.name),
                         channel_numbers)


class FileView(Frame):
    def __init__(self, xtf_file):
        Frame.__init__(self)

        for channel in xtf_file.channels:
            self.place(ChannelView(model = channel, scrolling = 'h'))
        self.resized((0, 0))

    def resized(self, delta):
        # make sure content components evenly fill all the space
        n = len(self.contents)
        for i, content in enumerate(self.contents):
            W, H = self.content_size
            content.bounds = 0, H / n * i, W, H / n * (i + 1)


class Channel(Model):
    def __init__(self, image, number):
        Model.__init__(self)
        self.image = image
        self.number = number


class ChannelView(ScrollableView):

    def draw(self, canvas, update_rect):
        #canvas.erase_rect(update_rect)

        # Draw channel image, scaled to fit the view vertically
        image = self.model.image
        W, H = image.size
        h = rect_height(self.viewed_rect())
        dst_rect = (0, 0, int(float(h) * W / H), h)
        image.draw(canvas, image.bounds, dst_rect)
        self.extent = rect_size(dst_rect)

        # Draw channel title
        canvas.moveto(10, self.height / 2)
        canvas.font = Font(system_font.family, 30, 'normal')
        canvas.textcolor = rgb(0.2, 0.4, 0.6)
        canvas.show_text('channel %d' % (self.model.number+1,))


class Project(Document):
    magic = 'XTF PROJECT'
    files = None

    def abspaths(self):
        return [f if os.path.isabs(f) else os.path.join(self.file.dir.path, f)
                for f in self.files]

    def new_contents(self):
        self.files = []

    def read_contents(self, file):
        if file.next().rstrip() != self.magic:
            raise RuntimeError('Bad project file')
        self.files = [filename.rstrip() for filename in file]

    def write_contents(self, file):
        file.write(self.magic + '\n')
        self.files = [self.normpath(f) for f in self.files]
        self.files.sort()
        for f in self.files:
            file.write(f + '\n')
        self.notify_windows('project_changed')

    def normpath(self, p):
        if self.file:
            proj_dir = os.path.abspath(self.file.dir.path)
            if os.path.abspath(p).startswith(proj_dir):
                p = os.path.relpath(p, proj_dir)
        return p.replace('\\', '/')

    def add_files(self, filenames):
        for f in filenames:
            f = self.normpath(f)
            if f not in self.files:
                self.files.append(f)
                self.changed()
        self.files.sort()
        self.notify_windows('project_changed', self.normpath(filenames[0]))

    def notify_windows(self, *event):
        for window in self.windows:
            getattr(window, event[0])(self, *event[1:])


XTFApp().run()
