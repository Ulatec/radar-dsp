"""
Compare VHDL CFAR output against the Python reference.

Reads cfar_output.csv (from GHDL simulation) and cfar_expected.csv
(from generate_cfar_test_vectors.py) and compares line by line.

Run:
    python scripts/compare_cfar.py rtl/common/cfar_output.csv rtl/common/cfar_expected.csv
"""

import sys
import os


def read_flags(path):
    flags = []
    with open(path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            flags.append(int(line))
    return flags


def main():
    if len(sys.argv) >= 3:
        vhdl_path = sys.argv[1]
        ref_path = sys.argv[2]
    else:
        candidates_vhdl = ['cfar_output.csv', 'rtl/common/cfar_output.csv']
        candidates_ref = ['cfar_expected.csv', 'rtl/common/cfar_expected.csv']
        vhdl_path = next((c for c in candidates_vhdl if os.path.exists(c)), None)
        ref_path = next((c for c in candidates_ref if os.path.exists(c)), None)
        if not vhdl_path or not ref_path:
            print('Error: could not find cfar_output.csv and/or cfar_expected.csv')
            sys.exit(1)

    vhdl_flags = read_flags(vhdl_path)
    ref_flags = read_flags(ref_path)

    print(f'VHDL samples:     {len(vhdl_flags)}')
    print(f'Expected samples: {len(ref_flags)}')

    min_len = min(len(vhdl_flags), len(ref_flags))
    if len(vhdl_flags) != len(ref_flags):
        print(f'WARNING: sample count mismatch! Comparing first {min_len}.')
    print()

    mismatches = 0
    for n in range(min_len):
        if vhdl_flags[n] != ref_flags[n]:
            mismatches += 1
            if mismatches <= 20:
                print(f'  MISMATCH at sample {n}: VHDL={vhdl_flags[n]} '
                      f'Expected={ref_flags[n]}')
    if mismatches > 20:
        print(f'  ... and {mismatches - 20} more mismatches')

    print()
    vhdl_detects = sum(vhdl_flags[:min_len])
    ref_detects = sum(ref_flags[:min_len])
    print(f'VHDL detections:     {vhdl_detects}')
    print(f'Expected detections: {ref_detects}')

    if mismatches == 0:
        print()
        print('PASS: All flags match bit-exact.')
    else:
        print()
        print(f'FAIL: {mismatches} mismatches out of {min_len} samples.')


if __name__ == '__main__':
    main()
