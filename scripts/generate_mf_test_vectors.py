"""
Generate matched filter test vectors for VHDL simulation.

Creates two files:
  - rtl/common/mf_input.csv   — input I/Q samples (Q1.15 signed decimal)
  - rtl/common/mf_expected.csv — expected output I/Q from the Python
                                  fixed-point matched filter (signed decimal)

The input is a simulated received signal with chirp echoes in noise,
using the exact same DDS logic as chirp.vhd to generate the chirp
and the same Q1.15 coefficients as mf_coef_pkg.vhd.

Run:
    python scripts/generate_mf_test_vectors.py
"""

import os
import math
import numpy as np

# --- Parameters (must match VHDL generics) ---
SAMPLE_RATE = 200_000
F_START     = 39_000
F_END       = 41_000
NUM_SAMPLES = 64
PHASE_WIDTH = 24
FRAC_BITS   = 15
SCALE       = 2 ** FRAC_BITS
MAX_VAL     = SCALE - 1
MIN_VAL     = -SCALE
LUT_SIZE    = 1024
LUT_QUARTER = 256

# Test scenario
TARGET_DELAYS     = [80, 160]
TARGET_AMPLITUDES = [1.0, 0.7]
NOISE_POWER       = 0.01
TOTAL_LENGTH      = 300
RANDOM_SEED       = 42

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), '..', 'rtl', 'common')


def float_to_q15(x):
    raw = int(round(x * SCALE))
    return max(MIN_VAL, min(MAX_VAL, raw))


def build_sin_table():
    table = []
    for i in range(LUT_SIZE):
        angle = 2.0 * math.pi * i / LUT_SIZE
        table.append(float_to_q15(math.sin(angle)))
    return table


def generate_chirp_q15():
    """Generate chirp samples using the exact same DDS logic as chirp.vhd."""
    sin_table = build_sin_table()

    fcw_start = int(round(F_START * (2 ** PHASE_WIDTH) / SAMPLE_RATE))
    fcw_end   = int(round(F_END   * (2 ** PHASE_WIDTH) / SAMPLE_RATE))
    fcw_step  = (fcw_end - fcw_start) // (NUM_SAMPLES - 1)

    phase_mask = (1 << PHASE_WIDTH) - 1
    lut_shift  = PHASE_WIDTH - 10

    phase = 0
    fcw = fcw_start
    chirp_i = []
    chirp_q = []

    for n in range(NUM_SAMPLES):
        lut_index = (phase >> lut_shift) & (LUT_SIZE - 1)
        cos_index = (lut_index + LUT_QUARTER) % LUT_SIZE
        chirp_i.append(sin_table[cos_index])
        chirp_q.append(sin_table[lut_index])
        phase = (phase + fcw) & phase_mask
        fcw = fcw + fcw_step

    return chirp_i, chirp_q


def simulate_received_q15(chirp_i, chirp_q):
    """Create a received signal with delayed chirp echoes + noise, in Q1.15."""
    np.random.seed(RANDOM_SEED)

    # Start with noise in float, then quantize
    noise_sigma = math.sqrt(NOISE_POWER / 2.0)
    rx_float_i = noise_sigma * np.random.randn(TOTAL_LENGTH)
    rx_float_q = noise_sigma * np.random.randn(TOTAL_LENGTH)

    # Add delayed chirp echoes
    for delay, amp in zip(TARGET_DELAYS, TARGET_AMPLITUDES):
        for n in range(NUM_SAMPLES):
            idx = delay + n
            if idx >= TOTAL_LENGTH:
                break
            rx_float_i[idx] += amp * chirp_i[n] / SCALE
            rx_float_q[idx] += amp * chirp_q[n] / SCALE

    # Quantize to Q1.15
    rx_q15_i = [float_to_q15(x) for x in rx_float_i]
    rx_q15_q = [float_to_q15(x) for x in rx_float_q]

    return rx_q15_i, rx_q15_q


def matched_filter_fixed(rx_i, rx_q, chirp_i, chirp_q):
    """
    Run the matched filter in fixed-point, matching the VHDL implementation.

    Uses the same time-multiplexed algorithm:
      - Shift buffer
      - MAC over all taps with complex multiply
      - Output the accumulator (top 32 bits of 48-bit result)

    Coefficients are the reversed, conjugated chirp (same as mf_coef_pkg.vhd).
    """
    num_taps = len(chirp_i)

    # Build coefficients: reversed, conjugated
    coef_i = list(reversed(chirp_i))
    coef_q = [-q for q in reversed(chirp_q)]

    # Sample buffer (shift register), initialized to zeros
    buf_i = [0] * num_taps
    buf_q = [0] * num_taps

    out_i = []
    out_q = []

    for n in range(len(rx_i)):
        # Shift buffer, new sample at position 0
        for k in range(num_taps - 1, 0, -1):
            buf_i[k] = buf_i[k - 1]
            buf_q[k] = buf_q[k - 1]
        buf_i[0] = rx_i[n]
        buf_q[0] = rx_q[n]

        # MAC: complex multiply-accumulate over all taps
        accum_real = 0
        accum_imag = 0
        for k in range(num_taps):
            # (a + jb)(c + jd) = (ac - bd) + j(ad + bc)
            accum_real += buf_i[k] * coef_i[k] - buf_q[k] * coef_q[k]
            accum_imag += buf_i[k] * coef_q[k] + buf_q[k] * coef_i[k]

        # Truncate to top 32 bits of 48-bit accumulator
        # The accumulator is a signed 48-bit value.
        # Taking bits 47 downto 16 is equivalent to right-shifting by 16.
        accum_real_trunc = accum_real >> 16
        accum_imag_trunc = accum_imag >> 16

        # Clamp to 32-bit signed range
        max32 = (1 << 31) - 1
        min32 = -(1 << 31)
        accum_real_trunc = max(min32, min(max32, accum_real_trunc))
        accum_imag_trunc = max(min32, min(max32, accum_imag_trunc))

        out_i.append(accum_real_trunc)
        out_q.append(accum_imag_trunc)

    return out_i, out_q


def main():
    print('Generating chirp (Q1.15, matching chirp.vhd)...')
    chirp_i, chirp_q = generate_chirp_q15()

    print(f'Simulating received signal ({TOTAL_LENGTH} samples, '
          f'{len(TARGET_DELAYS)} targets)...')
    rx_i, rx_q = simulate_received_q15(chirp_i, chirp_q)

    print('Running fixed-point matched filter (Python reference)...')
    mf_out_i, mf_out_q = matched_filter_fixed(rx_i, rx_q, chirp_i, chirp_q)

    # Write input vectors
    input_path = os.path.join(OUTPUT_DIR, 'mf_input.csv')
    with open(input_path, 'w') as f:
        for i_val, q_val in zip(rx_i, rx_q):
            f.write(f'{i_val},{q_val}\n')
    print(f'Wrote {len(rx_i)} input samples to {input_path}')

    # Write expected output vectors
    expected_path = os.path.join(OUTPUT_DIR, 'mf_expected.csv')
    with open(expected_path, 'w') as f:
        for i_val, q_val in zip(mf_out_i, mf_out_q):
            f.write(f'{i_val},{q_val}\n')
    print(f'Wrote {len(mf_out_i)} expected output samples to {expected_path}')

    # Quick summary
    mf_mag = [math.sqrt(i**2 + q**2) for i, q in zip(mf_out_i, mf_out_q)]
    peak_idx = mf_mag.index(max(mf_mag))
    print(f'\nExpected peak at index {peak_idx} '
          f'(target delays were {TARGET_DELAYS})')
    print(f'Peak magnitude: {max(mf_mag):.0f}')


if __name__ == '__main__':
    main()
