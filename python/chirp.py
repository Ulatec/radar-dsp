"""
Chirp Generator — LFM (Linear Frequency Modulation) waveform generation.

Generates complex baseband chirp signals for pulse compression radar.
"""

import numpy as np
import matplotlib.pyplot as plt

# Default parameters
DEFAULT_SAMPLE_RATE = 200_000      # Hz
DEFAULT_NUM_SAMPLES = 64
DEFAULT_F_START = 39_000           # Hz
DEFAULT_F_END = 41_000             # Hz


def generate_chirp(f_start, f_end, num_samples, sample_rate):
    
    """
    Generate a complex baseband LFM chirp signal.

    Args:
        f_start:     Start frequency of the sweep (Hz)
        f_end:       End frequency of the sweep (Hz)
        num_samples: Number of samples in the chirp
        sample_rate: Sample rate (Hz)

    Returns:
        Complex numpy array of shape (num_samples,) containing I + jQ samples.
    """
    t = np.arange(num_samples) / sample_rate
    
    # Chirp frequency sweep: f(t) = f_start + (f_end - f_start) * t / T
    # where T is the total time duration (num_samples / sample_rate)
    T = num_samples / sample_rate
    f_t = f_start + (f_end - f_start) * t / T
    
    # Phase accumulation: phi(t) = 2 * pi * integral(f(t) dt)
    # The integral of f(t) is f_start*t + 0.5 * (f_end - f_start)/T * t^2
    phase = 2 * np.pi * (f_start * t + 0.5 * (f_end - f_start) / T * t**2)
    
    # Complex signal: s(t) = exp(j * phase)
    chirp_signal = np.exp(1j * phase)
    return chirp_signal


def plot_chirp(chirp_signal, sample_rate):
    """
    Plot the chirp: real part, imaginary part, and spectrogram.

    Use this to visually verify that the instantaneous frequency
    sweeps linearly from f_start to f_end.

    Args:
        chirp_signal: Complex numpy array from generate_chirp()
        sample_rate:  Sample rate (Hz)
    """
    plt.figure()
    plt.subplot(3, 1, 1)
    plt.plot(chirp_signal.real)
    plt.title("Real Part")
    plt.xlabel("Sample")
    plt.ylabel("Amplitude")

    plt.subplot(3, 1, 2)
    plt.plot(chirp_signal.imag)
    plt.title("Imaginary Part")
    plt.xlabel("Sample")
    plt.ylabel("Amplitude")

    plt.subplot(3, 1, 3)
    plt.specgram(chirp_signal, Fs=sample_rate)
    plt.title("Spectrogram")
    plt.xlabel("Time (s)")
    plt.ylabel("Frequency (Hz)")

    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    chirp = generate_chirp(DEFAULT_F_START, DEFAULT_F_END,
                           DEFAULT_NUM_SAMPLES, DEFAULT_SAMPLE_RATE)
    plot_chirp(chirp, DEFAULT_SAMPLE_RATE)
