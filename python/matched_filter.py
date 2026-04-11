"""
Matched Filter — optimal detection of a known chirp signal in noise.

Convolves the received signal with the time-reversed complex conjugate
of the reference chirp. Peaks in the output correspond to target echoes.
"""

import numpy as np
import matplotlib.pyplot as plt
import fixed_point as fp
def matched_filter(received, reference_chirp):
    """
    Apply the matched filter to a received signal.

    Args:
        received:        Complex numpy array of received samples (echoes + noise)
        reference_chirp: Complex numpy array of the transmitted chirp waveform

    Returns:
        Complex numpy array — the matched filter output.
        Peaks in abs() of this correspond to target locations.
    """
    return np.convolve(received, np.conj(reference_chirp[::-1]), mode='same')

def matched_filter_fixed(received, reference_chirp):
    """
    Fixed-point matched filter that mimics the hardware signal path.

    Quantizes both inputs to Q1.15, then performs the complex convolution
    directly using integer multiply-accumulate in wide accumulators (int64).
    Returns a complex float array so it can be plotted and compared against
    the floating-point reference.

    Args:
        received:        Complex numpy array of received samples
        reference_chirp: Complex numpy array of the transmitted chirp

    Returns:
        Complex numpy array — same length as `received`, representing the
        matched filter output scaled back to float for easy comparison.
    """
    # 1. Quantize inputs to Q1.15 (separate real/imag int16 arrays)
    recv_r, recv_i = fp.complex_float_to_q15(received)
    ref_r,  ref_i  = fp.complex_float_to_q15(reference_chirp)

    # 2. Build the matched filter coefficients: conj(reference[::-1])
    #    (reversed and complex-conjugated). This is the FIR kernel.
    v_r = ref_r[::-1].astype(np.int64)
    v_i = (-ref_i[::-1]).astype(np.int64)

    a_r = recv_r.astype(np.int64)
    a_i = recv_i.astype(np.int64)

    M = len(a_r)         # received length
    N = len(v_r)         # kernel length
    full_len = M + N - 1

    # 3. Direct convolution: full_output[k] = sum_m a[m] * v[k-m]
    #    (complex multiply: (ar + j ai)(vr + j vi) = (ar*vr - ai*vi) + j(ar*vi + ai*vr))
    full_r = np.zeros(full_len, dtype=np.int64)
    full_i = np.zeros(full_len, dtype=np.int64)

    for k in range(full_len):
        m_lo = max(0, k - N + 1)
        m_hi = min(M, k + 1)
        if m_lo >= m_hi:
            continue
        ar = a_r[m_lo:m_hi]
        ai = a_i[m_lo:m_hi]
        vr = v_r[k - m_hi + 1 : k - m_lo + 1][::-1]
        vi = v_i[k - m_hi + 1 : k - m_lo + 1][::-1]
        full_r[k] = np.sum(ar * vr - ai * vi)
        full_i[k] = np.sum(ar * vi + ai * vr)

    # 4. Trim to 'same' mode: take the centered M samples.
    offset = (N - 1) // 2
    out_r = full_r[offset : offset + M]
    out_i = full_i[offset : offset + M]

    # 5. Convert accumulator back to float units for comparison.
    #    Each Q1.15 multiply contributes a factor of 2^15 twice, so divide by 2^30.
    scale = float(1 << (2 * fp.FRAC_BITS))  # 2^30
    return (out_r + 1j * out_i) / scale

def plot_matched_filter_output(mf_output, sample_rate):
    """
    Plot the magnitude of the matched filter output.

    Verify that the peak is sharp and located at the expected delay.

    Args:
        mf_output:   Complex numpy array from matched_filter()
        sample_rate: Sample rate (Hz)
    """
    plt.figure()
    plt.plot(np.abs(mf_output))
    plt.title("Matched Filter Output Magnitude")
    plt.xlabel("Sample Index")
    plt.ylabel("Magnitude")
    plt.grid()
    plt.show()
    


if __name__ == "__main__":
    from chirp import generate_chirp, DEFAULT_SAMPLE_RATE, DEFAULT_NUM_SAMPLES
    from chirp import DEFAULT_F_START, DEFAULT_F_END

    # Generate a chirp and run it through the matched filter against itself
    # (autocorrelation — should produce a sharp peak at the center)
    chirp = generate_chirp(DEFAULT_F_START, DEFAULT_F_END,
                           DEFAULT_NUM_SAMPLES, DEFAULT_SAMPLE_RATE)
    mf_out = matched_filter(chirp, chirp)
    plot_matched_filter_output(mf_out, DEFAULT_SAMPLE_RATE)
