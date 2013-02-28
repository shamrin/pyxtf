import json

import numpy
from GUI import Application, ScrollableView, Document, Window, Cursor, rgb, Image, Frame, Font, Model
from GUI.Files import FileType
from GUI.Geometry import pt_in_rect, offset_rect, rects_intersect, rect_sized, rect_height, rect_size
from GUI.StdColors import black, red, light_grey, white
from GUI.StdFonts import system_font
from GUI.Numerical import image_from_ndarray

class XTFApp(Application):

    def __init__(self):
        Application.__init__(self)
        self.proj_type = FileType(name = "XTF Project", suffix = "project")
        self.file_type = self.proj_type

    def open_app(self):
        self.new_cmd()

    def make_document(self, fileref):
        return Project(file_type = self.proj_type)

    def make_window(self, document):
        win = Window(size = (400, 600), document = document)

        file_view = FileView(document)
        win.place(file_view, top = 0, bottom = 0, left = 0, right = 0,
                             sticky = 'nesw')

        win.show()


def normalize(a):
    """Normalize array values to 0.0...255.0 range"""
    a = a.astype(float)
    lo, hi = a.min(), a.max()
    a -= lo
    a *= 255.0 / (hi - lo)
    return a.round()

def arrays(xtf_file):
    import xtf
    for a in xtf.read_XTF_as_numpy_images(xtf_file):
        a = normalize(a)

        # make grayscale RGB image: [x, y, ...] => [[x, x, x], [y, y, y], ...]
        g = numpy.empty(a.shape + (3,), dtype=numpy.uint8)
        g[...] = a[..., numpy.newaxis]

        yield g

class FileView(Frame):
    def __init__(self, document):
        Frame.__init__(self)

        self.document = document

        for i, channel in enumerate(image_from_ndarray(a, 'RGB')
                                    for a in arrays(self.document.files[0])):
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
        print self.files

    def write_contents(self, file):
        for f in self.files:
            file.write(f + '\n')

XTFApp().run()
