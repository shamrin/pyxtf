"""xtf.py - read and show eXtended Triton Format (XTF) files

From command line:
    python xtf.py <path-to-xtf-file>
"""

import sys
from pprint import pprint, pformat
from collections import OrderedDict, namedtuple
from itertools import groupby, islice, chain
from getpass import getuser
from datetime import datetime
from string import Template
import re

import numpy as np

import version
from sacker import wrap, unwrap, BadDataError
import segy

def UTMParams(auto = False, zone = None, south = None):
    if auto:
        assert not zone and south is None
    else:
        assert zone and south is not None
    return namedtuple('UTM', 'auto zone south')(auto, zone, south)

# XTF spec: http://www.tritonimaginginc.com/site/content/public/downloads/FileFormatInfo/Xtf%20File%20Format_X35.pdf

CHAN_TYPES = {
    0: 'subbottom',
    1: 'port',
    2: 'stbd',
    3: 'bathymetry',
}
CHANINFO_LEN = 128
HEADER_TYPES = {
    0: 'sonar', # sidescan and subbottom
    1: 'notes', # notes - text annotation
    2: 'bathy', # bathymetry (Seabat, Odom)
    3: 'attitude', # TSS or MRU attitude (pitch, roll, heave, yaw)
    4: 'forward', # forward-look sonar (polar display)
    5: 'elac', # Elac multibeam
    6: 'raw_serial', # Raw data from serial port
    7: 'embed_head', # Embedded header structure
    8: 'hidden_sonar', # hidden (non-displayable) ping
}
HEADER_LEN = 1024

HEADER = """
    B file_format == 0x7b !
    B system_type
    8s recording_program_name
    8s recording_program_version
    16s sonar_name
    H sonar_type
    64s note_string
    64s this_file_name
    H nav_units
    H number_of_sonar_channels
    H number_of_bathymetry_channels
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
"""

CHANINFO = """
    B type_of_channel
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
"""

def read_XTF(infile, packet_filter):
    file_data = memoryview(open(infile, 'rb').read())
    header_len, header = unwrap(file_data, HEADER, data_factory = OrderedDict)
    nchannels = (header['number_of_sonar_channels'] +
                 header['number_of_bathymetry_channels'])
    assert nchannels <= 6
    chaninfos = []
    for i in range(nchannels):
        chaninfo_len, chaninfo = unwrap(file_data[header_len+i*CHANINFO_LEN:],
                                        CHANINFO)
        assert chaninfo_len == CHANINFO_LEN
        chaninfos.append(chaninfo)

    pstart = HEADER_LEN
    return header, chaninfos, packets_gen(file_data[pstart:], chaninfos,
                                          packet_filter)

def pad(s, width):
    assert len(s) <= width
    return s.ljust(width, '\x00')

def write_XTF(outfile, header, chaninfos, packets):
    with open(outfile, 'wb') as out:
        out.write(pad(''.join([wrap(header, HEADER)] +
                              [wrap(c, CHANINFO) for c in chaninfos]),
                      HEADER_LEN))

        for p in packets:
            if hasattr(p, 'sheader'): # sonar packet
                out.write(pad(''.join([wrap(p.pheader, PACKET_HEADER),
                                       wrap(p.sheader, SONAR_HEADER),
                                       wrap(p.cheader, SONAR_CHANNEL_HEADER),
                                       p.raw_trace]),
                              p.pheader['num_bytes_this_record']))
            else:
                assert len(p.raw) == p.pheader['num_bytes_this_record']
                out.write(p.raw)


TraceHeader = namedtuple('TraceHeader', '''channel_number
    ping_date ping_time last_event_number ping_number
    ship_speed ship_longitude ship_latitude
    sensor_speed sensor_longitude sensor_latitude sensor_heading
    layback cable_out slant_range time_delay seconds_per_ping num_samples''')

Packet = namedtuple('Packet', 'pheader raw')

class SonarPacket(namedtuple('SonarPacket',
                             'pheader sheader cheader trace raw_trace')):
    __slots__ = () # prevent instance dict creation (see namedtuple docs)

    def trace_header(self):
        sheader, cheader = self.sheader, self.cheader
        return TraceHeader(
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

    @property
    def channel_number(self):
        return self.cheader['channel_number']

def header_type(pheader):
    return HEADER_TYPES.get(pheader['header_type'],
                                   'UNKNOWN (%d)' % pheader['header_type'])

PACKET_HEADER = """
    H magic_number == 0xFACE !
    B header_type
    B sub_channel_number
    H num_chans_to_follow
    4s reserved1
    I num_bytes_this_record
"""

SONAR_HEADER = """
    H year
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
"""

SONAR_CHANNEL_HEADER = """
    H channel_number
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
    B contact_sub_number
    b contact_type
    I num_samples
    H millivolt_scale
    f contact_time_of_track
    B contact_close_number
    B reserved2
    f fixed_VSOP
    h weight
    4s reserved
"""

def packets_gen(data, chaninfos, packet_filter):
    i = 0
    while data:
        pheader_len, pheader = unwrap(data, PACKET_HEADER)
        type = header_type(pheader)

        if packet_filter == '*' or type == packet_filter.lower():
            if type == 'sonar':
                sheader_len, sheader = unwrap(data[pheader_len:],
                                              SONAR_HEADER, 'XTFPINGHEADER')
                assert pheader_len + sheader_len == 256

                assert pheader['num_chans_to_follow'] <= 6
                if pheader['num_chans_to_follow'] > 1:
                    raise NotImplementedError('Multiple channels in a packet')

                cheader_len, cheader = unwrap(data[pheader_len + sheader_len:],
                                              SONAR_CHANNEL_HEADER,
                                              'XTFPINGCHANHEADER')
                assert cheader_len == 64

                dstart = (pheader_len + sheader_len +
                          cheader_len * pheader['num_chans_to_follow'])

                n = cheader['num_samples']
                s = chaninfos[cheader['channel_number']]['bytes_per_sample']
                raw_trace = data[dstart:dstart+s*n].tobytes()
                trace = np.frombuffer(raw_trace, {1: np.int8, 2: np.int16}[s])

                yield SonarPacket(pheader, sheader, cheader, trace, raw_trace)
            #elif type == 'notes':
            #    nheader_len, nheader = unwrap(data[pheader_len:],
            #                                  """H year
            #                                     B month
            #                                     B day
            #                                     B hour
            #                                     B minute
            #                                     B second
            #                                     35s reserved
            #                                     200s notes_text
            #                                  """)
            #    pprint(nheader)
            #    assert nheader_len + pheader_len == \
            #        pheader['num_bytes_this_record']
            else:
                yield Packet(pheader, data[:pheader['num_bytes_this_record']])

        sys.stdout.write('Packet: %d\r' % i)

        # only the last message is shown without flush(), but flushing too
        # often slows things down
        if i % 42 == 0:
            sys.stdout.flush()

        data = data[pheader['num_bytes_this_record']:]
        i += 1

    sys.stdout.write('\n')

def read_XTF_as_grayscale_arrays(infile):
    header, chaninfos, packets = read_XTF(infile, 'sonar')
    return header, len(chaninfos), grayscale_arrays_gen(packets, chaninfos)

def grayscale_arrays_gen(packets, chaninfos):
    """Iterator over channel info tuples: (number, type, trace_headers, data)

    data - grayscale numpy array (n_traces by trace_len)
    """

    packets = sorted(packets, key=lambda p: p.channel_number)

    for num, packets in groupby(packets, lambda p: p.channel_number):
        packets = list(packets)
        headers = [p.trace_header() for p in packets]
        traces = [p.trace for p in packets]
        type = CHAN_TYPES[chaninfos[num]['type_of_channel']]

        r = np.vstack(traces).transpose()
        yield num, type, headers, r

def export_XTF(infile, outfile, channel_numbers):
    header, chaninfos, packets = read_XTF(infile, '*')

    channel_numbers = sorted(set(channel_numbers))
    chaninfos = [chaninfos[ch] for ch, info in enumerate(chaninfos)
                               if ch in channel_numbers]

    n_bathymetry = len([c for c in chaninfos
                        if CHAN_TYPES[c['type_of_channel']] == 'bathymetry'])
    header['number_of_bathymetry_channels'] = n_bathymetry
    header['number_of_sonar_channels'] = len(chaninfos) - n_bathymetry

    def packets_gen():
        for p in packets:
            if header_type(p.pheader) == 'sonar':
                if p.channel_number in channel_numbers:
                    p.cheader['channel_number'] = \
                            channel_numbers.index(p.channel_number)
                    yield p
            else:
                yield p

    write_XTF(outfile, header, chaninfos, packets_gen())

def export_SEGY(infile, outfile, (channel_number,),
                to_utm = True, utm_params = UTMParams(auto = True)):
    header, chaninfos, packets = read_XTF(infile, 'sonar')
    try:
        chaninfo = chaninfos[channel_number]
    except IndexError:
        raise BadDataError('Channel %d not found in %r' %
                                            (channel_number + 1, infile))

    packets = (p for p in packets if p.channel_number == channel_number)

    # peek first packet, and keep generator intact
    p0 = packets.next()
    packets = chain([p0], packets)

    sample_interval = int(round(p0.cheader['time_duration'] /
                                p0.cheader['num_samples'] * 10**6))
    sample_format = {1: 'b', 2: 'h'}[ chaninfo['bytes_per_sample'] ]

    segy_header = dict(
        n_traces_per_ensemble = 1,
        n_auxtraces_per_ensemble = 0,
        sample_interval = sample_interval,
        n_trace_samples = p0.cheader['num_samples'],
        sample_format = segy.SAMPLE_FORMATS[sample_format],
        segy_rev = 0x0100,
        fixed_length_trace_flag = 1,
        n_extended_headers = 0,
        measurement_system = 1, # meters
        ensemble_fold = 1, # that's what Chesapeake XTF-To-SEGY is doing
    )

    if to_utm:
        # peek first point coordinates
        lon = p0.sheader['sensor_xcoordinate']
        lat = p0.sheader['sensor_ycoordinate']

        if utm_params.auto:
            # autodetect UTM zone and hemisphere
            zone = int((lon + 180.0) % 360.0 / 6) + 1
            south = lat < 0.0
            sys.stdout.write('UTM parameters: %d%s\n' %
                                (zone, 'S' if south else 'N'))
        else:
            zone = utm_params.zone
            south = utm_params.south

        from pyproj import Proj
        utm = Proj(proj = 'utm', zone = zone, ellps = 'WGS84', south = south)

    def d2s(deg, scale):
        """Convert degrees to (scaled) seconds of arc"""
        return deg * 60 * 60 * scale

    if to_utm:
        units = 1 # length
        scaler = 1
        convertor = utm
    else:
        units = 2 # secs of arc
        scaler = -100
        convertor = lambda lon, lat: (d2s(lon, 100), d2s(lat, 100))

    def traces():
        for i, p in enumerate(packets):

            # make sure we don't have variable trace len or sample interval
            assert p.cheader['num_samples'] == p0.cheader['num_samples']
            assert p.cheader['time_duration'] == p0.cheader['time_duration']

            x, y = convertor(p.sheader['sensor_xcoordinate'],
                             p.sheader['sensor_ycoordinate'])

            trace_header = dict(
                trace_seq_in_line = i + 1,
                trace_seq_in_file = i + 1,

                # not suitable for trace_seq_in_*, counts 1 3 5 7...
                trace_num_in_orig_record = p.sheader['ping_number'],

                trace_id_code = 1, # seismic

                year = p.sheader['year'],
                day_of_year = p.sheader['julian_day'],
                hour = p.sheader['hour'],
                minute = p.sheader['minute'],
                second = p.sheader['second'],

                time_basis_code = 4,
                n_samples = p.cheader['num_samples'],
                sample_interval = sample_interval,
                elevations_scaler = 1,

                coordinate_units = units,
                coordinates_scaler = scaler,
                reciever_coord_x = int(round(x)),
                reciever_coord_y = int(round(y)),

                # Chesapeake XTF-To-SEGY does this, but I think it's wrong
                #source_coord_x = ... p.sheader['ship_xcoordinate'] ... ,
                #source_coord_y = ... p.sheader['ship_ycoordinate'] ... ,

                #ensemble_num = ... # For marks when importing to Geographix
            )
            yield trace_header, p.trace

    text_header = Template("""Converted $filename to SEG-Y
XTF Surveyor v$version, $url
Converted by: $user
Converted at: $datetime
XTF recording program: $program
XTF this file name: $this_filename
XTF note string: $note""").substitute(
    filename = infile,
    version =  version.__version__,
    url = version.url,
    user = getuser(),
    datetime = datetime.now(),
    note = '\n' + re.sub(r'\r+', '\n', header['note_string']),
    this_filename = header['this_file_name'],
    program = '%s v%s' % (header['recording_program_name'],
                          header['recording_program_version']))

    segy.write_SEGY(outfile, segy_header, text_header, traces())

PLOT_NTRACES = 3000

def plot(infile):
    header, chaninfos, packets = read_XTF(infile, 'sonar')
    packets = sorted(packets, key=lambda p: p.channel_number)

    channels = [0] * len(chaninfos)
    for p in packets:
        channels[p.channel_number] += 1

    n_nonempty = len([c for c in channels if c])

    def clicked(*args):
        print 'clicked', args

    #import matplotlib; matplotlib.use('MacOSX')
    from matplotlib import pyplot as P, widgets
    P.suptitle('File: ' + infile)
    P.gcf().canvas.set_window_title("%s - xtf.py" % infile)

    buttons = []

    #first = None
    for i, (channel, packets) in enumerate(groupby(packets,
                                                   lambda p: p.channel_number)):
        traces = list(p.trace for p in islice(packets, PLOT_NTRACES))
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

def test_copy(infile):
    export_XTF(infile, infile+'_test_ch1.xtf', [1])
    export_SEGY(infile, infile+'_test_ch0.segy', [0])

def main(infile):
    header, chaninfos, packets = read_XTF(infile, 'sonar')
    pprint(header.items())
    for packet in packets:
        pprint(packet.pheader)
        pprint(packet.sheader)
        pprint(packet.cheader)
        break

if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit('Error: wrong arguments\n' + __doc__.rstrip())

    main(*sys.argv[1:])
    #plot(*sys.argv[1:])
    #test_copy(*sys.argv[1:])
