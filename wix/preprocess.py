import sys
import os
from string import Template

DEFINITION = Template(
"""
<Component Id='$name' Guid='*'>
   <File Id='$name' Name='$name' DiskId='1' Source='$source' />
</Component>""")

REFERENCE = Template(
"""
<ComponentRef Id="$name" />""")

def main(infile, outfile, distdir):
    filenames = os.listdir(distdir)

    defs = '\n<!-- DO NOT EDIT! Added by preprocess.py -->' + \
           ''.join(DEFINITION.substitute(name = n, source = distdir + '\\' +n)
                   for n in filenames) + \
            '\n<!-- end -->'
    refs = '\n<!-- DO NOT EDIT! Added by preprocess.py -->' + \
           ''.join(REFERENCE.substitute(name = n)
                   for n in filenames) + \
            '\n<!-- end -->'

    template = Template(open(infile).read())
    out = open(outfile, 'w')
    out.write(template.substitute(COMPONENT_DEFS=defs, COMPONENT_REFS=refs))

if __name__ == '__main__':
    main(*sys.argv[1:])
