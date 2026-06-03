# Changelog

Newest changes first. Each section header is the release date.

## fork - 2026-06-03d (LOAWB) - Max Bid reliability over long runs

Fix the bug where, after running a while, the bot would nudge the wrong filter
and stop finding cars. Cause: the lean "Up 2 from Confirm" hop assumed a known
cursor position, but the first keypress after the Search screen loads often
gets dropped by load lag - so Up 2 became Up 1, landing on the wrong row and
changing the wrong filter (e.g. Make/Model), corrupting the search.

Fix: reach Max Bid from the TOP of the form again (spam Up with margin - the
cursor can't overshoot the top, so a dropped first Up is harmless), after a
short settle so the screen is input-ready. Then navigate down to Confirm and
submit. Also backed the key timing off the over-aggressive values that were
contributing to dropped keys. Tunable: max_bid_top_presses, max_bid_row_from_top,
search_ready_delay_ms.

## fork - 2026-06-03b (LOAWB) - speed + hang fix

### Faster loop (no more landing-menu round-trip)
Between empty searches the bot used to ESC all the way out to the Auction
House landing menu and re-open Search every loop (~1.7s wasted/loop). It now
ESCs back to the Search screen and re-searches in place. Plus tighter key/poll
timing defaults and a faster loop pace. Net: roughly half the per-loop time.

### Fix: 25s hang on the expanded single-listing view
When a search surfaced the expanded "Auction Details" view it scored under
threshold and the bot sat in the 25s results timeout. Capped that wait at 8s
(and lowered the default) so it re-searches quickly instead of hanging.

Note: timing defaults only apply to a fresh config.json. Delete your existing
config.json (next to the exe) to pick them up, or edit the values by hand.

## fork - 2026-06-03 (LOAWB)

### Fix: buy-out dialog not detected on some builds (the bot wouldn't press the final buy)
The bundled buy-out template only matched the old wide-band confirm dialog. On
builds that render the newer compact "Buy Out" modal (green header + Yes/No),
the full-resolution match never cleared threshold, so the bot opened the dialog
but never recognised it and never pressed Yes. Re-cut `buy_out.png` /
`buy_out_bgoff.png` from the new modal; verified NCC 1.00 and 0.96-0.99 with a
different car behind the glass. Everything downstream (success, claim) already
matched, so only the buy-out template changed.

### New: Max Bid re-roll for faster listings
FH6 caches search results for an identical query, so freshly-listed cars don't
show until the query changes. The bot now nudges the Max Bid filter by one step
before every search (oscillating to stay in range), forcing a fresh server
query so new cars surface far faster. Toggle `cycle_max_bid` in config; tune
`max_bid_row_index` / `max_bid_steps` if your Search layout differs. Set a mid
Max Bid (~40,000,000) once and let it oscillate.

### New: auto-built Windows exe
Pushes build a ready-to-run bundle on GitHub Actions, published to Releases.

## v1.2.0 - 2026-05-28

### Run the bot while doing something else (contributed by @LennardDenby)
New **Win32 API input** toggle in Settings. With it on, the bot keeps buying cars even when FH6 isn't your active window. Alt-tab to a browser, watch YouTube, whatever. FH6 still needs to be running and not minimised. Off by default.

### Fewer self-changing settings
If you noticed your Moving Background toggle resetting to a different value on its own, that's fixed. The bot now double-checks before changing it.

## v1.1.3 - 2026-05-28

### Fix: bot was wrongly skipping cars as "all sold"
The lime "Auction Details" banner renders a frame or two before FH6 actually draws the car cards underneath it. The bot was checking the slots on that earlier frame, finding nothing rendered yet, and reporting "All listings sold, skipping" - so legitimate cars were being skipped without an attempt. The bot now waits for at least one card body to be visible before deciding what's buyable. This also stops the auto-toggle from ping-ponging the moving-background flag, since the buy-out dialog rendering race was a downstream symptom of the same root cause.

## v1.1.2 - 2026-05-27

### Clearer error when the bot can't see the game
If the bot starts and can't identify any FH6 menu screens (most often because the game language isn't English), the status now reads **"Set game language to English"** instead of the vague "could not recover".

### Better diagnostic logs
The full config is now logged at session start, and any setting changes made from the Settings tab get logged with old → new values. Useful when sharing `sniper.log` for troubleshooting.

## v1.1.1 - 2026-05-27

### Sold-listing detection fix
The bot was occasionally still trying to buy listings that had just sold - it would land on the View Seller / View Highest Bidder menu before backing out, wasting a cycle. Root cause: with moving background on, the bright FH6 menu scene showing through empty slots was being mistaken for a card. Detection now looks for the pure-white card UI body specifically, which the game's background scene never produces. The bot will correctly skip sold listings instead of stumbling into the wrong menu.

### Auto-fix for wrong Moving background flag
If your in-game **Moving background** setting doesn't match the **Moving background mode** toggle in the bot's Settings, the bot will now spot the mismatch on the first buyout attempt (about a second in), flip its own toggle to match, save the new value, and carry on. Costs one missed sale, then the bot runs as if the flag had been correct from the start.

## v1.1.0 - 2026-05-26

### Settings panel
New **Settings** tab in the overlay. Edit match sensitivity, loop speed, auto-stop limits, notifications, hotkeys, HDR mode, moving background, and overlay visibility in screenshots / recordings. Saves and applies live.

### Resolution & monitor support
- 1080p, 1440p, 4K: all work.
- Ultrawide / 16:10 / 4:3: run FH6 windowed at 1920×1080. Black bars get cropped automatically.

### HDR
HDR was shifting FH6's lime UI toward yellow and breaking color detection. Fixed. Extra **HDR mode** toggle in Settings for displays that shift even more.

### Slow-load fix
Was reporting "no cars" when the Auction House just hadn't finished loading yet. Now recognizes the loading screen and waits.

### Polish
- Tabbed Status / Settings layout
- Collapsible Settings sections, scrolls if your screen is short
- Faster captures at high resolutions

### Logs
Cleaner state names, including the new loading state.
