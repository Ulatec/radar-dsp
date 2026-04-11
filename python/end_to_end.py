"""
End-to-End Pulse Compression Simulation.

Full chain: generate chirp -> simulate received echo -> matched filter -> CFAR.
Verifies that the complete pipeline detects targets at the correct delays.
"""

import numpy as np
import matplotlib.pyplot as plt
from chirp import generate_chirp, DEFAULT_SAMPLE_RATE, DEFAULT_NUM_SAMPLES
from chirp import DEFAULT_F_START, DEFAULT_F_END
from matched_filter import matched_filter
from cfar import ca_cfar, DEFAULT_NUM_TRAIN, DEFAULT_NUM_GUARD, DEFAULT_PFA


def simulate_received_signal(chirp, delays, amplitudes, noise_power, total_length):
    """
    Construct a fake received signal: delayed copies of the chirp in noise.

    Args:
        chirp:        Complex numpy array — the transmitted chirp waveform
        delays:       List of integer sample delays (one per simulated target)
        amplitudes:   List of floats — echo amplitude for each target
        noise_power:  Float — power of additive white Gaussian noise
        total_length: Integer — total number of samples in the received signal

    Returns:
        Complex numpy array of the simulated received signal
    """
    signal = np.zeros(total_length, dtype=np.complex128)
    for delay, amp in zip(delays, amplitudes):
        if delay < total_length:
            signal[delay:delay+len(chirp)] += amp * chirp[:total_length-delay]
    noise = np.sqrt(noise_power/2) * (np.random.randn(total_length)
                                        + 1j * np.random.randn(total_length))   
    return signal + noise



def run_end_to_end():
    """
    Run the full pulse compression chain and plot results.

    1. Generate transmitted chirp
    2. Simulate received signal with known target delays
    3. Run matched filter
    4. Run CFAR detection
    5. Plot: input, matched filter output, detections
    6. Verify detections match expected target locations
    """
    # 1. Generate chirp
    chirp = generate_chirp(DEFAULT_F_START, DEFAULT_F_END,
                           DEFAULT_NUM_SAMPLES, DEFAULT_SAMPLE_RATE)
    
    # 2. Simulate received signal with targets at known delays
    target_delays = [300, 900, 1500]  # Sample indices where targets are located
    target_amplitudes = [1.0, 0.8, 0.5]  # Echo amplitudes
    noise_power = 0.01
    total_length = 2000
    received_signal = simulate_received_signal(chirp, target_delays,
                                              target_amplitudes,
                                              noise_power, total_length)
    
    # 3. Run matched filter
    mf_output = matched_filter(received_signal, chirp)
    
    # 4. Run CFAR detection
    magnitudes = np.abs(mf_output)**2
    detections, thresholds = ca_cfar(magnitudes, DEFAULT_NUM_TRAIN,
                                     DEFAULT_NUM_GUARD, DEFAULT_PFA)
    
    # 5. Plot results (omitted for brevity — implement as needed)
    time_vector = np.arange(len(magnitudes)) / DEFAULT_SAMPLE_RATE

    plt.figure(figsize=(14, 10))

    # Plot 1: Magnitude Signal
    plt.subplot(3, 1, 1)
    plt.plot(time_vector, magnitudes, label='Magnitude $|R|^2$')
    plt.title('Raw Magnitude Signal')
    plt.xlabel('Time (s)')
    plt.ylabel('Magnitude')
    plt.grid(True)
    plt.legend()

    # Plot 2: Adaptive Threshold
    plt.subplot(3, 1, 2)
    plt.plot(time_vector, thresholds, label='Adaptive Threshold $\\alpha \\cdot \\text{AvgTrain}$', color='red')
    plt.title('Adaptive Threshold')
    plt.xlabel('Time (s)')
    plt.ylabel('Threshold Value')
    plt.grid(True)
    plt.legend()

    # Plot 3: Detection Results
    plt.subplot(3, 1, 3)
    # Plot the signal again for context
    plt.plot(time_vector, magnitudes, label='Magnitude $|R|^2$', alpha=0.5)
    # Plot the detection flags (True=Detection)
    plt.plot(time_vector[detections], magnitudes[detections], 'ro', markersize=5, label='Detection')
    plt.plot(time_vector, thresholds, 'r--', label='Threshold')
    plt.title('Detection Results')
    plt.xlabel('Time (s)')
    plt.ylabel('Magnitude')
    plt.grid(True)
    plt.legend()

    plt.tight_layout()
    plt.show()
    # 6. Verify detections match expected target locations (print results)
    print("Expected target delays:", target_delays)
    print("Detected target indices:", np.where(detections)[0])


if __name__ == "__main__":
    run_end_to_end()
