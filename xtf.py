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
    0: 'SUBBOTTOM',
    1: 'PORT',
    2: 'STBD',
    3: 'BATHYMETRY',
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

def readxtf(infile):
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
        print '  ', i+1, chaninfo['sub_channel_number'], \
              CHAN_TYPES[chaninfo['type_of_channel']], \
              chaninfo['channel_name']
        #pprint(chaninfo.items())

    i = 0
    pstart = HEADER_LEN
    while file_data[pstart:]:
        sys.stdout.write('\rtrace % 4d' % i)
        sys.stdout.flush()

        pheader_len, pheader = unwrap(file_data[pstart:],
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
            sheader_len, sheader = unwrap(file_data[pstart + pheader_len:],
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
            for channel in range(pheader['num_chans_to_follow']):
                cheader_len, cheader = unwrap(file_data[pstart + pheader_len +
                                                        sheader_len:],
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

                dstart = (pstart + pheader_len + sheader_len +
                          cheader_len * pheader['num_chans_to_follow'])

                n = cheader['num_samples']
                s = chaninfo['bytes_per_sample']
                trace = np.frombuffer(file_data[dstart:dstart+s*n].tobytes(),
                                      {1: np.int8, 2: np.int16}[s])
                yield cheader['channel_number'], trace

        elif header_type == 'NOTES':
            nheader_len, nheader = unwrap(file_data[pstart + pheader_len:],
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

        pstart += pheader['num_bytes_this_record']
        i += 1

    sys.stdout.write('\n')

class BadDataError(Exception):
    pass

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
    channel_trace = sorted(readxtf(infile),key=lambda (c, t): c)

    channels = {}
    for c, t in channel_trace:
        channels.setdefault(c, 0)
        channels[c] += 1

    def clicked(name):
        def callback(*args):
            print 'clicked(%s): %s' % (name, args)
        return callback

    from matplotlib import pyplot as P, widgets
    P.suptitle('File: ' + infile)

    buttons = []

    first = None
    for i, (channel, traces) in enumerate(groupby(channel_trace,
                                                  lambda (c, t): c)):
        traces = list(t for c, t in traces)
        r = np.vstack(traces).transpose()
        print 'Plotting channel %d %s:' % (channel+1, r.shape)
        print r

        ax = P.subplot(len(channels), 2, i*2+1, sharex=first, sharey=first)
        if i == 0:
            first = ax
        P.title('Channel %d' % (channel+1))
        P.imshow(r, P.cm.gray)

        bax = P.subplot(len(channels), 2, i*2+2)
        buttons.append(widgets.CheckButtons(bax, ['select channel'], [False]))
        buttons[-1].on_clicked(clicked(channel+1))

    P.show()

if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit('Error: wrong arguments\n' + __doc__.rstrip())
    main(*sys.argv[1:])
