import os

import numpy
from GUI import (Application, ScrollableView, Document, Window, Cursor, rgb,
                 Image, Frame, Font, Model, Label, Menu, ViewBase)
from GUI.Files import FileType
from GUI.FileDialogs import request_old_files
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
    profile_menu = Menu("Profiles", [("Import XTF...", 'import_cmd'),
                                     '-',
                                     (profiles or [], 'profiles_cmd')])
    menus.append(profile_menu)
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
        m.profiles_cmd.enabled = True
        m.profiles_cmd.checked = False
        if self.current_file is not None:
            m.profiles_cmd[self.current_file].checked = True

    def import_cmd(self):
        refs = request_old_files('Select XTF files to import')
        self.document.add_files([os.path.join(r.dir.path, r.name)
                                 for r in refs])

    def profiles_cmd(self, i):
        self.current_file = i
        self.project_changed(self.document)

    def project_changed(self, model):
        self.menus = app_menu([f.replace('/', '\\')
                               for f in sorted(self.document.files)])

        for c in self.contents:
            self.remove(c)

        if self.document.files:
            if self.current_file is None:
                self.current_file = 0
            file_view = FileView(self.document.abspaths()[self.current_file])
            self.place(file_view, top = 0, bottom = 0, left = 0, right = 0,
                                 sticky = 'nesw')
        else:
            self.place(Label(text = 'Open project or import XTF files.',
                             font = Font(system_font.family, 30, 'normal')),
                       top = 20, left = 20)

        self.update_title()

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

def rgb_arrays(xtf_file):
    for number, a in xtf.read_XTF_as_grayscale_arrays(xtf_file):
        a = normalize(a)

        # make grayscale RGB image: [x, y, ...] => [[x, x, x], [y, y, y], ...]
        g = numpy.empty(a.shape + (3,), dtype=numpy.uint8)
        g[...] = a[..., numpy.newaxis]

        yield number, g

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


class FileView(Frame):
    def __init__(self, filename):
        Frame.__init__(self)

        self.filename = filename

        views = []
        try:
            for num, a in rgb_arrays(filename):
                image = image_from_rgb_array(a)
                v = ChannelView(model = Channel(image, num), scrolling = 'h')
                views.append(v)
        except xtf.BadDataError, e:
            # can't place Label directly: FileView content is auto-resized
            frame = Frame()
            frame.place(Label(text = 'Error in %s (%s)' % (filename, e),
                              font = Font(system_font.family, 15, 'normal')),
                        top = 20, left = 20)
            self.place(frame)
        else:
            for v in views:
                self.place(v)

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

    files = None

    def abspaths(self):
        return [f if os.path.isabs(f) else os.path.join(self.file.dir.path, f)
                for f in self.files]

    def new_contents(self):
        self.files = []

    def read_contents(self, file):
        self.files = [filename.rstrip() for filename in file]

    def write_contents(self, file):
        self.files = [self.normpath(f) for f in self.files]
        self.files.sort()
        for f in self.files:
            file.write(f + '\n')
        self.notify_windows()

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
        self.notify_windows()

    def notify_windows(self):
        for window in self.windows:
            window.project_changed(self)


XTFApp().run()
