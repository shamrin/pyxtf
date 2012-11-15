"""xtf.py - read and show eXtended Triton Format (XTF) files

Usage:
    python xtf.py <path-to-xtf-file>
"""

import sys
import re
import struct
from pprint import pprint, pformat
from collections import OrderedDict
from itertools import groupby

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
                                          """, dict_factory=OrderedDict)
        assert chaninfo_len == CHAN_INFO_LEN
        print '  %d %d %s "%s"' % (i+1,
                                   chaninfo['sub_channel_number'],
                                   CHAN_TYPES[chaninfo['type_of_channel']],
                                   chaninfo['channel_name'])
        #pprint(chaninfo.items())
        chaninfos.append(chaninfo)

    pstart = HEADER_LEN
    return chaninfos, traces_gen(file_data[pstart:], chaninfos)

def traces_gen(data, chaninfos):
    i = 0
    while data:
        sys.stdout.write('\rtrace % 4d' % i)
        sys.stdout.flush()

        pheader_len, pheader = unwrap(data,
                                      """H magic_number == 0xFACE !
                                         B header_type
                                         B sub_channel_number
                                         H num_chans_to_follow
                                         4s reserved1
                                         I num_bytes_this_record
                                      """, dict_factory=OrderedDict)
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
                                          """, 'XTFPINGHEADER',
                                          dict_factory=OrderedDict)
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
                                              """, 'XTFPINGCHANHEADER',
                                              dict_factory=OrderedDict)
                assert cheader_len == 64
                #if i % 99 == 0:
                #    pprint(cheader.items())

                dstart = (pheader_len + sheader_len +
                          cheader_len * pheader['num_chans_to_follow'])

                n = cheader['num_samples']
                s = chaninfos[cheader['channel_number']]['bytes_per_sample']
                trace = np.frombuffer(data[dstart:dstart+s*n].tobytes(),
                                      {1: np.int8, 2: np.int16}[s])
                yield cheader['channel_number'], trace

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
                                          """, dict_factory=OrderedDict)
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

_unwrap_cache = {}
def unwrap(binary, spec, data_name=None, dict_factory=dict):
    """Unwrap `binary` according to `spec`, return (consumed_length, data)

    Basically it's a convenient wrapper around struct.unpack. Each non-empty
    line in spec must be: <struct format> <field name> [<test> <action>]

    struct format - struct module format producing exactly one value
    field name - dictionary key to put unpacked value into
    test - optional test (unpacked) value should pass
    action - what to do if test failed: `!` (bad data) or `?` (unsupported)

    Example:
    >>> unwrap('\x0a\x00DATA\x00something else', '''h magic == 0x0a !
    ...                                             4s data''')
    (6, {'magic': 10, 'data': 'DATA'})
    """

    if spec in _unwrap_cache:
        formats, names, tests = _unwrap_cache[spec]
    else:
        matches = [re.match("""(\w+)           # struct format
                               \s+
                               (\w+)           # field name
                               ((.+)\ ([!?]))? # optional test-action pair
                               $""", s.strip(), re.VERBOSE)
                   for s in spec.split('\n') if s and not s.isspace()]

        for n, m in enumerate(matches):
            if not m: raise SyntaxError('Bad unwrap spec, LINE %d' % (n+1))

        formats = [m.group(1) for m in matches]
        names = [m.group(2) for m in matches]
        tests = [(m.group(4), m.group(5)) for m in matches]
        _unwrap_cache[spec] = formats, names, tests

    # unpack binary data
    fmt = '<' + ''.join(formats)
    length = struct.calcsize(fmt)
    sub = binary[:length]
    if isinstance(sub, memoryview):
        sub = sub.tobytes()
    values = list(struct.unpack(fmt, sub))

    # rstrip null bytes and '\r' from strings
    for i, c in enumerate(formats):
        if re.match(r'(\d+)s', c):
            values[i] = values[i].rstrip('\x00\r')

    # run optional tests
    for v, name, (test, action) in zip(values, names, tests):
        if test and not eval(name + test, {name: v}, globals()):
            adj = {'!': 'Bad', '?': 'Unsupported'}[action]
            raise BadDataError(' '.join(w for w in
                    [adj, data_name, name, '== %r' % v] if w))

    return length, dict_factory(zip(names, values))

def main(infile):
    chaninfos, channel_trace = read_XTF(infile)
    channel_trace = sorted(channel_trace, key=lambda (c, t): c)

    channels = [0] * len(chaninfos)
    for c, t in channel_trace:
        channels[c] += 1

    n_nonempty = len([c for c in channels if c])

    def clicked(*args):
        print 'clicked', args

    #import matplotlib; matplotlib.use('MacOSX')
    from matplotlib import pyplot as P, widgets
    P.suptitle('File: ' + infile)
    P.gcf().canvas.set_window_title("%s - xtf.py" % infile)

    buttons = []

    #first = None
    for i, (channel, traces) in enumerate(groupby(channel_trace,
                                                  lambda (c, t): c)):
        traces = list(t for c, t in traces)
        r = np.vstack(traces).transpose()
        print 'Plotting channel %d %s:' % (channel+1, r.shape)
        print r

        ax = P.subplot(n_nonempty, 2, i*2+1) #, sharex=first, sharey=first)
        #if i == 0: first = ax

        ax.set_xlim(0, 500)
        ax.set_ylim(500, 0)

        P.title('Channel %d' % (channel+1))
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
