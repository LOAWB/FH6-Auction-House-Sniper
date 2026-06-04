"""Skill-point grinder: a separate mode from the auction sniper.

Repeats a short custom "SP Farm" race to bank skill points: hold the
accelerator through the race, press Restart on the results screen, wait for the
reload + countdown, then hold again - up to sp_max_iterations laps or until
stopped. Deliberately simple and time-based (the route is a fixed-length race),
with all timings in config so they can be tuned without a rebuild.
"""
from __future__ import annotations
import logging
import time
from . import actions, capture

log = logging.getLogger("fh6.grind")


class SkillGrinder:
    """Drives the hold-gas / restart loop. One instance per run."""

    def __init__(self, cfg, clock=time.monotonic, sleeper=time.sleep,
                 on_status=None, on_lap=None):
        self.cfg = cfg
        self.clock = clock
        self.sleeper = sleeper
        self.on_status = on_status
        self.on_lap = on_lap
        self._stop = False
        self.laps = 0

    def request_stop(self) -> None:
        self._stop = True

    def _status(self, text: str) -> None:
        log.info("[grind] %s", text)
        if self.on_status:
            self.on_status(text)

    def _focused(self) -> bool:
        if self.cfg.win32_api_input:
            return True
        return capture.is_game_focused(self.cfg.window_title)

    def _interruptible_sleep(self, seconds: float) -> bool:
        """Sleep in small slices so a stop request is honoured promptly.
        Returns False if stopped during the wait."""
        deadline = self.clock() + seconds
        while self.clock() < deadline:
            if self._stop:
                return False
            self.sleeper(0.05)
        return not self._stop

    def _hold_gas(self, seconds: float) -> bool:
        """Hold the accelerator for `seconds`, releasing early on stop. Always
        releases the key, even on exception, so the throttle never sticks."""
        key = self.cfg.gas_key
        win32 = self.cfg.win32_api_input
        actions.key_down(key, use_win32=win32)
        try:
            ok = self._interruptible_sleep(seconds)
        finally:
            actions.key_up(key, use_win32=win32)
        return ok

    def _press(self, name: str) -> None:
        actions.tap_key(name, 1, self.cfg.key_hold_ms, self.cfg.between_keys_ms,
                        use_win32=self.cfg.win32_api_input)

    def run(self) -> str:
        """Loop the grind. Returns: stopped | done."""
        cfg = self.cfg
        total = cfg.sp_max_iterations
        log.info("=== skill grind started (%d laps, gas=%s) ===",
                 total, cfg.gas_key)
        if not self._focused():
            self._status("Paused: FH6 not focused")
            while not self._focused():
                if self._stop:
                    self._status("Skill grind stopped")
                    return "stopped"
                self.sleeper(0.5)
        for i in range(total):
            if self._stop:
                break
            # Hold gas through the race (it finishes mid-hold).
            self._status(f"Skill grind {i + 1}/{total}: holding gas")
            if not self._hold_gas(cfg.sp_race_hold_s):
                break
            if self._stop:
                break
            self.laps = i + 1                               # this race is done
            if self.on_lap:
                self.on_lap(self.laps, total)
            if i + 1 >= total:
                break                                       # last lap, no restart
            # Reset (X) on the results screen, then start the race event
            # (Enter), then wait for the reload + 3-2-1 countdown.
            self._status(f"Skill grind {i + 1}/{total} done: restarting")
            if not self._interruptible_sleep(cfg.sp_restart_settle_s):
                break
            self._press(cfg.sp_restart_key)                 # reset
            if cfg.sp_start_key:                            # start race event
                if not self._interruptible_sleep(cfg.sp_confirm_delay_s):
                    break
                self._press(cfg.sp_start_key)
            if not self._interruptible_sleep(cfg.sp_start_delay_s):
                break
        if self._stop:
            self._status(f"Skill grind stopped ({self.laps} laps)")
            return "stopped"
        self._status(f"Skill grind done ({self.laps} laps)")
        return "done"
