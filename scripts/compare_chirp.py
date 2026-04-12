"""
Compare VHDL chirp output against Python LUT-based reference.

Reads chirp_output.csv (from GHDL simulation) and compares each I/Q
sample against what the Python LUT would produce with the same parameters.

Run from the directory containing chirp_output.csv:
    python ../../scripts/compare_chirp.py

Or specify the CSV path:
    python scripts/compare_chirp.py rtl/common/chirp_output.csv
"""

import sys
import os
import math
import numpy as np

# --- Parameters (must match chirp.vhd generics) ---
SAMPLE_RATE = 200_000
F_START     = 39_000
F_END       = 41_000
NUM_SAMPLES = 64
PHASE_WIDTH = 24
FRAC_BITS   = 15
SCALE       = 2 ** FRAC_BITS
LUT_SIZE    = 1024
LUT_QUARTER = 256


def float_to_q15(x):
    raw = int(round(x * SCALE))
    return max(-SCALE, min(SCALE - 1, raw))


def build_sin_table():
    table = []
    for i in range(LUT_SIZE):
        angle = 2.0 * math.pi * i / LUT_SIZE
        table.append(float_to_q15(math.sin(angle)))
    return table


def generate_reference():
    """Reproduce the exact DDS behavior from the VHDL: phase accumulator +
    FCW ramp + LUT lookup."""
    sin_table = build_sin_table()

    fcw_start = int(round(F_START * (2 ** PHASE_WIDTH) / SAMPLE_RATE))
    fcw_end   = int(round(F_END   * (2 ** PHASE_WIDTH) / SAMPLE_RATE))
    fcw_step  = (fcw_end - fcw_start) // (NUM_SAMPLES - 1)

    phase_mask = (1 << PHASE_WIDTH) - 1
    lut_shift  = PHASE_WIDTH - 10  # top 10 bits for LUT index

    phase = 0
    fcw = fcw_start
    i_ref = []
    q_ref = []

    for n in range(NUM_SAMPLES):
        lut_index = (phase >> lut_shift) & (LUT_SIZE - 1)
        cos_index = (lut_index + LUT_QUARTER) % LUT_SIZE
        i_ref.append(sin_table[cos_index])
        q_ref.append(sin_table[lut_index])
        phase = (phase + fcw) & phase_mask
        fcw = fcw + fcw_step

    return np.array(i_ref), np.array(q_ref)


def main():
    # Find the CSV file
    if len(sys.argv) > 1:
        csv_path = sys.argv[1]
    else:
        candidates = [
            'chirp_output.csv',
            'rtl/common/chirp_output.csv',
        ]
        csv_path = None
        for c in candidates:
            if os.path.exists(c):
                csv_path = c
                break
        if csv_path is None:
            print('Error: chirp_output.csv not found. Pass the path as an argument.')
            sys.exit(1)

    # Read VHDL output
    vhdl_i = []
    vhdl_q = []
    with open(csv_path, 'r') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            parts = line.split(',')
            vhdl_i.append(int(parts[0]))
            vhdl_q.append(int(parts[1]))

    vhdl_i = np.array(vhdl_i)
    vhdl_q = np.array(vhdl_q)

    # Generate Python reference (LUT-based, matching VHDL exactly)
    ref_i, ref_q = generate_reference()

    print(f'VHDL samples:   {len(vhdl_i)}')
    print(f'Python samples: {len(ref_i)}')
    print()

    # Compare
    mismatches = 0
    for n in range(min(len(vhdl_i), len(ref_i))):
        i_match = vhdl_i[n] == ref_i[n]
        q_match = vhdl_q[n] == ref_q[n]
        if not i_match or not q_match:
            mismatches += 1
            print(f'  MISMATCH at sample {n}:')
            print(f'    VHDL:   I={vhdl_i[n]:6d}  Q={vhdl_q[n]:6d}')
            print(f'    Python: I={ref_i[n]:6d}  Q={ref_q[n]:6d}')
            print(f'    Diff:   I={vhdl_i[n]-ref_i[n]:6d}  Q={vhdl_q[n]-ref_q[n]:6d}')

    if mismatches == 0:
        print('PASS: All samples match bit-exact.')
    else:
        print(f'\nFAIL: {mismatches} mismatches out of {min(len(vhdl_i), len(ref_i))} samples.')

    # Print first few samples for visual inspection
    print()
    print('First 8 samples:')
    print(f'  {"n":>3}  {"VHDL_I":>8}  {"Ref_I":>8}  {"VHDL_Q":>8}  {"Ref_Q":>8}')
    for n in range(min(8, len(vhdl_i))):
        print(f'  {n:3d}  {vhdl_i[n]:8d}  {ref_i[n]:8d}  {vhdl_q[n]:8d}  {ref_q[n]:8d}')


if __name__ == '__main__':
    main()
