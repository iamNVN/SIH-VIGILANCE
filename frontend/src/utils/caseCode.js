/**
 * Displays complaint IDs as 4-char alphanumeric case codes ("BD4K") instead
 * of raw sequential numbers -- purely cosmetic, computed client-side from
 * the real numeric id (still used for routing/API calls, never replaced).
 *
 * A plain base36 pad-out of the id (1 -> "0001") would still look
 * sequential, so the id is first scrambled by a multiplicative bijection
 * over Z/M (M = 36^4). M's only prime factors are 2 and 3, so any
 * multiplier coprime to 6 is coprime to M -- making this a true bijection
 * (no two ids ever collide on the same code), just with no visible order.
 */
const M = 36 ** 4; // 1,679,616
const MULTIPLIER = 1000003; // prime, coprime to 6 -> coprime to M

export function caseCode(id) {
  const scrambled = (id * MULTIPLIER) % M;
  return scrambled.toString(36).toUpperCase().padStart(4, "0");
}

function modInverse(a, m) {
  let [oldR, r] = [a, m];
  let [oldS, s] = [1, 0];
  while (r !== 0) {
    const q = Math.floor(oldR / r);
    [oldR, r] = [r, oldR - q * r];
    [oldS, s] = [s, oldS - q * s];
  }
  return ((oldS % m) + m) % m;
}

const MULTIPLIER_INV = modInverse(MULTIPLIER, M);

/** Inverse of `caseCode` -- lets the Cases search box accept a typed case
 * code and turn it back into the real id to query by, without the backend
 * needing to know this display scheme exists. */
export function decodeCaseCode(code) {
  if (!/^[0-9A-Z]{1,4}$/i.test(code)) return null;
  const scrambled = parseInt(code, 36);
  if (Number.isNaN(scrambled)) return null;
  return (scrambled * MULTIPLIER_INV) % M;
}
