"""
Capture floating-point reference data for the full pulse compression chain.

Saves all intermediate results as .npy files and generates a reference plot.
These will be compared against the fixed-point chain later.
"""

import os
import numpy as np
import matplotlib.pyplot as plt
from chirp import generate_chirp, DEFAULT_SAMPLE_RATE, DEFAULT_NUM_SAMPLES
from chirp import DEFAULT_F_START, DEFAULT_F_END
from matched_filter import matched_filter
from cfar import ca_cfar, DEFAULT_NUM_TRAIN, DEFAULT_NUM_GUARD, DEFAULT_PFA
from end_to_end import simulate_received_signal

# Fixed seed for reproducibility — same noise every run
np.random.seed(42)

# --- Parameters ---
target_delays = [300, 900, 1500]
target_amplitudes = [1.0, 0.8, 0.5]
noise_power = 0.01
total_length = 2000

# --- Run the chain ---
chirp = generate_chirp(DEFAULT_F_START, DEFAULT_F_END,
                       DEFAULT_NUM_SAMPLES, DEFAULT_SAMPLE_RATE)

received = simulate_received_signal(chirp, target_delays, target_amplitudes,
                                    noise_power, total_length)

mf_output = matched_filter(received, chirp)

magnitudes = np.abs(mf_output) ** 2

detections, thresholds = ca_cfar(magnitudes, DEFAULT_NUM_TRAIN,
                                  DEFAULT_NUM_GUARD, DEFAULT_PFA)

# --- Save arrays ---
vectors_dir = os.path.join(os.path.dirname(__file__), '..', 'sim', 'vectors')

np.save(os.path.join(vectors_dir, 'float_chirp.npy'), chirp)
np.save(os.path.join(vectors_dir, 'float_received.npy'), received)
np.save(os.path.join(vectors_dir, 'float_mf_output.npy'), mf_output)
np.save(os.path.join(vectors_dir, 'float_magnitudes.npy'), magnitudes)
np.save(os.path.join(vectors_dir, 'float_thresholds.npy'), thresholds)
np.save(os.path.join(vectors_dir, 'float_detections.npy'), detections)

print(f'Saved {6} arrays to {os.path.abspath(vectors_dir)}')

# --- Save parameters for reproducibility ---
params = {
    'sample_rate': DEFAULT_SAMPLE_RATE,
    'num_samples': DEFAULT_NUM_SAMPLES,
    'f_start': DEFAULT_F_START,
    'f_end': DEFAULT_F_END,
    'target_delays': target_delays,
    'target_amplitudes': target_amplitudes,
    'noise_power': noise_power,
    'total_length': total_length,
    'num_train': DEFAULT_NUM_TRAIN,
    'num_guard': DEFAULT_NUM_GUARD,
    'pfa': DEFAULT_PFA,
    'random_seed': 42,
}
np.save(os.path.join(vectors_dir, 'float_params.npy'), params)

# --- Print summary ---
det_indices = np.where(detections)[0]
print(f'Target delays:     {target_delays}')
print(f'Detection indices: {det_indices}')
print(f'MF output max:     {np.max(magnitudes):.2f}')
print(f'MF output mean:    {np.mean(magnitudes):.4f}')

# --- Generate reference plot ---
docs_dir = os.path.join(os.path.dirname(__file__), '..', 'docs')
time_vec = np.arange(total_length) / DEFAULT_SAMPLE_RATE * 1000  # ms

fig, axes = plt.subplots(4, 1, figsize=(12, 10))

# 1. Raw received signal
axes[0].plot(time_vec, np.real(received), linewidth=0.5)
axes[0].set_title('Received Signal (Real Part)')
axes[0].set_xlabel('Time (ms)')
axes[0].set_ylabel('Amplitude')
axes[0].grid(True)

# 2. Matched filter output magnitude
axes[1].plot(time_vec, np.abs(mf_output), linewidth=0.8)
axes[1].set_title('Matched Filter Output |MF|')
axes[1].set_xlabel('Time (ms)')
axes[1].set_ylabel('Magnitude')
axes[1].grid(True)

# 3. Magnitude squared with CFAR threshold
axes[2].plot(time_vec, magnitudes, linewidth=0.8, label='|MF|²')
axes[2].plot(time_vec, thresholds, 'r--', linewidth=0.8, label='CFAR Threshold')
axes[2].set_title('Magnitude² + Adaptive Threshold')
axes[2].set_xlabel('Time (ms)')
axes[2].set_ylabel('Power')
axes[2].legend()
axes[2].grid(True)

# 4. Detections
axes[3].plot(time_vec, magnitudes, linewidth=0.5, alpha=0.5, label='|MF|²')
axes[3].plot(time_vec[detections], magnitudes[detections], 'ro',
             markersize=3, label='Detection')
for d in target_delays:
    axes[3].axvline(x=d / DEFAULT_SAMPLE_RATE * 1000, color='g',
                    linestyle=':', alpha=0.5, label=f'Target @ {d}' if d == target_delays[0] else '')
axes[3].set_title('CFAR Detections (Float Reference)')
axes[3].set_xlabel('Time (ms)')
axes[3].set_ylabel('Power')
axes[3].legend()
axes[3].grid(True)

plt.tight_layout()

plot_path = os.path.join(docs_dir, 'float_reference.png')
plt.savefig(plot_path, dpi=150)
print(f'Saved reference plot to {os.path.abspath(plot_path)}')
plt.show()
