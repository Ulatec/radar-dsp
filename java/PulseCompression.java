/*
 * ===============================================================================
 * Pulse Compression Radar — Java reference implementation.
 * ===============================================================================
 *
 * This file mirrors the Python reference in python/, but uses explicit primitive
 * types (short, int, long) to make bit widths obvious. This is meant as a
 * stepping stone to the Verilog implementation.
 *
 * Width conventions used throughout:
 *
 *   short  (16-bit signed)  — Q1.15 sample. Matches the FPGA ADC input width
 *                             and the output width of each FIR tap.
 *   int    (32-bit signed)  — Q1.15 * Q1.15 product. A 16x16 multiply produces
 *                             a 32-bit result (Q2.30 format, see below).
 *   long   (64-bit signed)  — FIR accumulator. When you sum many Q2.30 products
 *                             together, the accumulator needs to keep growing
 *                             to avoid overflow. 64 bits is more than enough
 *                             for any realistic chirp length.
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
 *   - To convert back to Q1.15 you would right-shift by 15. We don't do that
 *     in this matched filter — we accumulate Q2.30 products into a wide
 *     (long) accumulator and only normalise at the very end.
 *
 * Complex number representation:
 *   We keep the real and imaginary parts as two parallel arrays (e.g.
 *   `realSamples` and `imaginarySamples`). There is no Complex class. This
 *   matches the physical two-signal-path layout of I/Q in radar hardware —
 *   there are literally two wires, and each lane gets its own multiplier and
 *   accumulator. Seeing each multiply explicitly in the code makes the jump
 *   to Verilog much more natural.
 *
 * Run:
 *   javac PulseCompression.java
 *   java  PulseCompression
 *
 * Output: peak locations and magnitudes for the float and fixed-point matched
 * filter outputs, plus CFAR detections for both.
 * ===============================================================================
 */
public class PulseCompression {

    // -----------------------------------------------------------------
    // Parameters — match the Python defaults so results are comparable.
    // -----------------------------------------------------------------

    /** ADC sample rate in Hz. Set well above 2x the highest signal frequency
     *  (Nyquist) to leave headroom for filtering. 200 kHz is ~5x the 40 kHz
     *  ultrasonic carrier we will eventually demo with. */
    static final int    SAMPLE_RATE         = 200_000;

    /** Number of samples in the transmitted chirp. This is ALSO the number of
     *  taps in the matched filter: one tap per chirp sample. Increasing this
     *  increases compression gain but also FPGA resource usage. */
    static final int    CHIRP_NUM_SAMPLES   = 64;

    /** Start frequency of the linear frequency sweep, in Hz. */
    static final double CHIRP_FREQ_START_HZ = 39_000.0;

    /** End frequency of the linear frequency sweep, in Hz. The difference
     *  (end - start) is the chirp bandwidth, which determines range
     *  resolution after pulse compression. */
    static final double CHIRP_FREQ_END_HZ   = 41_000.0;


    // Q1.15 fixed-point constants (see big comment at top of file).
    static final int    Q15_FRAC_BITS = 15;
    static final int    Q15_SCALE     = 1 << Q15_FRAC_BITS;   // 32768 = 2^15
    static final int    Q15_MAX_VALUE = Q15_SCALE - 1;        // 32767
    static final int    Q15_MIN_VALUE = -Q15_SCALE;           // -32768


    // CFAR parameters.
    //
    // The CFAR window around each cell-under-test looks like:
    //
    //   [ TRAIN | GUARD | CUT | GUARD | TRAIN ]
    //     ^       ^       ^     ^       ^
    //     |       |       |     |       \
    //     |       |       |     \        right training cells
    //     |       |       |      right guard cells
    //     |       |       cell under test (the one we're deciding about)
    //     |       left guard cells (skipped to avoid target-self contamination)
    //     left training cells (used to estimate local noise floor)
    //
    // Training cells: big enough to get a stable noise estimate.
    // Guard cells:   big enough to keep the target's own energy (which
    //                spreads across many samples after the matched filter)
    //                from contaminating the training cells.

    static final int    CFAR_TRAINING_CELLS_PER_SIDE = 64;
    static final int    CFAR_GUARD_CELLS_PER_SIDE    = 32;

    /** Desired probability of false alarm per cell. Lower = fewer false
     *  detections but also harder to detect weak targets. */
    static final double CFAR_PROBABILITY_FALSE_ALARM = 1e-3;


    // =================================================================
    // Q1.15 helpers
    // =================================================================

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
    static short saturateToQ15(int rawValue) {
        if (rawValue > Q15_MAX_VALUE) return (short) Q15_MAX_VALUE;
        if (rawValue < Q15_MIN_VALUE) return (short) Q15_MIN_VALUE;
        return (short) rawValue;
    }

    /**
     * Convert a float in [-1, 1) to a Q1.15 short.
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
    static short floatToQ15(double floatValue) {
        int scaled = (int) Math.round(floatValue * Q15_SCALE);
        return saturateToQ15(scaled);
    }

    /**
     * Convert a Q1.15 short back to a float in [-1, 1).
     *
     * This is just the inverse of floatToQ15: divide by 2^15 to undo the
     * scaling. Used for debug/comparison only; real hardware wouldn't
     * convert back to float.
     */
    static double q15ToFloat(short q15Value) {
        return (double) q15Value / Q15_SCALE;
    }


    // =================================================================
    // Chirp generator
    // =================================================================

    /**
     * Generate a complex LFM (Linear Frequency Modulation) chirp.
     *
     * A chirp is a sinusoid whose frequency changes over time. For an LFM
     * chirp, the frequency increases (or decreases) linearly from startFreq
     * to endFreq over the duration of the pulse.
     *
     * The math:
     *
     *   Instantaneous frequency:   f(t) = f_start + (f_end - f_start) * t / T
     *     where T is the pulse duration (num_samples / sample_rate).
     *
     *   Phase is the integral of frequency:
     *     phase(t) = 2π * ∫ f(τ) dτ
     *              = 2π * (f_start * t + (f_end - f_start)/(2T) * t²)
     *
     *   Complex baseband signal:
     *     s(t) = exp(j * phase(t)) = cos(phase(t)) + j*sin(phase(t))
     *
     * Why complex? A real sinusoid carries both positive AND negative
     * frequency components that mirror each other. A complex exponential
     * carries only one frequency, which simplifies matched filtering and
     * makes the math cleaner. In hardware, the complex signal is implemented
     * as two real signal paths (I = cos, Q = sin) running in parallel.
     *
     * Why a linear sweep specifically? The autocorrelation of an LFM chirp
     * has a very sharp central peak, which is exactly what pulse compression
     * needs. Other waveforms exist (Barker codes, polyphase codes, nonlinear
     * chirps) but LFM is the workhorse because it's easy to generate in
     * hardware and gives great compression for its bandwidth.
     *
     * @param startFrequencyHz Frequency at t=0
     * @param endFrequencyHz   Frequency at t=T (pulse end)
     * @param numSamples       Chirp length in samples
     * @param sampleRate       Sample rate in Hz (determines T)
     * @return Two parallel arrays: [realSamples, imaginarySamples]
     */
    static double[][] generateChirp(double startFrequencyHz,
                                    double endFrequencyHz,
                                    int numSamples,
                                    int sampleRate) {
        double[] realSamples = new double[numSamples];
        double[] imaginarySamples = new double[numSamples];

        // Pulse duration in seconds: T = N / Fs.
        double chirpDurationSeconds = (double) numSamples / sampleRate;

        for (int sampleIndex = 0; sampleIndex < numSamples; sampleIndex++) {
            // Sample time in seconds: t = n / Fs.
            double timeSeconds = (double) sampleIndex / sampleRate;

            // Quadratic phase formula:
            //   phase(t) = 2π * (f_start * t + (f_end - f_start) / (2T) * t²)
            //
            // The first term (f_start * t) is a linear phase from the
            // starting frequency. The second term (the t² term) is what
            // makes the chirp sweep — its derivative with respect to time
            // is (f_end - f_start)/T, which is exactly the rate at which
            // frequency changes per second.
            double instantaneousPhase = 2.0 * Math.PI
                    * (startFrequencyHz * timeSeconds
                      + 0.5 * (endFrequencyHz - startFrequencyHz)
                            / chirpDurationSeconds
                            * timeSeconds * timeSeconds);

            // Complex exponential: exp(j*phase) = cos(phase) + j*sin(phase).
            realSamples[sampleIndex]      = Math.cos(instantaneousPhase);
            imaginarySamples[sampleIndex] = Math.sin(instantaneousPhase);
        }
        return new double[][] { realSamples, imaginarySamples };
    }


    // =================================================================
    // Simulated received signal (delayed echoes + complex noise)
    // =================================================================

    /**
     * Construct a fake received signal containing delayed, scaled copies
     * of the transmitted chirp plus complex Gaussian noise. This is how
     * we test the signal processing chain without needing real hardware.
     *
     * For each target:
     *   - "Delay" is expressed in samples. A delay of 500 samples at a
     *     200 kHz sample rate corresponds to 2.5 ms of round-trip travel,
     *     which at the speed of sound (343 m/s) is about 43 cm.
     *   - "Amplitude" models the echo loss. Real targets bounce back only
     *     a fraction of the energy that hit them, and that fraction depends
     *     on range, cross-section, and so on. We just pick a number.
     *
     * The noise is complex additive white Gaussian noise (AWGN). Both the
     * real and imaginary paths get independent Gaussian noise. The power
     * is split in half (noisePower / 2) between the two so that the
     * combined complex noise has total power equal to `noisePower`.
     * (Total power of a complex signal is |real|² + |imag|², and for
     * independent Gaussian samples each with variance σ², the sum has
     * variance 2σ². Setting σ² = noisePower/2 makes the total noisePower.)
     */
    static double[][] simulateReceivedSignal(double[] chirpReal,
                                             double[] chirpImaginary,
                                             int[] targetDelaysSamples,
                                             double[] targetAmplitudes,
                                             double noisePower,
                                             int receivedSignalLength,
                                             java.util.Random randomGenerator) {
        double[] receivedReal      = new double[receivedSignalLength];
        double[] receivedImaginary = new double[receivedSignalLength];

        // Place each target's echo into the receive buffer.
        for (int targetIndex = 0; targetIndex < targetDelaysSamples.length;
             targetIndex++) {
            int    delaySamples  = targetDelaysSamples[targetIndex];
            double echoAmplitude = targetAmplitudes[targetIndex];

            // Copy the chirp into position, starting at `delaySamples`.
            // If the chirp would run off the end of the buffer we just
            // clip it (break out of the inner loop).
            for (int chirpIndex = 0; chirpIndex < chirpReal.length; chirpIndex++) {
                int writeIndex = delaySamples + chirpIndex;
                if (writeIndex >= receivedSignalLength) break;
                receivedReal[writeIndex]      += echoAmplitude * chirpReal[chirpIndex];
                receivedImaginary[writeIndex] += echoAmplitude * chirpImaginary[chirpIndex];
            }
        }

        // Add independent Gaussian noise to each path.
        double noiseStandardDeviation = Math.sqrt(noisePower / 2.0);
        for (int sampleIndex = 0; sampleIndex < receivedSignalLength;
             sampleIndex++) {
            receivedReal[sampleIndex]      += noiseStandardDeviation
                    * randomGenerator.nextGaussian();
            receivedImaginary[sampleIndex] += noiseStandardDeviation
                    * randomGenerator.nextGaussian();
        }
        return new double[][] { receivedReal, receivedImaginary };
    }


    // =================================================================
    // Matched filter — floating point reference
    // =================================================================

    /**
     * Floating-point matched filter. This is the "golden" reference that
     * both the fixed-point Java version and the Verilog implementation
     * will eventually be compared against.
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
    static double[][] matchedFilterFloat(double[] receivedReal,
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
            // Valid range of m (index into received signal) for this output k.
            int receivedIndexLow  = Math.max(0, outputIndex - kernelLength + 1);
            int receivedIndexHigh = Math.min(receivedLength, outputIndex + 1);

            double accumulatorReal      = 0.0;
            double accumulatorImaginary = 0.0;
            for (int receivedIndex = receivedIndexLow;
                 receivedIndex < receivedIndexHigh; receivedIndex++) {
                // For each valid m, the kernel index is k - m.
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


    // =================================================================
    // Matched filter — Q1.15 fixed point (this is the HDL-relevant version)
    // =================================================================

    /**
     * Fixed-point matched filter. Identical structure to the float version,
     * but every sample, every product, and every accumulator uses an explicit
     * integer type with a known bit width. This is the version that
     * translates directly to Verilog.
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
     *     entire FIR. The Verilog equivalent would leave the DSP48 slices
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
     * your Verilog, each DSP48E2 will perform exactly these operations.
     */
    static double[][] matchedFilterFixed(double[] receivedReal,
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
            receivedRealQ15[sampleIndex]      = floatToQ15(receivedReal[sampleIndex]);
            receivedImaginaryQ15[sampleIndex] = floatToQ15(receivedImaginary[sampleIndex]);
        }

        // Step 2: build the reversed, conjugated reference chirp in Q1.15.
        // In hardware these coefficients would be pre-computed and stored
        // in a ROM or BRAM block. You'd compute them once in Python (or
        // Java), convert to Q1.15, and write a .mem file that Vivado loads
        // at synthesis time.
        short[] kernelRealQ15      = new short[kernelLength];
        short[] kernelImaginaryQ15 = new short[kernelLength];
        for (int kernelIndex = 0; kernelIndex < kernelLength; kernelIndex++) {
            kernelRealQ15[kernelIndex]      = floatToQ15( referenceReal[kernelLength - 1 - kernelIndex]);
            kernelImaginaryQ15[kernelIndex] = floatToQ15(-referenceImaginary[kernelLength - 1 - kernelIndex]);
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
                // product rather than an int16 truncation. In Verilog you'd
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
                // so the accumulator never silently overflows. In Verilog,
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
        double scaleFactor = (double)(1L << (2 * Q15_FRAC_BITS));  // 2^30
        double[] outputReal      = new double[receivedLength];
        double[] outputImaginary = new double[receivedLength];
        for (int sampleIndex = 0; sampleIndex < receivedLength; sampleIndex++) {
            outputReal[sampleIndex]      = fullOutputReal[centeringOffset + sampleIndex]      / scaleFactor;
            outputImaginary[sampleIndex] = fullOutputImaginary[centeringOffset + sampleIndex] / scaleFactor;
        }
        return new double[][] { outputReal, outputImaginary };
    }


    // =================================================================
    // CA-CFAR detector
    // =================================================================

    /**
     * Compute the CFAR threshold scaling factor alpha.
     *
     * Derivation (sketch):
     *   Under a "noise only" hypothesis, if the matched filter output is
     *   complex Gaussian, then |MF|² follows an exponential distribution.
     *   The sum of N training cells (each exponential) divided by N is a
     *   chi-squared-ish quantity whose distribution is known. We set the
     *   probability that |MF(CUT)|² exceeds alpha * (training average) to
     *   equal the desired false-alarm probability PFA, solve for alpha,
     *   and get:
     *
     *       alpha = N * (PFA^(-1/N) - 1)
     *
     *   where N is the total number of training cells (both sides combined).
     *   Higher N gives a more stable estimate; lower PFA pushes alpha up
     *   (fewer false alarms but potentially missing weak targets).
     *
     *   You don't need to re-derive this in an interview, but you should be
     *   able to say: "alpha comes from solving the false-alarm probability
     *   for a known noise distribution; it scales with 1/PFA and depends on
     *   how many training cells we use for the noise estimate."
     */
    static double computeThresholdFactor(int totalTrainingCells,
                                         double probabilityFalseAlarm) {
        return totalTrainingCells
             * (Math.pow(probabilityFalseAlarm, -1.0 / totalTrainingCells) - 1.0);
    }

    /**
     * Sliding-window CA-CFAR (Cell-Averaging Constant False Alarm Rate).
     *
     * For each sample in `magnitudes`:
     *   1. Treat that sample as the "cell under test" (CUT).
     *   2. Look at the training cells on both sides (skipping the nearby
     *      guard cells that could be contaminated by the CUT's own energy).
     *   3. Average those training cells to estimate the local noise floor.
     *   4. Multiply the average by alpha (from computeThresholdFactor).
     *   5. If the CUT exceeds that threshold, flag a detection.
     *
     * The "constant false alarm rate" property comes from the fact that the
     * threshold always sits at the same statistical distance above the local
     * noise — no matter what the absolute noise level is, the rate of
     * false alarms per cell stays roughly constant.
     *
     * Edge handling: cells near the beginning or end of the array don't have
     * a complete window around them. The simplest approach — used here — is
     * to skip those cells entirely (no detection, threshold = 0). A more
     * sophisticated implementation would reflect the window or shrink it,
     * but the hardware usually has a known warmup region so this is fine.
     *
     * The `thresholdsOut` parameter is filled in as a side effect, purely
     * so the caller can plot the adaptive threshold alongside the data.
     */
    static boolean[] caCfar(double[] magnitudes,
                            int trainingCellsPerSide,
                            int guardCellsPerSide,
                            double probabilityFalseAlarm,
                            double[] thresholdsOut) {
        int numSamples = magnitudes.length;
        boolean[] detections = new boolean[numSamples];

        // Compute alpha once, reuse for every cell.
        double thresholdScalingFactor = computeThresholdFactor(
                2 * trainingCellsPerSide, probabilityFalseAlarm);

        // Half-window size from the CUT out to the edge of the training
        // region on one side. This is the minimum distance from the edge
        // of the array for which we have a full window.
        int halfWindowSize = trainingCellsPerSide + guardCellsPerSide;

        for (int cellUnderTest = 0; cellUnderTest < numSamples; cellUnderTest++) {
            // Skip edge cells without a full window.
            if (cellUnderTest < halfWindowSize
             || cellUnderTest >= numSamples - halfWindowSize) {
                thresholdsOut[cellUnderTest] = 0.0;
                continue;
            }

            // Sum the training cells on both sides, skipping guard cells.
            double trainingSum = 0.0;

            // Left side: from (CUT - halfWindow) up to (CUT - guard - 1).
            for (int trainingCell = cellUnderTest - halfWindowSize;
                 trainingCell <= cellUnderTest - guardCellsPerSide - 1;
                 trainingCell++) {
                trainingSum += magnitudes[trainingCell];
            }
            // Right side: from (CUT + guard + 1) up to (CUT + halfWindow).
            for (int trainingCell = cellUnderTest + guardCellsPerSide + 1;
                 trainingCell <= cellUnderTest + halfWindowSize;
                 trainingCell++) {
                trainingSum += magnitudes[trainingCell];
            }

            // Average over the total number of training cells.
            double trainingAverage = trainingSum / (2 * trainingCellsPerSide);

            // Scale by alpha to get the detection threshold for this cell.
            double adaptiveThreshold = thresholdScalingFactor * trainingAverage;
            thresholdsOut[cellUnderTest] = adaptiveThreshold;

            // Detection decision.
            if (magnitudes[cellUnderTest] > adaptiveThreshold) {
                detections[cellUnderTest] = true;
            }
        }
        return detections;
    }


    // =================================================================
    // Main — end-to-end demo
    // =================================================================

    /**
     * Runs the entire pulse compression chain end-to-end in both floating
     * point and Q1.15 fixed point, then prints the peak locations and
     * detection results. Useful as a sanity check that everything still
     * agrees after the fixed-point conversion.
     */
    public static void main(String[] args) {
        // Fixed seed so results are reproducible across runs (and across
        // the Python reference, when using the same seed there).
        java.util.Random randomGenerator = new java.util.Random(42);

        // ----------------- 1. Generate the transmitted chirp.
        double[][] chirp = generateChirp(
                CHIRP_FREQ_START_HZ, CHIRP_FREQ_END_HZ,
                CHIRP_NUM_SAMPLES, SAMPLE_RATE);
        double[] chirpReal      = chirp[0];
        double[] chirpImaginary = chirp[1];

        // ----------------- 2. Simulate the received signal.
        int[]    targetDelaysSamples  = { 300, 900, 1500 };
        double[] targetAmplitudes     = { 1.0, 0.8,  0.5 };
        int      receivedSignalLength = 2000;
        double   noisePower           = 0.01;

        double[][] received = simulateReceivedSignal(
                chirpReal, chirpImaginary,
                targetDelaysSamples, targetAmplitudes,
                noisePower, receivedSignalLength, randomGenerator);
        double[] receivedReal      = received[0];
        double[] receivedImaginary = received[1];

        // ----------------- 3. Matched filter (both float and fixed-point).
        double[][] matchedFilterOutputFloat = matchedFilterFloat(
                receivedReal, receivedImaginary,
                chirpReal, chirpImaginary);
        double[][] matchedFilterOutputFixed = matchedFilterFixed(
                receivedReal, receivedImaginary,
                chirpReal, chirpImaginary);

        // ----------------- 4. Compute magnitude-squared for CFAR.
        //
        // We use |MF|² (not |MF|) so we can skip the square root. The CFAR
        // threshold math works fine in the squared-magnitude domain; it
        // just means alpha gets interpreted in power units instead of
        // amplitude units. Skipping the sqrt is a standard hardware
        // optimisation — square roots are expensive in FPGA logic.
        double[] magnitudeSquaredFloat = new double[receivedSignalLength];
        double[] magnitudeSquaredFixed = new double[receivedSignalLength];
        for (int sampleIndex = 0; sampleIndex < receivedSignalLength;
             sampleIndex++) {
            magnitudeSquaredFloat[sampleIndex]
                    = matchedFilterOutputFloat[0][sampleIndex] * matchedFilterOutputFloat[0][sampleIndex]
                    + matchedFilterOutputFloat[1][sampleIndex] * matchedFilterOutputFloat[1][sampleIndex];
            magnitudeSquaredFixed[sampleIndex]
                    = matchedFilterOutputFixed[0][sampleIndex] * matchedFilterOutputFixed[0][sampleIndex]
                    + matchedFilterOutputFixed[1][sampleIndex] * matchedFilterOutputFixed[1][sampleIndex];
        }

        // ----------------- 5. Run CA-CFAR on both magnitude arrays.
        double[]  thresholdsFloat = new double[receivedSignalLength];
        double[]  thresholdsFixed = new double[receivedSignalLength];
        boolean[] detectionsFloat = caCfar(magnitudeSquaredFloat,
                CFAR_TRAINING_CELLS_PER_SIDE, CFAR_GUARD_CELLS_PER_SIDE,
                CFAR_PROBABILITY_FALSE_ALARM, thresholdsFloat);
        boolean[] detectionsFixed = caCfar(magnitudeSquaredFixed,
                CFAR_TRAINING_CELLS_PER_SIDE, CFAR_GUARD_CELLS_PER_SIDE,
                CFAR_PROBABILITY_FALSE_ALARM, thresholdsFixed);

        // ----------------- 6. Summary report.
        int floatPeakIndex = argmax(magnitudeSquaredFloat);
        int fixedPeakIndex = argmax(magnitudeSquaredFixed);
        System.out.printf("Float peak: mag^2=%.2f at index %d%n",
                magnitudeSquaredFloat[floatPeakIndex], floatPeakIndex);
        System.out.printf("Fixed peak: mag^2=%.2f at index %d%n",
                magnitudeSquaredFixed[fixedPeakIndex], fixedPeakIndex);
        System.out.printf("Float detections: %d%n", countTrue(detectionsFloat));
        System.out.printf("Fixed detections: %d%n", countTrue(detectionsFixed));

        System.out.print("Float detection indices: ");
        printIndices(detectionsFloat);
        System.out.print("Fixed detection indices: ");
        printIndices(detectionsFixed);
    }


    // =================================================================
    // Small array utilities used only by main.
    // =================================================================

    /** Return the index of the largest element in an array. */
    static int argmax(double[] values) {
        int bestIndex = 0;
        for (int i = 1; i < values.length; i++) {
            if (values[i] > values[bestIndex]) bestIndex = i;
        }
        return bestIndex;
    }

    /** Count how many elements of a boolean array are true. */
    static int countTrue(boolean[] flags) {
        int count = 0;
        for (boolean flag : flags) if (flag) count++;
        return count;
    }

    /** Print the indices of the true elements in a boolean array. */
    static void printIndices(boolean[] flags) {
        StringBuilder builder = new StringBuilder("[");
        boolean first = true;
        for (int i = 0; i < flags.length; i++) {
            if (flags[i]) {
                if (!first) builder.append(", ");
                builder.append(i);
                first = false;
            }
        }
        builder.append("]");
        System.out.println(builder);
    }
}
