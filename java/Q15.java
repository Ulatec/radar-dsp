/*
 * ===============================================================================
 * Q15 — Q1.15 fixed-point arithmetic helpers.
 * ===============================================================================
 *
 * Q1.15 format quick reference:
 *   - 1 sign bit + 15 fractional bits = 16 bits total.
 *   - Represents values in [-1.0, +1.0) as integers in [-32768, +32767].
 *   - To encode a float: multiply by 2^15 (=32768), round, clamp to int16 range.
 *   - To decode a Q1.15 integer: divide by 32768.
 *   - Why: the FPGA has no floating-point, so all DSP is integer. Normalising
 *     signal amplitudes to [-1, +1] lets us use the maximum fractional precision
 *     available in 16 bits.
 *
 * Q2.30 is what you get when you multiply two Q1.15 values together:
 *   - 2 integer bits (sign + 1 extra because the product can briefly sit
 *     outside the [-1, 1) range during intermediate math) + 30 fractional bits.
 *   - Stored as a 32-bit signed integer.
 *   - To convert back to Q1.15 you would right-shift by 15.
 * ===============================================================================
 */
public class Q15 {

    /** Number of fractional bits in the Q1.15 format. */
    public static final int FRAC_BITS = 15;

    /** Scale factor used when converting between float and Q1.15. 2^15 = 32768. */
    public static final int SCALE = 1 << FRAC_BITS;

    /** Maximum representable Q1.15 integer value. */
    public static final int MAX_VALUE = SCALE - 1;       // 32767

    /** Minimum representable Q1.15 integer value. */
    public static final int MIN_VALUE = -SCALE;          // -32768


    /**
     * Clamp an integer to the Q1.15 range [-32768, 32767].
     *
     * Why this matters: when you scale a float by 2^15 (to put it into Q1.15
     * land), the result might exceed the int16 range. For example, 1.0 * 32768
     * is exactly 32768, but the maximum value you can store in a signed 16-bit
     * integer is 32767. Without clamping, the value would silently wrap to
     * -32768, which is catastrophic for signal processing — a max-positive
     * sample becomes a max-negative one. Saturation (clamping) is the
     * hardware-friendly way to handle this: values that exceed the range are
     * held at the extreme instead of wrapping.
     */
    public static short saturate(int rawValue) {
        if (rawValue > MAX_VALUE) return (short) MAX_VALUE;
        if (rawValue < MIN_VALUE) return (short) MIN_VALUE;
        return (short) rawValue;
    }

    /**
     * Convert a float in [-1, 1) to a Q1.15 short with rounding + saturation.
     *
     * Steps:
     *   1. Multiply by 2^15 to place the float's value on the integer grid
     *      [-32768, 32767]. A float of 0.5 becomes 16384; a float of -0.25
     *      becomes -8192.
     *   2. Round to the nearest integer. (The FPGA will do truncation OR
     *      rounding depending on how you write the Verilog. For bit-exact
     *      matching, Python and Java must do the same thing; here we round.)
     *   3. Saturate to the int16 range so we never wrap.
     */
    public static short fromFloat(double floatValue) {
        int scaled = (int) Math.round(floatValue * SCALE);
        return saturate(scaled);
    }

    /**
     * Convert a Q1.15 short back to a float in [-1, 1).
     *
     * Inverse of fromFloat: divide by 2^15 to undo the scaling. Used for
     * debug/comparison only; real hardware wouldn't convert back to float.
     */
    public static double toFloat(short q15Value) {
        return (double) q15Value / SCALE;
    }
}
