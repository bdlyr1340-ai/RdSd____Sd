"""Human-like typing simulator.

The goal: produce real per-character keystrokes with timing patterns
indistinguishable from a human. Each call to :func:`human_type` issues
one ``page.keyboard.type(ch, delay=0)`` per character, generating proper
``keydown``/``keypress``/``keyup`` events — NOT a single bulk insert.

Realism layers:

  • Variable inter-key delay drawn from a lognormal-ish distribution.
  • Char-class biases: spaces, punctuation, digits, capitals, accents
    each get their own base distribution.
  • Occasional "thinking pauses" (~3-4% of keys, +0.3..0.9 s).
  • Burst patterns — sometimes 2-3 fast keys in a row (start-of-word).
  • Initial orientation pause before the first character.
  • Settle pause after the last character.
  • OPTIONAL realistic typos: type the wrong adjacent key, pause, hit
    Backspace, then type the correct key. Disabled inside emails, URLs,
    pure-digit strings (codes/phone numbers) to avoid corrupting them.

This module has no Playwright dependency — it accepts any object with
``async keyboard.type(ch, delay=0)`` and ``async keyboard.press("Backspace")``.
That keeps it usable from both the bot and the auto-generated standalone
script.
"""
from __future__ import annotations

import asyncio
import random
import re
from typing import Any


# QWERTY adjacency map for realistic typo generation.
# Each key maps to keys reachable by a one-cell finger slip.
_ADJ = {
    "q": "wa",  "w": "qase", "e": "wsdr", "r": "edft", "t": "rfgy",
    "y": "tghu", "u": "yhji", "i": "ujko", "o": "iklp", "p": "ol",
    "a": "qwsz", "s": "awedxz", "d": "serfcx", "f": "drtgvc",
    "g": "ftyhbv", "h": "gyujnb", "j": "hujkmn", "k": "jiolm,",
    "l": "kop;.", "z": "asx", "x": "zsdc", "c": "xdfv", "v": "cfgb",
    "b": "vghn", "n": "bhjm", "m": "njk,",
}


_CODE_LIKE = re.compile(r"^[0-9\s\-+().]+$")
_EMAIL_LIKE = re.compile(r"@.+\.")
_URL_LIKE = re.compile(r"https?://|www\.")


def _is_sensitive_text(text: str) -> bool:
    """Skip typo simulation for codes, emails, urls, phone numbers."""
    if not text:
        return True
    if _CODE_LIKE.match(text):
        return True
    if _EMAIL_LIKE.search(text):
        return True
    if _URL_LIKE.search(text):
        return True
    return False


def _adjacent_typo(ch: str) -> str | None:
    """Return a plausible mistyped neighbour for ``ch``, or None."""
    if not ch or not ch.isalpha():
        return None
    low = ch.lower()
    neighbours = _ADJ.get(low)
    if not neighbours:
        return None
    typo = random.choice(neighbours)
    return typo.upper() if ch.isupper() else typo


async def human_type(
    page: Any,
    text: str,
    typo_rate: float = 0.0,
) -> None:
    """Type ``text`` into the focused element with human-like cadence.

    Args:
        page: A Playwright/Camoufox page (anything with ``page.keyboard``).
        text: The text to type. May contain any unicode (Arabic supported).
        typo_rate: Probability per character of injecting a typo + correction.
            0.0 disables typos. Auto-overridden to 0 for sensitive inputs
            (codes, emails, urls).
    """
    if not text:
        return

    # Disable typos for sensitive content even if caller asked for them.
    if _is_sensitive_text(text):
        typo_rate = 0.0

    # 1) Orientation pause — humans don't start typing instantly.
    await asyncio.sleep(random.uniform(0.18, 0.45))

    burst_left = 0   # remaining chars in a fast burst
    last_was_space = False

    for i, ch in enumerate(text):
        # ─── Typo injection ────────────────────────────────────────
        if (
            typo_rate > 0
            and burst_left == 0
            and random.random() < typo_rate
            and i > 0          # never typo the very first char
        ):
            typo = _adjacent_typo(ch)
            if typo:
                # Type the wrong key.
                await page.keyboard.type(typo, delay=0)
                # Brief delay — human realises the mistake.
                await asyncio.sleep(random.uniform(0.10, 0.30))
                # Sometimes a small "noticing" pause.
                if random.random() < 0.4:
                    await asyncio.sleep(random.uniform(0.15, 0.45))
                # Backspace.
                await page.keyboard.press("Backspace")
                await asyncio.sleep(random.uniform(0.08, 0.18))
                # Now type the correct character below.

        # ─── Send the real keystroke ──────────────────────────────
        await page.keyboard.type(ch, delay=0)

        # ─── Compute the inter-key delay ───────────────────────────
        if burst_left > 0:
            burst_left -= 1
            d = random.uniform(0.030, 0.075)
        else:
            # Base distribution by character class.
            if ch == " ":
                d = random.uniform(0.10, 0.22)
            elif ch in ".,!?;:":
                d = random.uniform(0.14, 0.32)
            elif ch in "\n\t":
                d = random.uniform(0.20, 0.40)
            elif ch.isdigit():
                d = random.uniform(0.07, 0.16)
            elif ch.isupper():
                d = random.uniform(0.10, 0.22)  # shift adds time
            else:
                # Lognormal-ish: most keys 60-150ms, occasional slower.
                base = random.lognormvariate(mu=-2.35, sigma=0.40)
                d = max(0.04, min(0.30, base))

            # Boost speed slightly right after a space (start-of-word burst).
            if last_was_space and random.random() < 0.35:
                burst_left = random.randint(1, 3)

            # Occasional thinking pause (~3.5%).
            r = random.random()
            if r < 0.035:
                d += random.uniform(0.30, 0.90)
            # Or a smaller hesitation (~12%).
            elif r < 0.155:
                d += random.uniform(0.05, 0.14)

        last_was_space = (ch == " ")
        await asyncio.sleep(d)

    # 2) Settle pause after the last character.
    await asyncio.sleep(random.uniform(0.05, 0.18))
