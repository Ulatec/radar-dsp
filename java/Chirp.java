/*
 * ===============================================================================
 * Chirp — Linear FM chirp generator (floating point reference).
 * ===============================================================================
 *
 * Produces a complex LFM chirp as two parallel arrays (real, imaginary).
 * This is the floating-point "truth" that the VHDL DDS chirp generator
 * will be compared against.
 * ===============================================================================
 */
public class Chirp {

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
    public static double[][] generate(double startFrequencyHz,
                                      double endFrequencyHz,
                                      int numSamples,
                                      int sampleRate) {
        double[] realSamples      = new double[numSamples];
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
}
