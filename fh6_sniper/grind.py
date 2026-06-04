"""Skill-point grinder: a separate mode from the auction sniper.

Farms a short custom "SP Farm" race to bank skill points. It is VISION-DRIVEN
and self-healing: every iteration it looks at the screen, decides which single
screen it is on, and takes the one action that screen needs. Because it
re-classifies after every action, it copes with the confirmation screens
appearing in any order and recovers from dropped key presses on its own.

The real reset loop (mapped from capture) is:
    driving -> (race ends) -> results -> press Restart (X)
            -> "Restart Event" Yes/No dialog -> press Confirm (Enter, Yes)
            -> HORIZON FESTIVAL load -> countdown -> driving -> ...
There is no separate "Start Race Event" menu in the restart path, but the grind
still handles that menu (press Enter) so it can also be started cold from there.

Per-screen action map, checked every loop:
    results          -> press Restart (X)         [opens the confirm dialog]
    restart_confirm  -> press Confirm (Enter)     [Yes -> relaunch]
    start_menu       -> press Start (Enter)        [cold-start launch]
    driving/loading  -> hold gas until the screen changes to a menu

A lap is counted only when a race we were actually driving reaches the results
screen, and the grind stops at sp_max_iterations laps WITHOUT kicking off
another restart. Timings are only safety caps; nothing is on a blind timer.
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
        self._results_tmpl = self._load_template("sp_results.png")
        self._start_tmpl = self._load_template("sp_start.png")
        self._restart_tmpl = self._load_template("sp_restart_confirm.png")

    def _load_template(self, name):
        path = paths.app_dir() / self.cfg.template_dir / name
        img = cv2.imread(str(path))
        if img is None:
            log.warning("grind: template missing (%s)", path)
        return img

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

    def _grab(self):
        return capture.grab_screen(self.cfg.window_title)

    def _classify(self, frame) -> str:
        """Identify the current grind screen from a single frame.

        Returns one of: 'restart_confirm', 'results', 'start_menu', 'driving'.
        Order matters: the restart-confirm dialog is checked FIRST because a
        blurred copy of the results leaderboard header sits behind it (it scores
        ~0.54 on the results template, below threshold, but checking confirm
        first removes any ambiguity). Anything we don't recognise is treated as
        'driving' (also covers loading and the countdown) so we hold the gas."""
        cfg = self.cfg
        if vision.is_sp_restart_confirm(
                frame, self._restart_tmpl, cfg.sp_restart_confirm_threshold):
            return "restart_confirm"
        if vision.is_sp_results(
                frame, self._results_tmpl, cfg.sp_results_threshold):
            return "results"
        if vision.is_sp_start_menu(
                frame, self._start_tmpl, cfg.sp_start_threshold):
            return "start_menu"
        return "driving"

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

    def _hold_gas_until_change(self, max_s: float) -> str:
        """Hold the accelerator until the screen stops being 'driving' (a menu
        appears - normally the results screen when the race finishes) or max_s
        elapses. Always releases the key, even on stop or exception, so the
        throttle never sticks.
        Returns 'changed' | 'timeout' | 'stop'."""
        key = self.cfg.gas_key
        win32 = self.cfg.win32_api_input
        actions.key_down(key, use_win32=win32)
        try:
            deadline = self.clock() + max_s
            while self.clock() < deadline:
                if self._stop:
                    return "stop"
                if self._classify(self._grab()) != "driving":
                    return "changed"
                self.sleeper(0.15)
            return "timeout"
        finally:
            actions.key_up(key, use_win32=win32)

    def _wait_for_focus(self) -> bool:
        """Block until FH6 is focused. Returns False if stopped while waiting."""
        if self._focused():
            return True
        self._status("Paused: FH6 not focused")
        while not self._focused():
            if self._stop:
                return False
            self.sleeper(0.5)
        return True

    def run(self) -> str:
        """Loop the per-screen action map until sp_max_iterations laps or a stop
        request. Startable from ANY screen. Returns 'stopped' | 'done'."""
        cfg = self.cfg
        total = cfg.sp_max_iterations
        vision_ok = (self._results_tmpl is not None
                     and self._restart_tmpl is not None
                     and self._start_tmpl is not None)
        log.info("=== skill grind started (%d laps, gas=%s, vision=%s) ===",
                 total, cfg.gas_key, vision_ok)
        was_driving = False
        while self.laps < total:
            if self._stop:
                break
            if not self._wait_for_focus():
                break
            screen = self._classify(self._grab())

            if screen == "results":
                # A race we were driving just finished -> count the lap. Then
                # restart, unless we have hit the lap target (stop on results,
                # don't kick off another race).
                if was_driving:
                    self.laps += 1
                    was_driving = False
                    if self.on_lap:
                        self.on_lap(self.laps, total)
                    if self.laps >= total:
                        break
                self._status(f"Skill grind {self.laps}/{total}: "
                             "race finished, restarting")
                if not self._interruptible_sleep(cfg.sp_restart_settle_s):
                    break
                self._press(cfg.sp_restart_key)        # X -> confirm dialog

            elif screen == "restart_confirm":
                self._status(f"Skill grind {self.laps}/{total}: "
                             "confirming restart")
                self._press(cfg.sp_confirm_key)        # Enter -> Yes

            elif screen == "start_menu":
                self._status(f"Skill grind {self.laps}/{total}: starting race")
                self._press(cfg.sp_start_key)          # Enter -> launch

            else:                                       # driving/loading/count
                was_driving = True
                self._status(f"Skill grind {self.laps + 1}/{total}: "
                             "holding gas")
                outcome = self._hold_gas_until_change(cfg.sp_race_hold_s)
                if outcome == "stop":
                    break
                if outcome == "timeout":
                    self._status(f"Skill grind {self.laps + 1}/{total}: "
                                 "no finish yet, watching")
                    log.info("grind: gas-hold cap hit without a screen change")
                continue            # re-classify immediately, no extra settle

            if not self._interruptible_sleep(cfg.sp_loop_settle_s):
                break

        if self._stop:
            self._status(f"Skill grind stopped ({self.laps} laps)")
            return "stopped"
        self._status(f"Skill grind done ({self.laps} laps)")
        return "done"
