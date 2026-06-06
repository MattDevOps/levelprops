"""Desktop notifications with de-duplication.

Uses `notify-send` (libnotify) on Linux -- already present on GNOME/Fedora --
and falls back to a terminal bell + stderr line anywhere else. De-dups so the
same setup doesn't re-fire every poll: a key is remembered and only re-alerted
after it clears or after a cooldown number of ticks.
"""
import shutil
import subprocess
import sys

_HAS_NOTIFY = shutil.which("notify-send") is not None


def desktop(title: str, body: str, critical: bool = False) -> None:
    if _HAS_NOTIFY:
        urgency = "critical" if critical else "normal"
        subprocess.run(["notify-send", title, body, "--app-name=levelprobs",
                        f"--urgency={urgency}"], check=False)
    else:
        sys.stderr.write(f"\a[ALERT] {title} -- {body}\n")
        sys.stderr.flush()


class Deduper:
    """Suppress repeat alerts for the same key until it clears / cools down."""

    def __init__(self, cooldown_ticks: int = 12):
        self.cooldown = cooldown_ticks
        self._seen = {}   # key -> ticks since last fired

    def should_fire(self, key) -> bool:
        for k in list(self._seen):
            self._seen[k] += 1
            if self._seen[k] > self.cooldown:
                del self._seen[k]
        if key in self._seen:
            return False
        self._seen[key] = 0
        return True

    def clear(self, active_keys) -> None:
        """Forget keys no longer active so they can fire fresh next time."""
        active = set(active_keys)
        for k in list(self._seen):
            if k not in active:
                del self._seen[k]
