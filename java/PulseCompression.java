/*
 * ===============================================================================
 * PulseCompression — End-to-end demo driver for the radar-dsp Java reference.
 * ===============================================================================
 *
 * This is the entry point. It wires together the individual blocks
 * (Chirp, ReceivedSignal, MatchedFilter, Cfar) into the full signal
 * chain and runs it in both floating-point and Q1.15 fixed-point.
 *
 * The point of having a Java reference at all:
 *   The Python reference in python/ is the easiest to iterate on. The
 *   Java reference uses explicit primitive types (short, int, long) so
 *   that the bit widths at every stage are visible in the source code.
 *   That makes this the cleanest bridge from "working algorithm" to
 *   "VHDL RTL" — you can map each Java line directly to a hardware
 *   operation.
 *
 * Run:
 *   javac *.java
 *   java  PulseCompression
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

    /** Training cells per side of the CFAR window. */
    static final int    CFAR_TRAINING_CELLS_PER_SIDE = 64;

    /** Guard cells per side of the CFAR window. */
    static final int    CFAR_GUARD_CELLS_PER_SIDE    = 32;

    /** Desired CFAR probability of false alarm per cell. */
    static final double CFAR_PROBABILITY_FALSE_ALARM = 1e-3;


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
        double[][] chirp = Chirp.generate(
                CHIRP_FREQ_START_HZ, CHIRP_FREQ_END_HZ,
                CHIRP_NUM_SAMPLES, SAMPLE_RATE);
        double[] chirpReal      = chirp[0];
        double[] chirpImaginary = chirp[1];

        // ----------------- 2. Simulate the received signal.
        int[]    targetDelaysSamples  = { 300, 900, 1500 };
        double[] targetAmplitudes     = { 1.0, 0.8,  0.5 };
        int      receivedSignalLength = 2000;
        double   noisePower           = 0.01;

        double[][] received = ReceivedSignal.simulate(
                chirpReal, chirpImaginary,
                targetDelaysSamples, targetAmplitudes,
                noisePower, receivedSignalLength, randomGenerator);
        double[] receivedReal      = received[0];
        double[] receivedImaginary = received[1];

        // ----------------- 3. Matched filter (both float and fixed-point).
        double[][] matchedFilterOutputFloat = MatchedFilter.filterFloat(
                receivedReal, receivedImaginary,
                chirpReal, chirpImaginary);
        double[][] matchedFilterOutputFixed = MatchedFilter.filterFixed(
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
        boolean[] detectionsFloat = Cfar.detect(magnitudeSquaredFloat,
                CFAR_TRAINING_CELLS_PER_SIDE, CFAR_GUARD_CELLS_PER_SIDE,
                CFAR_PROBABILITY_FALSE_ALARM, thresholdsFloat);
        boolean[] detectionsFixed = Cfar.detect(magnitudeSquaredFixed,
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
