"""Configuration dataclass and JSON load/save."""
from __future__ import annotations
import json
from dataclasses import dataclass, asdict
from pathlib import Path

DEFAULT_CONFIG_PATH = Path("config.json")


@dataclass
class Config:
    window_title: str = "Forza Horizon 6"
    resolution: tuple = (1920, 1080)
    match_threshold: float = 0.80
    # lime UI colour in HSV (OpenCV: H 0-179, S/V 0-255). The default window
    # is wide enough to catch both the native lime banner (H~42) and the
    # yellow-shifted variant Windows HDR produces (H~30).
    lime_hsv_lower: tuple = (25, 110, 110)
    lime_hsv_upper: tuple = (55, 255, 255)
    # Wider fallback for aggressive HDR setups that shift further than the
    # default window covers. Enabled by `hdr_mode`.
    hdr_lime_hsv_lower: tuple = (18, 110, 110)
    hdr_lime_hsv_upper: tuple = (60, 255, 255)
    hdr_mode: bool = False
    # key timing in ms (min, max), randomised per press. Moderate - fast
    # enough to be snappy, slow enough that FH6 doesn't drop keys mid-burst
    # (dropped keys during navigation are what made the Max Bid hop land on
    # the wrong field). Don't push these much lower.
    key_hold_ms: tuple = (18, 38)
    between_keys_ms: tuple = (18, 42)
    poll_interval_ms: tuple = (35, 75)
    # extra ms between selecting Buy Out (Down) and confirming (Enter).
    # bump if the bot occasionally opens Place Bid instead of Buy Out -
    # usually means FH6 didn't register the Down before Enter arrived.
    buyout_select_delay_ms: int = 0
    # Re-roll the Max Bid filter on the Search screen before every search.
    # FH6 caches results for an identical query, so newly-listed cars don't
    # appear until you change the query. Nudging Max Bid each loop forces a
    # fresh server query, so fresh listings surface far faster (the single
    # biggest factor in snipe rate). Set a mid Max Bid (~40,000,000) once;
    # the bot oscillates it +/- one step each search to stay in your range.
    cycle_max_bid: bool = True
    # Closed-loop Max Bid navigation (default). The selected field row is drawn
    # with a lime OUTLINE box; the bot reads that box's Y to know which row the
    # cursor is on, then steps straight to Max Bid, re-checking after every
    # press. A dropped key just costs one extra press - it can never land on the
    # wrong field. Far faster than the old run-to-the-top-and-count-down hop
    # (no trip to the top, only the few presses actually needed) and immune to
    # the off-by-one corruption blind counting suffered. Set False to fall back
    # to the blind method below.
    max_bid_closed_loop: bool = True
    # Max Bid row is targeted RELATIVE to the lime title bar, not at a fixed Y -
    # the form renders at different heights on different setups, so a hardcoded
    # Y can land on the wrong row. This is the px gap from the title centre down
    # to the Max Bid row centre at 1920x1080 (see vision.TITLE_TO_MAX_BID_DY).
    max_bid_title_dy: int = 279
    # How close (px) the detected selection box must be to the computed target
    # to count as "on Max Bid". Half the ~53px row pitch, so rows map cleanly.
    max_bid_row_tol: int = 26
    # Pause (ms) after each navigation press and between confirm reads, so the
    # cursor and the form's open animation are settled before the next read.
    # Without it the bot reads mid-animation and stops on the wrong row.
    max_bid_settle_ms: int = 70
    # Max presses to walk the cursor onto Max Bid before giving up and skipping
    # the nudge for this loop (skipping is safe - re-searching still refreshes).
    max_bid_nav_attempts: int = 12
    # Blind fallback (used only when max_bid_closed_loop is False): spam Up to
    # the top of the form, then step Down a fixed count. Search layout top-down:
    # Make, Model, Performance Class, Car Type, Max Bid -> 4 Downs.
    max_bid_top_presses: int = 7
    max_bid_row_from_top: int = 4
    # Settle so the freshly-loaded Search screen is input-ready before the first
    # key. Only used by the blind fallback - the closed-loop path re-detects
    # instead of waiting, so it needs no settle.
    search_ready_delay_ms: int = 250
    # Left/Right presses to change the Max Bid value per search.
    max_bid_steps: int = 1
    # Whether moving background is enabled in FH6 video settings. Picks
    # which buy_out template set to load - keeping the other set unused
    # saves a couple of full-res template matches per buyout poll.
    moving_background: bool = True
    # timeouts in seconds. timeout_results_s is also hard-capped at 8s in code
    # so an unrecognised post-search screen (e.g. the single-listing expanded
    # Auction Details view) can't hang the loop for 25s like it used to.
    timeout_results_s: float = 8.0
    timeout_outcome_s: float = 25.0
    timeout_claim_s: float = 20.0
    timeout_generic_s: float = 10.0
    loop_pace_s: float = 0.05
    # auto-stop
    auto_stop_enabled: bool = True
    max_cars: int = 1
    max_minutes: float = 180.0
    # behaviour
    collect_after_buyout: bool = True
    notify_sound: bool = True
    notify_toast: bool = True
    # When False the overlay window is hidden from screen capture
    # (WDA_EXCLUDEFROMCAPTURE) so the bot can't accidentally template-match
    # against its own HUD. Set True if you want to screenshot or stream the
    # overlay.
    overlay_capturable: bool = False
    # paths
    log_path: str = "logs/purchases.csv"
    template_dir: str = "templates"
    # global hotkeys (pynput format)
    hotkey_start_stop: str = "<f8>"
    hotkey_panic: str = "<f9>"
    hotkey_sp_grind: str = "<f7>"
    win32_api_input: bool = False

    # --- Skill-point grind (separate mode, own hotkey/button) ---------------
    # Repeats: hold gas through the race, press Restart, wait for the next race
    # to start, repeat - to farm a short "SP Farm" custom route. Independent of
    # the auction sniper; only one mode runs at a time.
    # Key that accelerates the car (held during the race). On the ROG Ally
    # keyboard this is "w". Must be one of actions.KEY_MAP.
    gas_key: str = "w"
    # The grind is VISION-DRIVEN, not on a timer: it holds gas until it sees the
    # race results screen (so it can't desync from the race length), then
    # presses Restart until that screen actually clears. sp_race_hold_s is just
    # the SAFETY CAP on how long to hold gas while waiting for the finish.
    sp_race_hold_s: float = 45.0
    # Match confidence (0-1) for recognising the results screen (the
    # "A Continue / X Restart" prompt bar). 1.0 on a clean match in testing.
    sp_results_threshold: float = 0.70
    # Pause after the results screen appears before pressing Restart.
    sp_restart_settle_s: float = 0.8
    # Reset / restart key on the results screen (X). Must be in actions.KEY_MAP.
    sp_restart_key: str = "x"
    # After pressing Restart the game shows a "Restart Event" Yes/No dialog with
    # Yes already highlighted. The grind confirms it by pressing this key. Match
    # confidence for recognising that dialog (0.90-1.00 on a real match; every
    # other grind screen scores <=0.54, so 0.70 separates cleanly).
    sp_confirm_key: str = "enter"
    sp_restart_confirm_threshold: float = 0.70
    # Press Restart up to this many times, each waiting sp_reset_timeout_s for
    # the pre-race "Start Race Event" menu to appear, before giving up for this
    # lap. (Reset is confirmed by the menu showing, not just results clearing.)
    sp_reset_attempts: int = 4
    sp_reset_timeout_s: float = 5.0
    # Key that launches the race from the start menu (Enter selects the already-
    # highlighted "Start Race Event"). Set blank ("") to skip if your route
    # restarts straight into the countdown.
    sp_start_key: str = "enter"
    # Match confidence for the start-race menu, and how many times to press the
    # start key (each waiting sp_start_timeout_s for the menu to disappear =
    # race launching) before giving up for this lap.
    sp_start_threshold: float = 0.70
    sp_start_attempts: int = 4
    sp_start_timeout_s: float = 5.0
    # Pause after each menu action (press X / Enter) before re-reading the
    # screen, so the bot acts on a settled frame rather than mid-transition.
    sp_loop_settle_s: float = 0.4
    # Stop after this many laps (or stop manually with the grind hotkey/button).
    sp_max_iterations: int = 100

    def effective_lime_bounds(self) -> tuple:
        """Return the (lower, upper) HSV bounds to use right now."""
        if self.hdr_mode:
            return self.hdr_lime_hsv_lower, self.hdr_lime_hsv_upper
        return self.lime_hsv_lower, self.lime_hsv_upper


_TUPLE_FIELDS = {
    name for name, f in Config.__dataclass_fields__.items()
    if isinstance(f.default, tuple)
}


def load_config(path=DEFAULT_CONFIG_PATH) -> Config:
    path = Path(path)
    if not path.exists():
        cfg = Config()
        save_config(cfg, path)
        return cfg
    data = json.loads(path.read_text(encoding="utf-8"))
    for key in _TUPLE_FIELDS:
        if key in data and isinstance(data[key], list):
            data[key] = tuple(data[key])
    known = set(Config.__dataclass_fields__)
    cfg = Config(**{k: v for k, v in data.items() if k in known})
    # Preserve any extra keys as attributes on cfg. Lets a private config.json
    # carry dev / power-user flags (e.g. overlay_capturable) without those
    # keys ever appearing in a freshly auto-generated config.
    for key, value in data.items():
        if key not in known:
            setattr(cfg, key, value)
    if not known.issubset(data.keys()):
        save_config(cfg, path)          # backfill any missing fields
    return cfg


def save_config(cfg: Config, path=DEFAULT_CONFIG_PATH) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = asdict(cfg)
    declared = set(Config.__dataclass_fields__)
    for key, value in cfg.__dict__.items():           # round-trip extras
        if key not in declared:
            data[key] = value
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
