"""
CA-CFAR (Cell-Averaging Constant False Alarm Rate) Detector.

Adaptive threshold detection that estimates the local noise floor
from training cells surrounding each cell-under-test (CUT).
"""

import numpy as np
import matplotlib.pyplot as plt

# Default CFAR parameters
DEFAULT_NUM_TRAIN = 64     # Training cells on each side of the CUT
DEFAULT_NUM_GUARD = 32      # Guard cells on each side of the CUT
DEFAULT_PFA = 1e-3         # Desired probability of false alarm


def ca_cfar(magnitudes, num_train, num_guard, pfa):
    """
    Run CA-CFAR detection on a 1D magnitude array.

    For each cell-under-test (CUT):
      1. Average the training cells on both sides (skip guard cells)
      2. Multiply by a threshold factor derived from pfa
      3. If CUT exceeds the threshold, flag as detection

    Args:
        magnitudes: 1D numpy array of real values (e.g. |matched_filter_output|^2)
        num_train:  Number of training cells on EACH side of the CUT
        num_guard:  Number of guard cells on EACH side of the CUT
        pfa:        Desired probability of false alarm

    Returns:
        detections: Boolean numpy array, True where a target is detected
        thresholds: Numpy array of the adaptive threshold at each cell
    """
    # Initialize detection array and threshold array
    num_samples = len(magnitudes)
    detections = np.zeros(num_samples, dtype=bool)
    thresholds = np.zeros(num_samples)
    
    # The total number of training cells used for threshold calculation
    N_train_total = 2 * num_train
    
    # Calculate the constant threshold factor once
    alpha = compute_threshold_factor(2*num_train, pfa)

    for i in range(num_samples):
        # Skip guard cells (indices from num_guard to num_guard-1, and num_samples-num_guard to num_samples-1)
        if (i < num_guard) or (i >= num_samples - num_guard):
            thresholds[i] = 0 # Set threshold to 0 or some sentinel value for guard cells
            continue

        # Define the window boundaries for training cells
        start_train = max(0, i - num_train - num_guard)
        end_train = min(num_samples - 1, i + num_train + num_guard)
        
        # The actual training window is [i - num_train - num_guard, i - num_guard - 1]
        # and [i + num_guard + 1, i + num_train + num_guard]
        
        # Left training window: [i - num_train - num_guard, i - num_guard - 1]
        left_start = max(0, i - num_train - num_guard)
        left_end = i - num_guard - 1
        
        # Right training window: [i + num_guard + 1, i + num_train + num_guard]
        right_start = i + num_guard + 1
        right_end = min(num_samples - 1, i + num_train + num_guard)
        
        # Extract training cell magnitudes
        left_train = magnitudes[left_start:left_end + 1]
        right_train = magnitudes[right_start:right_end + 1]
        
        # Average the training cells (assuming equal weighting)
        # We must handle cases where the window is truncated at the edges
        avg_train = np.mean(np.concatenate((left_train, right_train)))
        
        # Calculate the adaptive threshold
        thresholds[i] = alpha * avg_train
        
        # Detection decision
        if magnitudes[i] > thresholds[i]:
            detections[i] = True
            
    return detections, thresholds


def compute_threshold_factor(num_train, pfa):
    """
    Compute the CFAR threshold multiplier from the number of
    training cells and desired probability of false alarm.

    Args:
        num_train: Total number of training cells (both sides combined)
        pfa:       Desired probability of false alarm

    Returns:
        alpha: Threshold scaling factor
    """
    # The threshold factor alpha is derived from the chi-squared distribution
    # for the sum of squared normalized Gaussian random variables.
    # For a given PFA and N_train, alpha is often approximated or calculated
    # using the inverse CDF of the chi-squared distribution.
    # A common approximation for the threshold factor is:
    # alpha = (N_train * (1 - pfa))^(-1/2) * (1 + 2/N_train)
    # However, for simplicity and matching typical DSP textbook examples,
    # we use a simplified form derived from the assumption of Gaussian noise.
    
    # A more robust approach often involves the inverse CDF of chi-squared.
    # For this implementation, we will use a common simplified form:
    return num_train *(pfa ** (-1/num_train) -1)


def plot_cfar(magnitudes, thresholds, detections, sample_rate):
    """
    Plot the magnitude signal, adaptive threshold, and detection flags.

    Args:
        magnitudes: Input magnitude array
        thresholds: Adaptive threshold from ca_cfar()
        detections: Boolean detection array from ca_cfar()
        sample_rate: Sample rate (Hz)
    """
    # Time vector for plotting
    time_vector = np.arange(len(magnitudes)) / sample_rate

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


if __name__ == "__main__":
    # Test with synthetic data: a few peaks embedded in noise
    pass
