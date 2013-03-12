from struct import Struct
import re

class BadDataError(Exception):
    pass

def unwrap(binary, spec, data_name=None, dict_factory=dict):
    """Unwrap `binary` according to `spec`, return (consumed_length, data)

    Basically it's a convenient wrapper around struct.unpack. Each non-empty
    line in spec must be: <struct format> <field name> [== <test> <action>]

    struct format - struct module format producing exactly one value
    field name - dictionary key to put unpacked value into
    test - optional test an unpacked value be equal to
    action - what to do if test failed: `!` (bad data) or `?` (unsupported)

    Example:
    >>> unwrap('\x0a\x00DATA\x00something else', '''h magic == 0x0a !
    ...                                             4s data''')
    (6, {'magic': 10, 'data': 'DATA'})
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

    return length, dict_factory(zip(names, values))

def wrap(data, spec):
    struct, names, tests, s_indices = parse(spec)
    return struct.pack(*[data[name] for name in names])

_cache = {}
def parse(spec):
    try:
        return _cache[spec]
    except KeyError:
        matches = [re.match("""(\w+)           # struct format
                               \s+
                               (\w+)           # field name
                               \s*
                               (==\s*(.+)\ ([!?]))? # optional test-action
                               $""", s.strip(), re.VERBOSE)
                   for s in spec.split('\n') if s and not s.isspace()]

        for n, m in enumerate(matches):
            if not m: raise SyntaxError('Bad unwrap spec, LINE %d' % (n+1))

        formats = [m.group(1) for m in matches]
        names = [m.group(2) for m in matches]

        tests = [(m.group(4), m.group(5)) for m in matches]
        tests = [(i, eval(test, {}), action)
                 for i, (test, action) in enumerate(tests) if test]

        # string format spec indices
        s_indices = [i for i, c in enumerate(formats)
                       if re.match(r'(\d+)s', c)]

        struct = Struct('<' + ''.join(formats))

        _cache[spec] = struct, names, tests, s_indices
        return _cache[spec]

