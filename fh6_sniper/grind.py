"""Skill-point grinder: a separate mode from the auction sniper.

Farms a short custom "SP Farm" race to bank skill points. It is VISION-DRIVEN,
not on a timer, so it can't desync from the race: it holds the accelerator
until it sees the results screen (race finished), presses Restart until that
screen actually clears, presses Start to relaunch the race, then repeats - up
to sp_max_iterations laps or until stopped. Timings are only safety caps.
"""
from __future__ import annotations
import logging
import time
import cv2
from . import actions, capture, paths, vision

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
        self._results_tmpl = self._load_results_template()
        self._start_tmpl = self._load_template("sp_start.png")

    def _load_template(self, name):
        path = paths.app_dir() / self.cfg.template_dir / name
        img = cv2.imread(str(path))
        if img is None:
            log.warning("grind: template missing (%s)", path)
        return img

    def _load_results_template(self):
        return self._load_template("sp_results.png")

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

    def _on_results(self) -> bool:
        """True if the race results / restart screen is currently showing."""
        if self._results_tmpl is None:
            return False
        frame = capture.grab_screen(self.cfg.window_title)
        return vision.is_sp_results(
            frame, self._results_tmpl, self.cfg.sp_results_threshold)

    def _on_start_menu(self) -> bool:
        """True if the pre-race 'Start Race Event' menu is currently showing."""
        if self._start_tmpl is None:
            return False
        frame = capture.grab_screen(self.cfg.window_title)
        return vision.is_sp_start_menu(
            frame, self._start_tmpl, self.cfg.sp_start_threshold)

    def _interruptible_sleep(self, seconds: float) -> bool:
        """Sleep in slices so a stop request is honoured promptly.
        Returns False if stopped."""
        deadline = self.clock() + seconds
        while self.clock() < deadline:
            if self._stop:
                return False
            self.sleeper(0.05)
        return not self._stop

    def _press(self, name: str) -> None:
        if not name:
            return
        actions.tap_key(name, 1, self.cfg.key_hold_ms, self.cfg.between_keys_ms,
                        use_win32=self.cfg.win32_api_input)

    def _hold_gas_until_results(self, max_s: float) -> str:
        """Hold the accelerator until the results screen appears (race
        finished) or max_s elapses. Always releases the key, even on stop or
        exception, so the throttle never sticks.
        Returns 'finished' | 'timeout' | 'stop'."""
        key = self.cfg.gas_key
        win32 = self.cfg.win32_api_input
        actions.key_down(key, use_win32=win32)
        try:
            deadline = self.clock() + max_s
            while self.clock() < deadline:
                if self._stop:
                    return "stop"
                if self._on_results():
                    return "finished"
                self.sleeper(0.15)
            return "timeout"
        finally:
            actions.key_up(key, use_win32=win32)

    def _reset_to_menu(self) -> bool:
        """Press Restart until the pre-race start menu appears (confirming the
        reset actually took and we're ready to launch). Returns True on success.
        Without the menu template we can't verify, so press once and assume."""
        cfg = self.cfg
        if self._start_tmpl is None:
            self._press(cfg.sp_restart_key)
            return True
        for attempt in range(cfg.sp_reset_attempts):
            if self._stop:
                return False
            self._press(cfg.sp_restart_key)
            deadline = self.clock() + cfg.sp_reset_timeout_s
            while self.clock() < deadline:
                if self._stop:
                    return False
                if self._on_start_menu():
                    return True             # on the start menu -> reset took
                self.sleeper(0.2)
            log.info("grind: start menu not up after restart #%d, retrying",
                     attempt + 1)
        return False

    def _start_race(self) -> bool:
        """Press the start key until the start menu disappears (race launching).
        Returns True on success. No menu template -> press once and assume."""
        cfg = self.cfg
        if not cfg.sp_start_key:
            return True
        if self._start_tmpl is None:
            self._press(cfg.sp_start_key)
            return True
        for attempt in range(cfg.sp_start_attempts):
            if self._stop:
                return False
            self._press(cfg.sp_start_key)
            deadline = self.clock() + cfg.sp_start_timeout_s
            while self.clock() < deadline:
                if self._stop:
                    return False
                if not self._on_start_menu():
                    return True             # menu gone -> race is launching
                self.sleeper(0.2)
            log.info("grind: start menu still up after start #%d, retrying",
                     attempt + 1)
        return False

    def run(self) -> str:
        """Loop the grind as a state machine, so it can be started from ANY
        screen (mid-race, on the results screen, or on the start menu) and do
        the right thing. Each iteration it looks at the screen:
          - results screen  -> reset (X) to the start menu, then start (Enter)
          - start menu       -> start the race (Enter)
          - anything else    -> assume driving: hold gas until the race finishes
        A lap is counted only when a race we were driving actually finishes.
        Returns: stopped | done.
        """
        cfg = self.cfg
        total = cfg.sp_max_iterations
        log.info("=== skill grind started (%d laps, gas=%s, vision=%s) ===",
                 total, cfg.gas_key,
                 self._results_tmpl is not None and self._start_tmpl is not None)
        if not self._focused():
            self._status("Paused: FH6 not focused")
            while not self._focused():
                if self._stop:
                    self._status("Skill grind stopped")
                    return "stopped"
                self.sleeper(0.5)
        while self.laps < total:
            if self._stop:
                break
            if self._on_results():
                # On the results screen: reset to the start menu, then launch.
                self._status(f"Skill grind {self.laps}/{total}: restarting")
                if not self._interruptible_sleep(cfg.sp_restart_settle_s):
                    break
                if not self._reset_to_menu():
                    if self._stop:
                        break
                    self._status("Skill grind: restart not confirmed, retrying")
                    continue
                self._status(f"Skill grind {self.laps}/{total}: starting race")
                if not self._start_race():
                    if self._stop:
                        break
                    self._status("Skill grind: start not confirmed, retrying")
                continue
            if self._on_start_menu():
                # On the pre-race menu: just launch the race.
                self._status(f"Skill grind {self.laps}/{total}: starting race")
                if not self._start_race():
                    if self._stop:
                        break
                    self._status("Skill grind: start not confirmed, retrying")
                continue
            # Otherwise we're driving (or loading / counting down): hold gas
            # until the race finishes (the results screen appears).
            self._status(f"Skill grind {self.laps + 1}/{total}: holding gas")
            outcome = self._hold_gas_until_results(cfg.sp_race_hold_s)
            if outcome == "stop":
                break
            if outcome == "timeout":
                self._status(f"Skill grind {self.laps + 1}/{total}: "
                             "no finish yet, watching")
                log.info("grind: gas-hold cap hit without a results screen")
                continue
            self.laps += 1                          # a driven race finished
            if self.on_lap:
                self.on_lap(self.laps, total)
        if self._stop:
            self._status(f"Skill grind stopped ({self.laps} laps)")
            return "stopped"
        self._status(f"Skill grind done ({self.laps} laps)")
        return "done"
