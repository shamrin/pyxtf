"""xtf.py - read and show eXtended Triton Format (XTF) files

Usage:
    python xtf.py <path-to-xtf-file>
"""

import sys
import re
from struct import Struct
from pprint import pprint, pformat
from collections import OrderedDict, namedtuple
from itertools import groupby, islice

import numpy as np

CHAN_TYPES = {
    0: 'subbottom',
    1: 'port',
    2: 'stbd',
    3: 'bathymetry',
}
CHAN_INFO_LEN = 128
HEADER_TYPES = {
    0: 'SONAR', # sidescan and subbottom
    1: 'NOTES', # notes - text annotation
    2: 'BATHY', # bathymetry (Seabat, Odom)
    3: 'ATTITUDE', # TSS or MRU attitude (pitch, roll, heave, yaw)
    4: 'FORWARD', # forward-look sonar (polar display)
    5: 'ELAC', # Elac multibeam
    6: 'RAW_SERIAL', # Raw data from serial port
    7: 'EMBED_HEAD', # Embedded header structure
    8: 'HIDDEN_SONAR', # hidden (non-displayable) ping
}
HEADER_LEN = 1024

def read_XTF(infile):
    file_data = memoryview(open(infile, 'rb').read())
    header_len, header = unwrap(file_data,
                                """B file_format == 0x7b !
                                   B system_type
                                   8s recording_program_name
                                   8s recording_program_version
                                   16s sonar_name
                                   H sonar_type
                                   64s note_string
                                   64s this_file_name
                                   H nav_units
                                   H number_of_sonar_channels
                                   H number_of_bathimetry_channels
                                   B number_of_snippet_channels
                                   B number_of_forward_look_arrays
                                   H number_of_echo_strength_channels
                                   B number_of_interferometry_channels
                                   B reserved1
                                   H reserved2
                                   f reference_point_height
                                   12s projection_type
                                   10s spheroid_type
                                   l navigation_latency
                                   f origin_x
                                   f origin_y
                                   f nav_offset_y
                                   f nav_offset_x
                                   f nav_offset_z
                                   f nav_offset_yaw
                                   f MRU_offset_y
                                   f MRU_offset_x
                                   f MRU_offset_z
                                   f MRU_offset_yaw
                                   f MRU_offset_pitch
                                   f MRU_offset_roll
                                """, dict_factory=OrderedDict)
    pprint(header.items())
    nchannels = (header['number_of_sonar_channels'] +
                 header['number_of_bathimetry_channels'])
    assert nchannels <= 6
    print 'Channels:'
    chaninfos = []
    for i in range(nchannels):
        chaninfo_len, chaninfo = unwrap(file_data[header_len+i*CHAN_INFO_LEN:],
                                          """B type_of_channel
                                             B sub_channel_number
                                             H correction_flags
                                             H uni_polar
                                             H bytes_per_sample
                                             I reserved1
                                             16s channel_name
                                             f volt_scale
                                             f frequency
                                             f horiz_beam_angle
                                             f tilt_angle
                                             f beam_width
                                             f offset_x
                                             f offset_y
                                             f offset_z
                                             f offset_yaw
                                             f offset_pitch
                                             f offset_roll
                                             H beams_per_array
                                             54s reserved2
                                          """)
        assert chaninfo_len == CHAN_INFO_LEN
        print '  %d %d %s "%s"' % (i+1,
                                   chaninfo['sub_channel_number'],
                                   CHAN_TYPES[chaninfo['type_of_channel']],
                                   chaninfo['channel_name'])
        #pprint(chaninfo.items())
        chaninfos.append(chaninfo)

    pstart = HEADER_LEN
    return chaninfos, traces_gen(file_data[pstart:], chaninfos)

TraceHeader = namedtuple('TraceHeader', '''channel_number
    ping_date ping_time last_event_number ping_number
    ship_speed ship_longitude ship_latitude
    sensor_speed sensor_longitude sensor_latitude sensor_heading
    layback cable_out slant_range time_delay seconds_per_ping num_samples''')

def traces_gen(data, chaninfos):
    i = 0
    while data:
        sys.stdout.write('\rPacket: %d' % i)

        # only the last message is shown without flush(), but flushing too
        # often slows things down
        if i % 42 == 0:
            sys.stdout.flush()

        pheader_len, pheader = unwrap(data,
                                      """H magic_number == 0xFACE !
                                         B header_type
                                         B sub_channel_number
                                         H num_chans_to_follow
                                         4s reserved1
                                         I num_bytes_this_record
                                      """)
        #pprint(pheader.items())
        header_type = HEADER_TYPES.get(pheader['header_type'], 
                                       'UNKNOWN (%d)' % pheader['header_type'])
        if header_type == 'SONAR':
            sheader_len, sheader = unwrap(data[pheader_len:],
                                          """H year
                                             B month
                                             B day
                                             B hour
                                             B minute
                                             B second
                                             B hseconds
                                             H julian_day
                                             I event_number
                                             I ping_number
                                             f sound_velocity
                                             f ocean_tide
                                             I reserved2
                                             f conductiviy_freq
                                             f temperature_freq
                                             f pressure_freq
                                             f pressure_temp
                                             f conductivity
                                             f water_temperature
                                             f pressure
                                             f computed_sound_velocity
                                             f mag_x
                                             f mag_y
                                             f mag_z
                                             f aux_val1
                                             f aux_val2
                                             f aux_val3
                                             f aux_val4
                                             f aux_val5
                                             f aux_val6
                                             f speed_log
                                             f turbidity
                                             f ship_speed
                                             f ship_gyro
                                             d ship_ycoordinate
                                             d ship_xcoordinate
                                             H ship_alititude
                                             H ship_depth
                                             B fix_time_hour
                                             B fix_time_minute
                                             B fix_time_second
                                             B fix_time_hsecond
                                             f sensor_speed
                                             f KP
                                             d sensor_ycoordinate
                                             d sensor_xcoordinate
                                             H sonar_status
                                             H range_to_fish
                                             H bearing_to_fish
                                             H cable_out
                                             f layback
                                             f cable_tension
                                             f sensor_depth
                                             f sensor_primary_altitude
                                             f sensor_aux_altitude
                                             f sensor_pitch
                                             f sensor_roll
                                             f sensor_heading
                                             f heave
                                             f yaw
                                             I attitude_time_lag
                                             f DOT
                                             I nav_fix_milliseconds
                                             B computer_clock_hour
                                             B computer_clock_minute
                                             B computer_clock_second
                                             B computer_clock_hsec
                                             h fish_position_delta_x
                                             h fish_position_delta_y
                                             B fish_position_error_code
                                             11s reserved3
                                          """, 'XTFPINGHEADER')
            assert pheader_len + sheader_len == 256

            #if i % 99 == 0:
            #    print '% 5d' % i, header_type
            #    pprint(pheader.items())
            #    pprint(sheader.items())

            assert pheader['num_chans_to_follow'] <= 6
            assert pheader['num_chans_to_follow'] == 1, 'Not implemented'
            for channel in range(pheader['num_chans_to_follow']):
                cheader_len, cheader = unwrap(data[pheader_len + sheader_len:],
                                              """H channel_number
                                                 H downsample_method
                                                 f slant_range
                                                 f ground_range
                                                 f time_delay
                                                 f time_duration
                                                 f seconds_per_ping
                                                 H processing_flags
                                                 H frequency
                                                 H initial_gain_code
                                                 H gain_code
                                                 H band_width
                                                 I contact_number
                                                 H contact_classification
                                                 B conact_sub_number
                                                 b contact_type
                                                 I num_samples
                                                 H millivolt_scale
                                                 f contact_time_of_track
                                                 B contact_close_number
                                                 B reserved2
                                                 f fixed_VSOP
                                                 h weight
                                                 4s reserved
                                              """, 'XTFPINGCHANHEADER')
                assert cheader_len == 64
                #if i % 99 == 0:
                #    pprint(cheader.items())

                dstart = (pheader_len + sheader_len +
                          cheader_len * pheader['num_chans_to_follow'])

                n = cheader['num_samples']
                s = chaninfos[cheader['channel_number']]['bytes_per_sample']
                trace = np.frombuffer(data[dstart:dstart+s*n].tobytes(),
                                      {1: np.int8, 2: np.int16}[s])

                trace_header = TraceHeader(
                    ping_date = '%04d-%02d-%02d' % (sheader['year'],
                                                    sheader['month'],
                                                    sheader['day']),
                    ping_time = '%02d:%02d.%02d' % (sheader['minute'],
                                                    sheader['second'],
                                                    sheader['hseconds']),
                    last_event_number = sheader['event_number'],
                    ping_number = sheader['ping_number'],
                    ship_speed = sheader['ship_speed'],
                    ship_longitude = sheader['ship_xcoordinate'],
                    ship_latitude = sheader['ship_ycoordinate'],
                    sensor_speed = sheader['sensor_speed'],
                    sensor_longitude = sheader['sensor_xcoordinate'],
                    sensor_latitude = sheader['sensor_ycoordinate'],
                    layback = sheader['layback'],
                    cable_out = sheader['cable_out'],
                    sensor_heading = sheader['sensor_heading'],
                    channel_number = cheader['channel_number'],
                    slant_range = cheader['slant_range'],
                    time_delay = cheader['time_delay'],
                    seconds_per_ping = cheader['seconds_per_ping'],
                    num_samples = cheader['num_samples'])

                yield trace_header, trace

        elif header_type == 'NOTES':
            nheader_len, nheader = unwrap(data[pheader_len:],
                                          """H year
                                             B month
                                             B day
                                             B hour
                                             B minute
                                             B second
                                             35s reserved
                                             200s notes_text
                                          """)
            #print '% 5d' % i, header_type, repr(nheader['notes_text'])
            #pprint(pheader.items()); pprint(nheader.items())
            assert nheader_len + pheader_len == pheader['num_bytes_this_record']
        else:
            print '% 5d' % i, header_type 

        data = data[pheader['num_bytes_this_record']:]
        i += 1

    sys.stdout.write('\n')

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
        values[i] = values[i].rstrip('\x00\r')

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
        tests = [(i, eval(test, {}, globals()), action)
                 for i, (test, action) in enumerate(tests) if test]

        # string format spec indices
        s_indices = [i for i, c in enumerate(formats)
                       if re.match(r'(\d+)s', c)]

        struct = Struct('<' + ''.join(formats))

        _cache[spec] = struct, names, tests, s_indices
        return _cache[spec]


PLOT_NTRACES = 3000

def read_XTF_as_grayscale_arrays(infile):
    chaninfos, header_trace = read_XTF(infile)
    return len(chaninfos), grayscale_arrays_gen(header_trace, chaninfos)

def grayscale_arrays_gen(header_trace, chaninfos):
    """Iterator over channel info tuples: (number, type, trace_headers, data)

    data - grayscale numpy array (n_traces by trace_len)
    """

    header_trace = sorted(header_trace, key=lambda (h, t): h.channel_number)

    for num, traces in groupby(header_trace, lambda (h, t): h.channel_number):
        traces = list(traces)
        headers = [h for h, t in traces]
        traces = [t for h, t in traces]
        type = CHAN_TYPES[chaninfos[num]['type_of_channel']]

        r = np.vstack(traces).transpose()
        yield num, type, headers, r

def main(infile):
    chaninfos, header_trace = read_XTF(infile)
    header_trace = sorted(header_trace, key=lambda (h, t): h.channel_number)

    channels = [0] * len(chaninfos)
    for h, t in header_trace:
        channels[h.channel_number] += 1

    n_nonempty = len([c for c in channels if c])

    def clicked(*args):
        print 'clicked', args

    #import matplotlib; matplotlib.use('MacOSX')
    from matplotlib import pyplot as P, widgets
    P.suptitle('File: ' + infile)
    P.gcf().canvas.set_window_title("%s - xtf.py" % infile)

    buttons = []

    #first = None
    for i, (channel, traces) in enumerate(groupby(header_trace,
                                                  lambda (h, t):
                                                      h.channel_number)):
        traces = list(t for h, t in islice(traces, PLOT_NTRACES))
        r = np.vstack(traces).transpose()
        print 'Plotting %d traces of channel %d (%.1fMb):' % \
            (min(channels[i], PLOT_NTRACES),
             channel + 1,
             (r.size * r.itemsize) / 10.0**6)
        print r

        ax = P.subplot(n_nonempty, 2, i*2+1) #, sharex=first, sharey=first)
        #if i == 0: first = ax

        ax.set_xlim(0, 500)
        ax.set_ylim(500, 0)

        P.title('Channel %d%s' %
                (channel + 1, ' (part)' if PLOT_NTRACES < channels[i] else ''))
        P.imshow(r, P.cm.gray)

    cbax = P.subplot(2, 2, 2)
    P.title('Choose channels:')
    w = widgets.CheckButtons(cbax, ['ch.%d, %s, traces: %d' %
                                    (c+1, CHAN_TYPES[chaninfos[c]['type_of_channel']], t)
                                    for c, t in enumerate(channels)],
                                   [t > 0 for t in channels])
    w.on_clicked(clicked)

    bax1 = P.subplot(6, 4, 15)
    b1 = widgets.Button(bax1, '<< Prev file')
    b1.on_clicked(clicked)

    bax2 = P.subplot(6, 4, 16)
    b2 = widgets.Button(bax2, 'Next file >>')
    b2.on_clicked(clicked)

    bax3 = P.subplot(6, 2, 10)
    b3 = widgets.Button(bax3, 'Save all files to SEG-Y')
    b3.on_clicked(clicked)

    bax4 = P.subplot(6, 2, 12)
    b4 = widgets.Button(bax4, 'Save all files to XTF')
    b4.on_clicked(clicked)

    P.show()

if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit('Error: wrong arguments\n' + __doc__.rstrip())
    main(*sys.argv[1:])
