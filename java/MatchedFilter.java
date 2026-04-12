/*
 * ===============================================================================
 * MatchedFilter — Pulse compression matched filter, float and Q1.15 fixed-point.
 * ===============================================================================
 *
 * The matched filter is the core of pulse compression. It correlates the
 * received signal against a known reference chirp, producing a sharp peak
 * wherever an echo matches the chirp pattern.
 *
 * Two implementations in this class:
 *
 *   - filterFloat(): double-precision reference. "Golden" truth.
 *
 *   - filterFixed(): Q1.15 fixed-point using explicit short/int/long bit
 *     widths. This is the version that maps directly onto VHDL DSP48E2
 *     slice operations.
 *
 * Complex values are stored as two parallel arrays (real, imaginary) to
 * match the two-signal-path (I/Q) layout of the hardware. Every complex
 * multiply expands to four real multiplies and two adds, which is exactly
 * what you'll implement in VHDL.
 * ===============================================================================
 */
public class MatchedFilter {

    /**
     * Floating-point matched filter. This is the "golden" reference that
     * both the fixed-point version and the VHDL implementation will
     * eventually be compared against.
     *
     * What a matched filter does, in plain terms:
     *
     *   Slide a copy of the known chirp across the received signal. At
     *   every position, compute a score that tells you how well the
     *   received signal matches the chirp there. Where there's a real
     *   echo, the score is high (the chirp pattern lines up). Where
     *   there's only noise, the score is low (the noise cancels out
     *   when multiplied against the structured chirp template).
     *
     * Mathematical definition:
     *
     *   y[n] = Σ_m  r[n-m] * conj(h[m])
     *
     *   where r is the received signal and h is the matched filter
     *   impulse response. For a matched filter, h[m] = reference[m]
     *   (the transmitted waveform), so:
     *
     *   y[n] = Σ_m  r[n-m] * conj(reference[m])
     *
     *   This is correlation of r with reference. It can equivalently be
     *   expressed as convolution of r with conj(reference[::-1]) (the
     *   time-reversed, complex-conjugated reference), which is what
     *   NumPy's np.convolve(r, np.conj(ref[::-1])) does. We use that
     *   definition here because it matches NumPy's standard output.
     *
     * Complex multiply reminder:
     *
     *   (a + jb) * (c + jd) = (a*c - b*d) + j*(a*d + b*c)
     *
     *   That's four real multiplies and two adds per complex product.
     *
     * 'same' mode:
     *
     *   A full convolution of a length-M signal with a length-N kernel
     *   produces M+N-1 output samples. 'same' mode trims that down to M
     *   samples, centered on the middle of the full convolution. This
     *   makes the output line up in index-space with the input, which
     *   is convenient for plotting and for mapping detections to target
     *   delays.
     *
     * @return Two parallel arrays: [outputReal, outputImaginary].
     */
    public static double[][] filterFloat(double[] receivedReal,
                                         double[] receivedImaginary,
                                         double[] referenceReal,
                                         double[] referenceImaginary) {
        int receivedLength   = receivedReal.length;
        int kernelLength     = referenceReal.length;
        int fullOutputLength = receivedLength + kernelLength - 1;

        // Step 1: build the filter kernel by reversing and conjugating the
        // reference. "Reverse" means h[k] = ref[N-1-k], and "conjugate"
        // means we flip the sign of the imaginary part.
        double[] kernelReal      = new double[kernelLength];
        double[] kernelImaginary = new double[kernelLength];
        for (int kernelIndex = 0; kernelIndex < kernelLength; kernelIndex++) {
            kernelReal[kernelIndex]      =  referenceReal[kernelLength - 1 - kernelIndex];
            kernelImaginary[kernelIndex] = -referenceImaginary[kernelLength - 1 - kernelIndex];
        }

        // Step 2: full convolution.
        //
        // The convolution formula:
        //   fullOutput[k] = Σ_m  received[m] * kernel[k - m]
        //
        // where the sum is only over valid m values (those where both
        // `received[m]` and `kernel[k - m]` are in range). The bounds
        // receivedIndexLow and receivedIndexHigh below handle exactly that.
        double[] fullOutputReal      = new double[fullOutputLength];
        double[] fullOutputImaginary = new double[fullOutputLength];
        for (int outputIndex = 0; outputIndex < fullOutputLength; outputIndex++) {
            int receivedIndexLow  = Math.max(0, outputIndex - kernelLength + 1);
            int receivedIndexHigh = Math.min(receivedLength, outputIndex + 1);

            double accumulatorReal      = 0.0;
            double accumulatorImaginary = 0.0;
            for (int receivedIndex = receivedIndexLow;
                 receivedIndex < receivedIndexHigh; receivedIndex++) {
                int kernelIndex = outputIndex - receivedIndex;

                // Complex multiply: (a + jb)(c + jd) = (ac - bd) + j(ad + bc)
                //   a = receivedReal, b = receivedImaginary
                //   c = kernelReal,   d = kernelImaginary
                accumulatorReal += receivedReal[receivedIndex]      * kernelReal[kernelIndex]
                                 - receivedImaginary[receivedIndex] * kernelImaginary[kernelIndex];
                accumulatorImaginary += receivedReal[receivedIndex]      * kernelImaginary[kernelIndex]
                                      + receivedImaginary[receivedIndex] * kernelReal[kernelIndex];
            }
            fullOutputReal[outputIndex]      = accumulatorReal;
            fullOutputImaginary[outputIndex] = accumulatorImaginary;
        }

        // Step 3: trim to 'same' mode. Take the center M samples of the full
        // output. The offset (N-1)/2 matches numpy's convention.
        int centeringOffset = (kernelLength - 1) / 2;
        double[] outputReal      = new double[receivedLength];
        double[] outputImaginary = new double[receivedLength];
        System.arraycopy(fullOutputReal, centeringOffset,
                         outputReal, 0, receivedLength);
        System.arraycopy(fullOutputImaginary, centeringOffset,
                         outputImaginary, 0, receivedLength);
        return new double[][] { outputReal, outputImaginary };
    }


    /**
     * Fixed-point matched filter. Identical structure to the float version,
     * but every sample, every product, and every accumulator uses an explicit
     * integer type with a known bit width. This is the version that
     * translates directly to VHDL.
     *
     * Bit-width evolution through the pipeline:
     *
     *   INPUTS         short (16 bits, Q1.15)      — receivedRealQ15 etc
     *   PRODUCTS       int   (32 bits, Q2.30)      — productRealReal etc
     *   ACCUMULATOR    long  (64 bits, wider)      — accumulatorReal etc
     *   OUTPUT         long (kept in accumulator, or normalised at the end)
     *
     * Why widths grow at each stage:
     *
     *   16 * 16 → 32 bits: the product of two signed 16-bit numbers can need
     *     up to 32 bits. In the worst case, (-32768) * (-32768) = 2^30, which
     *     comfortably fits in 32 bits.
     *
     *   Σ of 32-bit products → wider accumulator: if you sum N products of
     *     up to 2^30 each, you need roughly 30 + ceil(log2(N)) bits. For
     *     N = 64 taps, that's 30 + 6 = 36 bits. 64-bit long has huge margin.
     *     On real FPGA DSP48E2 slices, the native accumulator width is 48
     *     bits, which also has plenty of room for a 64-tap complex FIR.
     *
     *   No intermediate truncation: we never shift or truncate between
     *     multiplies and accumulates. This keeps full precision through the
     *     entire FIR. The VHDL equivalent would leave the DSP48 slices
     *     accumulating without any right-shift between taps.
     *
     * Each iteration of the inner loop is ONE tap of the complex FIR. That
     * means one tap does:
     *   - 4 signed 16x16 multiplies (the four real products in the complex
     *     multiplication)
     *   - 2 additions (to combine them into real and imaginary products)
     *   - 2 accumulate operations (into the real and imaginary accumulators)
     *
     * This is what one DSP48E2 slice pair does on UltraScale+ hardware. In
     * your VHDL, each DSP48E2 will perform exactly these operations.
     */
    public static double[][] filterFixed(double[] receivedReal,
                                         double[] receivedImaginary,
                                         double[] referenceReal,
                                         double[] referenceImaginary) {
        int receivedLength   = receivedReal.length;
        int kernelLength     = referenceReal.length;
        int fullOutputLength = receivedLength + kernelLength - 1;

        // Step 1: quantize received signal to Q1.15. In hardware this is
        // what the ADC gives you directly — the received samples arrive
        // already as signed 16-bit integers. We're simulating that here.
        short[] receivedRealQ15      = new short[receivedLength];
        short[] receivedImaginaryQ15 = new short[receivedLength];
        for (int sampleIndex = 0; sampleIndex < receivedLength; sampleIndex++) {
            receivedRealQ15[sampleIndex]      = Q15.fromFloat(receivedReal[sampleIndex]);
            receivedImaginaryQ15[sampleIndex] = Q15.fromFloat(receivedImaginary[sampleIndex]);
        }

        // Step 2: build the reversed, conjugated reference chirp in Q1.15.
        // In hardware these coefficients would be pre-computed and stored
        // in a ROM or BRAM block. You'd compute them once in Python (or
        // Java), convert to Q1.15, and write a .mem file that Vivado loads
        // at synthesis time.
        short[] kernelRealQ15      = new short[kernelLength];
        short[] kernelImaginaryQ15 = new short[kernelLength];
        for (int kernelIndex = 0; kernelIndex < kernelLength; kernelIndex++) {
            kernelRealQ15[kernelIndex]      = Q15.fromFloat( referenceReal[kernelLength - 1 - kernelIndex]);
            kernelImaginaryQ15[kernelIndex] = Q15.fromFloat(-referenceImaginary[kernelLength - 1 - kernelIndex]);
        }

        // Step 3: full convolution in integer math.
        long[] fullOutputReal      = new long[fullOutputLength];
        long[] fullOutputImaginary = new long[fullOutputLength];
        for (int outputIndex = 0; outputIndex < fullOutputLength; outputIndex++) {
            int receivedIndexLow  = Math.max(0, outputIndex - kernelLength + 1);
            int receivedIndexHigh = Math.min(receivedLength, outputIndex + 1);

            long accumulatorReal      = 0L;
            long accumulatorImaginary = 0L;
            for (int receivedIndex = receivedIndexLow;
                 receivedIndex < receivedIndexHigh; receivedIndex++) {
                int kernelIndex = outputIndex - receivedIndex;

                // ==========================================================
                // ONE TAP OF THE COMPLEX FIR — this is the unit that each
                // DSP48E2 slice (pair) will implement on the FPGA.
                // ==========================================================
                //
                // Reading: "(int) x" forces widening from 16-bit short to
                // 32-bit int BEFORE the multiply, so we get a full 32-bit
                // product rather than an int16 truncation. In VHDL you'd
                // sign-extend the 16-bit operands to 32 bits for the same
                // reason.
                //
                // Complex multiply expands to four real multiplies:
                //   (a + jb)(c + jd) = (ac - bd) + j(ad + bc)
                //
                // Where:
                //   a = receivedRealQ15       (input I)
                //   b = receivedImaginaryQ15  (input Q)
                //   c = kernelRealQ15         (coefficient I)
                //   d = kernelImaginaryQ15    (coefficient Q)

                int productRealReal = (int) receivedRealQ15[receivedIndex]
                                    * (int) kernelRealQ15[kernelIndex];          // a*c
                int productImagImag = (int) receivedImaginaryQ15[receivedIndex]
                                    * (int) kernelImaginaryQ15[kernelIndex];     // b*d
                int productRealImag = (int) receivedRealQ15[receivedIndex]
                                    * (int) kernelImaginaryQ15[kernelIndex];     // a*d
                int productImagReal = (int) receivedImaginaryQ15[receivedIndex]
                                    * (int) kernelRealQ15[kernelIndex];          // b*c

                // Combine the four products into real and imaginary parts
                // of the complex product, and accumulate into the wide long.
                // The (long) cast is important: it tells Java to widen the
                // 32-bit int result into a 64-bit long BEFORE the addition,
                // so the accumulator never silently overflows. In VHDL,
                // this corresponds to using a 48-bit-wide accumulator
                // register that is sign-extended from the 32-bit product.
                accumulatorReal      += (long)(productRealReal - productImagImag);  // (ac - bd)
                accumulatorImaginary += (long)(productRealImag + productImagReal);  // (ad + bc)
            }
            fullOutputReal[outputIndex]      = accumulatorReal;
            fullOutputImaginary[outputIndex] = accumulatorImaginary;
        }

        // Step 4: trim to 'same' mode and scale the accumulator back into
        // floating-point units so we can plot the result and compare it to
        // the float reference.
        //
        // Why divide by 2^30? Each Q1.15 multiply introduced a factor of
        // 2^15 twice (once per operand), so every product is scaled by 2^30
        // relative to what the "true" float product would be. Dividing by
        // 2^30 at the very end removes that scaling.
        //
        // In hardware you don't divide — you just interpret the accumulator
        // as a Q-format number with 30 fractional bits, and you either
        // right-shift to get a narrower output, or pass the wide accumulator
        // straight to the next block.
        int centeringOffset = (kernelLength - 1) / 2;
        double scaleFactor = (double)(1L << (2 * Q15.FRAC_BITS));  // 2^30
        double[] outputReal      = new double[receivedLength];
        double[] outputImaginary = new double[receivedLength];
        for (int sampleIndex = 0; sampleIndex < receivedLength; sampleIndex++) {
            outputReal[sampleIndex]      = fullOutputReal[centeringOffset + sampleIndex]      / scaleFactor;
            outputImaginary[sampleIndex] = fullOutputImaginary[centeringOffset + sampleIndex] / scaleFactor;
        }
        return new double[][] { outputReal, outputImaginary };
    }
}
