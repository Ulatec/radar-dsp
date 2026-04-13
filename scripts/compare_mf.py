"""
Compare VHDL matched filter output against Python fixed-point reference.

Reads mf_output.csv (from GHDL simulation) and mf_expected.csv (from
generate_mf_test_vectors.py) and compares sample by sample.

Run:
    python scripts/compare_mf.py rtl/common/mf_output.csv rtl/common/mf_expected.csv
"""

import sys
import os
import numpy as np


def read_csv(path):
    i_vals = []
    q_vals = []
    with open(path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split(',')
            i_vals.append(int(parts[0]))
            q_vals.append(int(parts[1]))
    return np.array(i_vals), np.array(q_vals)


def main():
    if len(sys.argv) >= 3:
        vhdl_path = sys.argv[1]
        ref_path = sys.argv[2]
    else:
        candidates_vhdl = ['mf_output.csv', 'rtl/common/mf_output.csv']
        candidates_ref = ['mf_expected.csv', 'rtl/common/mf_expected.csv']
        vhdl_path = next((c for c in candidates_vhdl if os.path.exists(c)), None)
        ref_path = next((c for c in candidates_ref if os.path.exists(c)), None)
        if not vhdl_path or not ref_path:
            print('Error: could not find mf_output.csv and/or mf_expected.csv')
            sys.exit(1)

    vhdl_i, vhdl_q = read_csv(vhdl_path)
    ref_i, ref_q = read_csv(ref_path)

    print(f'VHDL samples:     {len(vhdl_i)}')
    print(f'Expected samples: {len(ref_i)}')

    min_len = min(len(vhdl_i), len(ref_i))
    if len(vhdl_i) != len(ref_i):
        print(f'WARNING: sample count mismatch! Comparing first {min_len}.')
    print()

    mismatches = 0
    max_diff_i = 0
    max_diff_q = 0
    for n in range(min_len):
        diff_i = abs(vhdl_i[n] - ref_i[n])
        diff_q = abs(vhdl_q[n] - ref_q[n])
        max_diff_i = max(max_diff_i, diff_i)
        max_diff_q = max(max_diff_q, diff_q)
        if diff_i != 0 or diff_q != 0:
            mismatches += 1
            if mismatches <= 10:
                print(f'  MISMATCH at sample {n}:')
                print(f'    VHDL:     I={vhdl_i[n]:12d}  Q={vhdl_q[n]:12d}')
                print(f'    Expected: I={ref_i[n]:12d}  Q={ref_q[n]:12d}')
                print(f'    Diff:     I={vhdl_i[n]-ref_i[n]:12d}  Q={vhdl_q[n]-ref_q[n]:12d}')

    if mismatches > 10:
        print(f'  ... and {mismatches - 10} more mismatches')

    print()
    if mismatches == 0:
        print('PASS: All samples match bit-exact.')
    else:
        print(f'RESULT: {mismatches} mismatches out of {min_len} samples.')
        print(f'Max |diff| I: {max_diff_i}')
        print(f'Max |diff| Q: {max_diff_q}')

    # Print first 8 samples for visual inspection
    print()
    print('First 8 samples:')
    print(f'  {"n":>3}  {"VHDL_I":>12}  {"Ref_I":>12}  {"VHDL_Q":>12}  {"Ref_Q":>12}')
    for n in range(min(8, min_len)):
        print(f'  {n:3d}  {vhdl_i[n]:12d}  {ref_i[n]:12d}  {vhdl_q[n]:12d}  {ref_q[n]:12d}')

    # Show where the peak is
    vhdl_mag = vhdl_i[:min_len].astype(np.int64)**2 + vhdl_q[:min_len].astype(np.int64)**2
    ref_mag = ref_i[:min_len].astype(np.int64)**2 + ref_q[:min_len].astype(np.int64)**2
    print()
    print(f'VHDL peak at index:     {np.argmax(vhdl_mag)}')
    print(f'Expected peak at index: {np.argmax(ref_mag)}')


if __name__ == '__main__':
    main()
