"""sacker - convenient wrappers around struct.pack and struct.unpack"""

from struct import Struct
import re

class BadDataError(Exception):
    pass

def unwrap(binary, spec, data_name=None, data_factory=dict):
    r"""Unwrap `binary` according to `spec`, return (consumed_length, data)

    Basically it's a convenient wrapper around struct.unpack. Each non-empty
    line in spec must be: <struct format> <field name> [== <test> <action>]

    <struct format> - struct format producing one value (except for 'x' format)
    <field name> - dictionary key to put unpacked value into
    <test> - optional test an unpacked value be equal to
    <action> - what to do when test fails: `!` (bad data) or `?` (unsupported)

    Example:
    >>> unwrap('\xff\x00DATA1234\x10something else', '''# comment
    ...                                                 H magic == 0xff !
    ...                                                 4s data
    ...                                                 4x
    ...                                                 b byte''',
    ...                                              data_factory = list)
    (11, [('magic', 255), ('data', 'DATA'), ('byte', 16)])
    """

    struct, names, tests, s_indices = parse(spec)

    # unpack binary data
    length = struct.size
    sub = binary[:length]
    if isinstance(sub, memoryview):
        sub = sub.tobytes()
    values = list(struct.unpack(sub))

    # strip padding from end of strings
    for i in s_indices:
        values[i] = values[i].rstrip('\x00')

    # run optional tests
    for i, test, action in tests:
        if values[i] != test:
            adj = {'!': 'Bad', '?': 'Unsupported'}[action]
            raise BadDataError(' '.join(w for w in
                    [adj, data_name, names[i], '== %r' % values[i]] if w))

    return length, data_factory(zip(names, values))

def wrap(data, spec):
    r"""Wrap `data` dict to binary according to `spec`. Opposite of `unwrap`.

    Example:
    >>> wrap({'data': 'DATA', 'num': 121},'''4s data
    ...                                      b num
    ...                                      h opt    # missing data means 0
    ...                                   ''')
    'DATAy\x00\x00'
    """

    struct, names, tests, s_indices = parse(spec)
    return struct.pack(*[data.get(name, 0) for name in names])

def strip(s):
    try:
        s = s[:s.index('#')]
    except ValueError:
        pass
    return s.strip()

_cache = {}
def parse(spec):
    try:
        return _cache[spec]
    except KeyError:
        matches = [re.match("""(?P<format>\w+)
                               (
                                 \s+
                                 (?P<name>\w+)
                                 \s*
                                 (==\s*(?P<test>.+)
                                    \ (?P<action>[!?]))?
                               )?
                               $""", strip(s), re.VERBOSE)
                   for s in spec.split('\n') if strip(s)]

        for n, m in enumerate(matches):
            if not m:
                raise SyntaxError('Bad spec, LINE %d' % (n+1))
            if not (m.group('name') or re.match('(\d+)x', m.group('format'))):
                raise SyntaxError('Bad spec, name required, LINE %d' % (n+1))

        formats = [m.group('format') for m in matches if m.group('name')]
        names = [m.group('name') for m in matches if m.group('name')]

        tests = [(m.group('test'), m.group('action')) for m in matches]
        tests = [(i, eval(test, {}), action)
                 for i, (test, action) in enumerate(tests) if test]

        # string format spec indices
        s_indices = [i for i, c in enumerate(formats)
                       if re.match(r'(\d+)s', c)]

        struct = Struct('<' + ''.join(m.group('format') for m in matches))

        _cache[spec] = struct, names, tests, s_indices
        return _cache[spec]

if __name__ == '__main__':
    import doctest
    doctest.testmod()
