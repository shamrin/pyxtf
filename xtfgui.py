import numpy
from GUI import (Application, ScrollableView, Document, Window, Cursor, rgb,
                 Image, Frame, Font, Model, Label, Menu)
from GUI.Files import FileType
from GUI.Geometry import (pt_in_rect, offset_rect, rects_intersect,
                          rect_sized, rect_height, rect_size)
from GUI.StdColors import black, red, light_grey, white
from GUI.StdFonts import system_font
from GUI.StdMenus import basic_menus, edit_cmds, pref_cmds, print_cmds
from GUI.Numerical import image_from_ndarray

class XTFApp(Application):

    def __init__(self):
        Application.__init__(self)
        self.proj_type = FileType(name = "XTF Project", suffix = "project")
        self.file_type = self.proj_type

        menus = basic_menus(
            exclude = edit_cmds + pref_cmds + print_cmds,
            substitutions = {
                'new_cmd': 'New Project',
                'open_cmd': 'Open Project...',
                'save_cmd': 'Save Project',
                'save_as_cmd': 'Save Project As...'})
        profile_menu = Menu("Profiles", [("Import XTF...", 'import_cmd')])
        menus.append(profile_menu)
        self.menus = menus

    def open_app(self):
        self.new_cmd()

    def make_document(self, fileref):
        return Project(file_type = self.proj_type)

    def make_window(self, document):
        win = Window(size = (500, 400), document = document)

        if document.files:
            file_view = FileView(document.files[0])
            win.place(file_view, top = 0, bottom = 0, left = 0, right = 0,
                                 sticky = 'nesw')
        else:
            win.place(Label(text='Open project or import XTF files.',
                            font = Font(system_font.family, 30, 'normal')),
                      top = 20, left = 20)

        win.show()


def normalize(a):
    """Normalize array values to 0.0...255.0 range"""
    a = a.astype(float)
    lo, hi = a.min(), a.max()
    a -= lo
    a *= 255.0 / (hi - lo)
    return a.round()

def rgb_arrays(xtf_file):
    import xtf
    for a in xtf.read_XTF_as_grayscale_arrays(xtf_file):
        a = normalize(a)

        # make grayscale RGB image: [x, y, ...] => [[x, x, x], [y, y, y], ...]
        g = numpy.empty(a.shape + (3,), dtype=numpy.uint8)
        g[...] = a[..., numpy.newaxis]

        yield g

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

        for i, channel in enumerate(image_from_rgb_array(a)
                                    for a in rgb_arrays(filename)):
            view = ChannelView(model = Channel(channel, i+1), scrolling = 'h')
            self.place(view)

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
        canvas.show_text('channel %d' % (self.model.number,))


class Project(Document):

    files = None

    def new_contents(self):
        self.files = []

    def read_contents(self, file):
        self.files = [filename.rstrip() for filename in file]

    def write_contents(self, file):
        for f in self.files:
            file.write(f + '\n')

XTFApp().run()
