"""
case_code.py -- the SAME scrambled 4-char display code the frontend shows
for a complaint (frontend/src/utils/caseCode.js), reimplemented here so
backend-emitted text (the Live Investigation Feed's event messages) names
a case identically to however the UI is already showing it elsewhere --
"Case #FLYY" here must mean the same complaint as "#FLYY" on the Cases
page, not a second, disagreeing label for it.

Bijective (no two complaint ids ever collide on the same code): M = 36^4
factors only into 2 and 3, so any multiplier coprime to 6 is coprime to M,
making multiplication by it a permutation of Z/M. See caseCode.js for the
full rationale -- this must stay byte-for-byte in sync with that file's
constants and algorithm.
"""

_M = 36 ** 4  # 1,679,616
_MULTIPLIER = 1000003  # prime, coprime to 6 -> coprime to M
_DIGITS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _to_base36(n: int) -> str:
    if n == 0:
        return "0"
    digits = []
    while n:
        n, rem = divmod(n, 36)
        digits.append(_DIGITS[rem])
    return "".join(reversed(digits))


def case_code(complaint_id: int) -> str:
    scrambled = (complaint_id * _MULTIPLIER) % _M
    return _to_base36(scrambled).zfill(4)
