/*
 * ===============================================================================
 * Cfar — Cell-Averaging Constant False Alarm Rate detector.
 * ===============================================================================
 *
 * Given a magnitude array (typically |matched_filter_output|²), decide
 * which cells are targets and which are noise. The threshold for each
 * cell is computed adaptively from the surrounding cells' noise level,
 * so the false-alarm rate stays roughly constant regardless of the
 * absolute noise floor.
 *
 * Window layout around each cell-under-test:
 *
 *   [ TRAIN | GUARD | CUT | GUARD | TRAIN ]
 *     ^       ^       ^     ^       ^
 *     |       |       |     |       \
 *     |       |       |     \        right training cells
 *     |       |       |      right guard cells
 *     |       |       cell under test (the one we're deciding about)
 *     |       left guard cells (skipped to avoid target-self contamination)
 *     left training cells (used to estimate local noise floor)
 *
 * Training cells: big enough to get a stable noise estimate.
 * Guard cells:   big enough to keep the target's own energy (which
 *                spreads across many samples after the matched filter)
 *                from contaminating the training cells.
 * ===============================================================================
 */
public class Cfar {

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
    public static double computeThresholdFactor(int totalTrainingCells,
                                                double probabilityFalseAlarm) {
        return totalTrainingCells
             * (Math.pow(probabilityFalseAlarm, -1.0 / totalTrainingCells) - 1.0);
    }

    /**
     * Sliding-window CA-CFAR.
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
     * to skip those cells entirely (no detection, threshold = 0).
     *
     * The `thresholdsOut` parameter is filled in as a side effect, purely
     * so the caller can plot the adaptive threshold alongside the data.
     */
    public static boolean[] detect(double[] magnitudes,
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
}
