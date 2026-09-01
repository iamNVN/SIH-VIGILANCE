/**
 * A bare "18%" reads as "unreliable" out of context -- but with ~40
 * candidate cash-out points per city, random guessing succeeds ~2.5% of
 * the time, so 18% is a genuine, large lift over chance. This computes
 * that lift honestly from real numbers already in the response (never a
 * fabricated confidence tier) so the UI can say so instead of just
 * printing the raw percentage.
 */
export function confidenceContext(confidence, nCandidates) {
  if (!nCandidates || nCandidates <= 0) return null;
  const randomRate = 1 / nCandidates;
  const lift = confidence / randomRate;
  return {
    randomRate,
    lift,
    nCandidates,
    sentence:
      lift >= 1.5
        ? `${lift.toFixed(1)}x more likely than picking at random among the ${nCandidates} candidate locations considered.`
        : `About as likely as picking at random among the ${nCandidates} candidate locations considered.`,
  };
}
