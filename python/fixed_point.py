"""
Fixed-Point Arithmetic Helpers — Q1.15 conversion and operations.

Provides utilities to convert between floating-point and Q1.15 format,
and to perform fixed-point math that matches the Verilog implementation
bit-for-bit.
"""

import numpy as np


FRAC_BITS = 15
SCALE = 2 ** FRAC_BITS          # 32768
MAX_VAL = SCALE - 1             # 32767
MIN_VAL = -SCALE                # -32768


def float_to_q15(x: float | np.ndarray) -> int | np.ndarray:
    """
    Convert a float (or float array) in range [-1.0, 1.0) to Q1.15 integer(s).

    Args:
        x: Float or numpy array of floats

    Returns:
        Integer or numpy array of int16 values in Q1.15 format
    """

    if np.isscalar(x):
        t = int(round(float(x) * SCALE));
        return saturate_q15(t)
    else:
        t = np.round(saturate_q15(x * SCALE))
        return t.astype(np.int16)


def q15_to_float(x):
    """
    Convert Q1.15 integer(s) back to float(s).

    Args:
        x: Integer or numpy array of int16 Q1.15 values

    Returns:
        Float or numpy array of floats
    """
    if np.isscalar(x):
        return float(x) / SCALE
    else:
        return x.astype(np.float64) / SCALE



def q15_multiply(a: int | np.ndarray, b: int | np.ndarray) -> int | np.ndarray:
    """
    Multiply two Q1.15 values and return a Q1.15 result.

    The raw product of two Q1.15 values is Q2.30 (32 bits).
    This function shifts right by 15 to get back to Q1.15.

    Must match the Verilog truncation/rounding behavior exactly.

    Args:
        a: Q1.15 integer(s)
        b: Q1.15 integer(s)

    Returns:
        Q1.15 integer(s) — the product
    """
    if np.isscalar(a) and np.isscalar(b):
        product = int(a) * int(b)  # Q2.30
        # Shift right by 15 to get back to Q1.15, with rounding
        result = (product + (1 << (FRAC_BITS - 1))) >> FRAC_BITS
        return saturate_q15(result)
    else:
        product = a.astype(np.int32) * b.astype(np.int32)  # Q2.30
        result = (product + (1 << (FRAC_BITS - 1))) >> FRAC_BITS
        return saturate_q15(result).astype(np.int16)




def saturate_q15(x):
    """
    Clamp a value to the Q1.15 range [-32768, 32767].

    Args:
        x: Integer or numpy array

    Returns:
        Clamped integer or numpy array
    """
    return np.clip(x, MIN_VAL, MAX_VAL)

    # if x > MAX_VAL:
    #     return MAX_VAL
    # elif x < MIN_VAL:
    #     return MIN_VAL
    # else:
    #     return x

def complex_float_to_q15(z):
    """
    Convert a complex float array to Q1.15 format.

    Returns a tuple (real_q15, imag_q15) where each is an int16 array.
    Keeping real and imag separate makes integer complex multiplies easy
    and matches the two-signal-path layout of the hardware.

    Args:
        z: Numpy array of complex floats (or a complex scalar)

    Returns:
        Tuple (real_q15, imag_q15) of int16 arrays (or scalars)
    """
    return float_to_q15(np.real(z)), float_to_q15(np.imag(z))


def complex_q15_to_float(real_q15, imag_q15):
    """
    Convert a tuple of Q1.15 int16 arrays back to a complex float array.

    Args:
        real_q15: int16 array (or scalar) — real part in Q1.15
        imag_q15: int16 array (or scalar) — imaginary part in Q1.15

    Returns:
        Complex float array (or scalar)
    """
    return q15_to_float(real_q15) + 1j * q15_to_float(imag_q15)