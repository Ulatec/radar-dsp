"""
Float vs Fixed-Point (Q1.15) Comparison.

Runs the full pulse compression chain in both floating-point and Q1.15
fixed-point, and generates a side-by-side comparison plot. Demonstrates
that 16-bit fixed-point is sufficient to preserve detection performance.
"""

import os
import numpy as np
import matplotlib.pyplot as plt
from chirp import generate_chirp, DEFAULT_SAMPLE_RATE, DEFAULT_NUM_SAMPLES
from chirp import DEFAULT_F_START, DEFAULT_F_END
from matched_filter import matched_filter, matched_filter_fixed
from cfar import ca_cfar, DEFAULT_NUM_TRAIN, DEFAULT_NUM_GUARD, DEFAULT_PFA
from end_to_end import simulate_received_signal

# Same seed/parameters as capture_float_reference.py
np.random.seed(42)
target_delays = [300, 900, 1500]
target_amplitudes = [1.0, 0.8, 0.5]
noise_power = 0.01
total_length = 2000

# --- Generate chirp and received signal ---
chirp = generate_chirp(DEFAULT_F_START, DEFAULT_F_END,
                       DEFAULT_NUM_SAMPLES, DEFAULT_SAMPLE_RATE)
received = simulate_received_signal(chirp, target_delays, target_amplitudes,
                                    noise_power, total_length)

# --- Run both matched filters ---
print('Running float matched filter...')
mf_float = matched_filter(received, chirp)

print('Running fixed-point matched filter (this may take a moment)...')
mf_fixed = matched_filter_fixed(received, chirp)

# --- Magnitudes and CFAR on both ---
mag_float = np.abs(mf_float) ** 2
mag_fixed = np.abs(mf_fixed) ** 2

det_float, thr_float = ca_cfar(mag_float, DEFAULT_NUM_TRAIN,
                                DEFAULT_NUM_GUARD, DEFAULT_PFA)
det_fixed, thr_fixed = ca_cfar(mag_fixed, DEFAULT_NUM_TRAIN,
                                DEFAULT_NUM_GUARD, DEFAULT_PFA)

# --- Summary stats ---
mag_float_amp = np.abs(mf_float)
mag_fixed_amp = np.abs(mf_fixed)

print()
print(f'Float  peak: {np.max(mag_float_amp):.4f} at index {np.argmax(mag_float_amp)}')
print(f'Fixed  peak: {np.max(mag_fixed_amp):.4f} at index {np.argmax(mag_fixed_amp)}')
print(f'Peak relative error: {abs(np.max(mag_float_amp) - np.max(mag_fixed_amp)) / np.max(mag_float_amp) * 100:.4f}%')
print(f'Float detections: {np.sum(det_float)} cells')
print(f'Fixed detections: {np.sum(det_fixed)} cells')

# --- Plot comparison ---
time_vec = np.arange(total_length) / DEFAULT_SAMPLE_RATE * 1000  # ms

fig, axes = plt.subplots(4, 1, figsize=(12, 11))

# 1. Matched filter output (magnitude) overlay
axes[0].plot(time_vec, mag_float_amp, 'b-', linewidth=0.8,
             label='Float', alpha=0.8)
axes[0].plot(time_vec, mag_fixed_amp, 'r--', linewidth=0.8,
             label='Q1.15 Fixed', alpha=0.8)
axes[0].set_title('Matched Filter Output Magnitude — Float vs Fixed')
axes[0].set_xlabel('Time (ms)')
axes[0].set_ylabel('|MF|')
axes[0].legend()
axes[0].grid(True)

# 2. Quantization error (difference between float and fixed)
error = mag_float_amp - mag_fixed_amp
axes[1].plot(time_vec, error, 'k-', linewidth=0.5)
axes[1].set_title(f'Quantization Error (float − fixed)   '
                  f'max |error| = {np.max(np.abs(error)):.4f}')
axes[1].set_xlabel('Time (ms)')
axes[1].set_ylabel('Error')
axes[1].grid(True)

# 3. Float chain detections
axes[2].plot(time_vec, mag_float, 'b-', linewidth=0.5, alpha=0.5,
             label='|MF|² (float)')
axes[2].plot(time_vec, thr_float, 'b--', linewidth=0.8, label='Threshold (float)')
axes[2].plot(time_vec[det_float], mag_float[det_float], 'bo',
             markersize=3, label='Detection (float)')
for d in target_delays:
    axes[2].axvline(x=d / DEFAULT_SAMPLE_RATE * 1000, color='g',
                    linestyle=':', alpha=0.4)
axes[2].set_title('Float Chain — CFAR Detections')
axes[2].set_xlabel('Time (ms)')
axes[2].set_ylabel('Power')
axes[2].legend(loc='upper right')
axes[2].grid(True)

# 4. Fixed-point chain detections
axes[3].plot(time_vec, mag_fixed, 'r-', linewidth=0.5, alpha=0.5,
             label='|MF|² (fixed)')
axes[3].plot(time_vec, thr_fixed, 'r--', linewidth=0.8, label='Threshold (fixed)')
axes[3].plot(time_vec[det_fixed], mag_fixed[det_fixed], 'ro',
             markersize=3, label='Detection (fixed)')
for d in target_delays:
    axes[3].axvline(x=d / DEFAULT_SAMPLE_RATE * 1000, color='g',
                    linestyle=':', alpha=0.4)
axes[3].set_title('Q1.15 Fixed-Point Chain — CFAR Detections')
axes[3].set_xlabel('Time (ms)')
axes[3].set_ylabel('Power')
axes[3].legend(loc='upper right')
axes[3].grid(True)

plt.tight_layout()

docs_dir = os.path.join(os.path.dirname(__file__), '..', 'docs')
plot_path = os.path.join(docs_dir, 'float_vs_fixed.png')
plt.savefig(plot_path, dpi=150)
print(f'Saved comparison plot to {os.path.abspath(plot_path)}')
plt.show()
