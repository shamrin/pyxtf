"""segy.py - read and write SEG-Y files

From command line:
    python segy.py <path-to-segy-file>
"""

from collections import OrderedDict
from pprint import pprint

import numpy as np

from sacker import Sacker

# SEG-Y spec: http://www.tritonimaginginc.com/site/content/public/downloads/FileFormatInfo/seg_y_rev1.pdf

SAMPLE_FORMATS = {
    'f': 5, # 4-byte, IEEE floating-point
    'i': 2, # 4-byte, two's complement integer
    'h': 3, # 2-byte, two's complement integer
    'b': 8, # 1-byte, two's complement integer
}

SEGY_HEADER = Sacker('>', '''
    I job_id                   # Job identification number
    i line_num                 # Line number
    i reel_num                 # Reel number
    h n_traces_per_ensemble    # Number of data traces per ensemble
    h n_auxtraces_per_ensemble # Number of auxilary traces per ensemble
    h sample_interval          # Sample interval (us)
    h orig_sample_interval     # Sample interval of original field recording
    h n_trace_samples          # Number of samples per data trace
    h orig_n_trace_samples     # Number of samples per data trace for original
                               #    field recording
    h sample_format            # Data sample format code
    h ensemble_fold            # Expected number of data traces per
                               #    trace ensemble (e.g. the CMP fold)
    h trace_sorting_code
    h vertical_sum_code
    h sweep_freq_at_start      # (Hz)
    h sweep_freq_at_end        # (Hz)
    h sweep_length             # (ms)
    h sweep_type_code
    h sweep_channel_trace_number
    h start_taper_length       # (ms)
    h end_taper_length         # (ms)
    h taper_type
    h correlated_traces
    h binary_gain_recovered
    h amplitude_recovery_method
    h measurement_system       # (1: meters, 2: feet)
    h impulse_signal_polarity
    h vibratory_polarity_code
    240x
    h segy_rev
    h fixed_length_trace_flag
    h n_extended_headers
    94x''', length = 400)

TRACE_HEADER = Sacker('>', '''
    i trace_seq_in_line         # Trace sequence number within line - Numbers
                                # continue to increase if the same line
                                # continues across multiple SEG Y files
    i trace_seq_in_file         # Trace sequence number within SEG Y file.
                                # Each file starts with trace sequence one.
    i orig_field_record_num
    i trace_num_in_orig_record
    i energy_source_point_number
    i ensemble_num                    # i.e. CDP, CMP, CRP, etc
    i trace_num_in_ensemble           # Each ensemble starts with trace 1
    h trace_id_code
    h n_of_vertically_summed_traces   # yielding this trace
    h n_of_horizontally_summed_traces # yielding this trace
    h data_use                        # (1 - production, 2 - test)
    i source_reciever_dist
    i reciever_elevation
    i surface_elevation_at_source
    i source_depth_below_surface      # (a positive number)
    i datum_elevation_at_reciever
    i datum_elevation_at_source
    i water_depth_at_source
    i water_depth_at_reciever
    h elevations_scaler  # (1, 10, 100, 1000, 10000)
    h coordinates_scaler # (1, 10, 100, 1000, 10000)
    i source_coord_x
    i source_coord_y
    i reciever_coord_x
    i reciever_coord_y
    h coordinate_units   # (1: length, 2: secs of arc,  3: decimal degrees,
                         #  4: degrees, minutes, seconds)
    h weathering_velocity           # (m/s or ft/s)
    h subweathering_velocity        # (m/s or ft/s)
    h uphole_time_at_source         # (ms)
    h uphole_time_at_reciever       # (ms)
    h static_correction_at_source   # (ms)
    h static_correction_at_reciever # (ms)
    h total_static                  # (ms)
    h lag_time_A                    # (ms)
    h lag_time_B                    # (ms)
    h delay_recording_time          # (ms)
    h mute_time_start               # (ms)
    h mute_time_end                 # (ms)
    h n_samples                     # Number of samples in this trace
    h sample_interval               # (us)
    h field_instruments_gain_type   # (1: fixed, 2: binary, 3: float)
    h instrument_gain_const         # (dB)
    h instrument_early_gain         # (dB)
    h correlated                    # (1: no, 2: yes)

    h sweep_freq_at_start # (Hz)
    h sweep_freq_at_end   # (Hz)
    h sweep_length        # (ms)
    h sweep_type_code
    h start_taper_length  # (ms)
    h end_taper_length    # (ms)
    h taper_type

    h alias_filter_freq  # (Hz)
    h alias_filter_slope # (dB/octave)
    h notch_filter_freq  # (Hz)
    h notch_filter_slope # (dB/octave)

    h low_cut_filter_freq   # (Hz)
    h high_cut_filter_freq  # (Hz)
    h low_cut_filter_slope  # (dB/octave)
    h high_cut_filter_slope # (dB/octave)

    h year
    h day_of_year
    h hour
    h minute
    h second
    h time_basis_code # (1: local, 2: GMT, 3: Other, 4: UTC)

    h trace_weighting_factor
    h geophone_group_num_of_roll_switch
    h geophone_group_num_of_first_trace
    h geophone_group_num_of_last_trace
    h gap_size    # (total number of groups dropped)
    h over_travel # associated with taper (1: down, 2: up)
    60x''', length = 240)

TEXT_LEN = 3200

def decode_text(s):
    text = s.decode('ibm037')
    return '\n'.join(text[i:i+80] for i in range(0, len(text), 80))

def encode_text(s):
    t = ''.join(line.ljust(80,' ')
                for line in s.split('\n')).ljust(TEXT_LEN,' ')
    return t.encode('ibm037')

def write_SEGY(outfile, file_header, text, traces):
    with open(outfile, 'wb') as out:
        out.write(encode_text(text))
        out.write(SEGY_HEADER.wrap(file_header))
        for header, data in traces:
            out.write(TRACE_HEADER.wrap(header))
            out.write(np.getbuffer(data.byteswap()))

def read_SEGY(infile):
    file_data = memoryview(open(infile, 'rb').read())
    print decode_text(file_data[:TEXT_LEN].tobytes())
    data = file_data[TEXT_LEN:]
    header_len, header = SEGY_HEADER.unwrap(data, data_factory = OrderedDict)
    pprint([(k, v) for k, v in header.items() if v != 0])

    i = 0
    data = data[header_len:]
    while data:
        trace_len, trace = TRACE_HEADER.unwrap(data, data_factory = OrderedDict)
        print 'TRACE', i, '[%d]' % trace['trace_num_in_orig_record'],
        pprint([(k, v) for k, v in trace.items() if v != 0])
        print np.frombuffer(data[trace_len:trace_len + trace['n_samples']*2].tobytes(), np.int16).byteswap()
        data = data[trace_len + trace['n_samples'] * 2:]
        i += 1
        if i > 10:
            break


def main(infile):
    read_SEGY(infile)

if __name__ == '__main__':
    import sys
    if len(sys.argv) != 2:
        sys.exit('Error: wrong arguments\n' + __doc__.rstrip())
    main(*sys.argv[1:])
