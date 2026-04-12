/*
 * ===============================================================================
 * ReceivedSignal — Simulated radar echoes with additive complex noise.
 * ===============================================================================
 *
 * In a real system the received signal comes back from the antenna through
 * an ADC. Here we fake it: place delayed, scaled copies of the chirp into
 * a buffer, add complex Gaussian noise, and hand that to the matched filter
 * as if it had come from the hardware.
 * ===============================================================================
 */
public class ReceivedSignal {

    /**
     * Construct a fake received signal containing delayed, scaled copies
     * of the transmitted chirp plus complex Gaussian noise.
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
     *
     * @return Two parallel arrays: [receivedReal, receivedImaginary]
     */
    public static double[][] simulate(double[] chirpReal,
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
}
