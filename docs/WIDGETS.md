# Own widgets for the XENEON EDGE kiosk

Anyone can make a widget for Quartercore's XENEON EDGE kiosk: a small HTML page
with its own data. Share it in the
[widget store](https://github.com/wwoutt/quartercore-widgets), or install widgets
other people made.

> The format is the same as the custom widgets of the former OpenLinkHub fork
> wwoutt/OpenLinkHub (no longer on GitHub), so those widgets
> work here unchanged. The first time Quartercore starts with this feature, it
> takes over your widgets, their settings and `secrets.json` from
> `~/.config/openlinkhub-widgets/` (once; nothing is changed there).

## Use a widget
1. Open **XENEON EDGE layout** in Quartercore.
2. **Widget store** installs a widget. **Add widget** puts it in the layout; own
   widgets are listed as "(own widget)".
3. Select the widget. If it has settings, such as a server address or a token,
   fill them in on the right and click **Save settings**. They are saved right
   away, separately from the layout.
4. Click **Save** to show the layout on the XENEON EDGE.

Widgets live in `~/.config/Quartercore/widgets/<id>/`. A folder you put there
yourself shows up within a few seconds; an edited widget reloads in the kiosk.

## Make a widget
**Quickest way:** copy the [AI prompt](#ai-prompt) below into an AI assistant,
describe what you want, and save the files it gives you.

**By hand:** create a folder in `~/.config/Quartercore/widgets/` (lowercase
letters, digits, `-` and `_`, at most 64 characters) with:

**`widget.json`**
```json
{
    "name": "My widget",
    "description": "What it shows. Mention every website it contacts.",
    "author": "your name",
    "license": "GPL-3.0-or-later",
    "version": "1.0.0",
    "size": {"w": 4, "h": 4},
    "refresh": 60,
    "source": {"type": "none"}
}
```
- `size`: default size in grid cells (the grid is 24 × 12 on 2560 × 720, one
  cell is about 106 × 60 pixels). The user can resize it, so design for any size.
- `refresh`: seconds between data updates
- `source`: where the data comes from, see [Data sources](#data-sources)
- optional: [`settings`](#settings) and an [`action`](#actions)

**`widget.html`**: what the widget shows. Define `onData` to receive the data:
```html
<style>
    .value { font-size: 48px; color: var(--olh-accent); padding: 14px; }
</style>
<div class="value" id="value">--</div>
<script>
    function onData(data, info) {
        // info: {ok, error, updated}
        document.getElementById('value').textContent = info.ok ? data.value : info.error;
    }
</script>
```
Available: the colours `--olh-text`, `--olh-muted` and `--olh-accent`. The
background is transparent; the kiosk draws the card behind the widget.

### What a widget can and cannot do
The widget runs in a sandboxed iframe in a web view, with a strict Content
Security Policy:

| Can | Cannot |
|---|---|
| Inline `<style>` and `<script>` | Load external scripts, stylesheets or fonts (no CDNs) |
| Images from `data:` or `https://` URLs | `fetch`, `XMLHttpRequest` or WebSockets: data only comes through the source |
| Animations, timers, canvas, SVG | `localStorage`, cookies, popups, forms, navigating away |
| React to touch and clicks | Do anything outside the widget, except through its own [action](#actions) script |

### Data sources

| `source.type` | Use | Settings |
|---|---|---|
| `none` | Only JavaScript (a clock, a countdown) | |
| `url` | Internet: JSON or text from a web address | `url`, optional `headers`, `timeout` (s) |
| `script` | Linux: any program that prints JSON | `command` (default `["python3", "data.py"]`), `timeout` (s) |

**Internet** (`url`): Quartercore fetches the address, so it works for APIs that
browsers block, and API keys stay out of the page. Use `${NAME}` in `url` or
`headers` for a [setting](#settings):
```json
"source": {
    "type": "url",
    "url": "https://api.example.com/data?key=${EXAMPLE_KEY}",
    "headers": {"Authorization": "Bearer ${EXAMPLE_TOKEN}"}
}
```

**Linux** (`script`): runs in the widget folder as your own user, so it can use
your files, commands and desktop session, but never more than you can. It must
print JSON (or text) on stdout within `timeout` seconds. Python is recommended,
any language works. `OLH_SETTINGS_FILE` points to the widget's saved settings
(JSON), `OLH_WIDGET_DIR` to its folder.

### Settings
A widget can ask for settings, such as a server address or an API token. They
show in the layout editor when the widget is selected:
```json
"settings": [
    {"name": "HA_URL", "label": "Server", "type": "url", "default": "http://127.0.0.1:8123"},
    {"name": "HA_TOKEN", "label": "Token", "type": "secret", "help": "Where to find it"}
]
```
- `type`: `text`, `url` (must start with `http://` or `https://`) or `secret`
  (a password field; the value is never shown again, only whether it is set,
  and leaving it empty keeps the stored value).
- The values are kept in `~/.config/Quartercore/widgets/.settings/<id>.json`,
  readable only by you, outside the widget folder, so store updates keep them.
  Removing the widget in the store removes them too.
- Use them as `${NAME}` in a `url` source, or read the file in
  `OLH_SETTINGS_FILE` from a script. Fields that were never saved are missing
  from that file; use their default. Older widgets that read `secrets.json`
  (`OLH_SECRETS_FILE`) keep working.

### Actions
A widget can also *do* something, such as switching a light. Add an action
script to `widget.json`:
```json
"action": {"type": "script", "command": ["python3", "action.py"], "timeout": 15}
```
In `widget.html`, call `olhAction(request)`. It returns a Promise with
`{ok, error, data}`:
```js
olhAction({entity_id: 'light.desk', service: 'toggle'}).then(function (result) { ... });
```
Quartercore runs the script in the widget folder as your user, with the request
as JSON on stdin and `OLH_SETTINGS_FILE` set. The script prints JSON on success,
or writes an error to stderr and exits non-zero. Afterwards the widget's data
refreshes right away.

The request comes from the widget page, so the action script must check it:
allow only the specific things the widget is meant to do (see
[home-assistant/action.py](https://github.com/wwoutt/quartercore-widgets/blob/main/widgets/home-assistant/action.py)),
and never pass the request on to a shell or use it as a command.

## Share your widget
- **Reviewed catalog:** open a pull request that adds your widget folder to
  [wwoutt/quartercore-widgets](https://github.com/wwoutt/quartercore-widgets), see its
  [CONTRIBUTING.md](https://github.com/wwoutt/quartercore-widgets/blob/main/CONTRIBUTING.md).
  It shows up in the **Reviewed** tab after review.
- **Your own repository:** put the widget files (`widget.json`, `widget.html`,
  ...) in the root of a public GitHub repository and add the topic
  [`quartercore-widget`](https://github.com/topics/quartercore-widget). It shows
  up in the **Community** tab right away.

Rules for both: a flat folder, at most 30 files, 512 KB per file and 2 MB in
total; allowed types `.json .html .css .js .py .sh .png .jpg .jpeg .svg .webp
.md .txt`; no secrets in the files (use [settings](#settings)), readable code
only, data scripts that only read data, and action scripts that only allow what
the widget is meant to do.

## The store
**Widget store** in the layout editor shows widgets made by others:
- **Reviewed**: the catalog
  [wwoutt/quartercore-widgets](https://github.com/wwoutt/quartercore-widgets).
  Widgets are reviewed before they are added, and every downloaded file is
  checked against the SHA-256 in its `index.json`.
- **Community (not reviewed)**: public GitHub repositories with the topic
  `quartercore-widget` and the widget files in the repository root. They are
  installed at a fixed commit, so the code you preview is the code you install.

Widgets that run code (a `script` source, an `action`, `.py` or `.sh` files)
show their code first and need an explicit confirmation. Nothing updates by
itself: the store shows "update available" and you choose. Only widgets
installed from the store can be removed there.

Settings in `~/.config/Quartercore/widgets/store.json` (all optional):
```json
{
    "catalog": "https://raw.githubusercontent.com/wwoutt/quartercore-widgets/main/",
    "community": true,
    "topic": "quartercore-widget"
}
```
GitHub allows 60 unauthenticated requests per hour. With many community
widgets, put a personal access token without permissions as `GITHUB_TOKEN` in
`~/.config/Quartercore/widgets/secrets.json`.

## Security
- Each widget is shown in a web view with an off-the-record profile (nothing is
  stored on disk), that may only open Quartercore's own widget pages: no other
  sites, no new windows, no permissions.
- Inside it, `widget.html` runs in a sandboxed iframe without network access;
  Quartercore passes it its data. A broken widget can't affect the rest of the
  kiosk.
- The widget pages come from a server in Quartercore on `127.0.0.1`, on a
  random port, that only answers requests with the secret token of that run.
  Other websites and programs can't read widget data or run widget scripts.
- Scripts run as your user, never as root. Only install widgets you trust.

## AI prompt
Copy everything in the box below into an AI assistant (Claude, ChatGPT, a local
model, ...) and replace the last line with what your widget should do. Always
read what you get back before installing it, especially a `data.py`,
`action.py` or `.sh` script: it runs on your computer as your user.

````text
You are making a custom widget for the XENEON EDGE kiosk of Quartercore
(github.com/wwoutt/quartercore). Follow this specification exactly.

## Output
Give me the complete contents of each file, each in its own code block with the
file name above it. A widget is one flat folder (no subfolders) named with
lowercase letters, digits, "-" and "_" (max 64 characters), for example
"weather-now". It contains:
- widget.json  (required)
- widget.html  (required)
- data.py      (only for a "script" source; another language is allowed, see below)
- action.py    (only when the widget must change something, see "Actions")
Allowed file types: .json .html .css .js .py .sh .png .jpg .jpeg .svg .webp .md .txt.
At most 30 files, 512 KB per file, 2 MB in total. Readable code only: nothing
minified or obfuscated.
After the files, tell me in short: which settings I must fill in (if any), which
websites the widget contacts, and how to install it.

## widget.json
{
    "name": "Human readable name",
    "description": "What it shows. Mention every website it contacts.",
    "author": "<my name or GitHub user>",
    "license": "GPL-3.0-or-later",
    "version": "1.0.0",
    "size": {"w": 4, "h": 4},
    "refresh": 60,
    "source": {"type": "none"}
}
- size: default size in grid cells. The screen is 2560 x 720 pixels and the grid
  is 24 columns x 12 rows, so one cell is about 106 x 60 px. Example: w 4, h 4 is
  about 420 x 235 px. The user can resize the widget, so the layout must adapt to
  any size (use flexbox, percentages, clamp() or container-relative sizes; never
  a fixed width or height in pixels for the whole widget).
- refresh: seconds between data updates (minimum 1). Pick a sensible value for
  the data source and respect API rate limits.
- source: one of
  - {"type": "none"}: no data, everything happens in JavaScript (clock, timer).
  - {"type": "url", "url": "https://...", "headers": {...}, "timeout": 10}:
    Quartercore fetches the URL on the computer and passes the JSON (or text) to
    the widget. headers and timeout (seconds, max 60) are optional.
  - {"type": "script", "command": ["python3", "data.py"], "timeout": 10}:
    Quartercore runs the command in the widget folder and passes what it prints.
    command is optional and defaults to ["python3", "data.py"].
- settings (optional): fields the user fills in after adding the widget, e.g. a
  server address or an API key. Never put such values in the widget files and
  never ask the user to edit a file for them:
    "settings": [
        {"name": "HA_URL", "label": "Server", "type": "url", "default": "http://127.0.0.1:8123"},
        {"name": "HA_TOKEN", "label": "Token", "type": "secret", "help": "Where to find it"}
    ]
  name: letters, digits and "_". type: "text", "url" or "secret" (secrets are
  never sent back to the page). label and help are shown to the user.
  Write ${NAME} in the url or in a header value to use a setting.
  Example: "headers": {"Authorization": "Bearer ${HA_TOKEN}"}.
  Scripts read the saved values from the JSON file in the environment variable
  OLH_SETTINGS_FILE (name -> value); fields that were never saved are missing,
  so fall back to the default. The file may not exist yet.

## widget.html
An HTML fragment (no <html>, <head> or <body> tags) with <style> and <script>.
The kiosk wraps it in a sandboxed iframe with this Content Security Policy:
    default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline';
    img-src data: https:; font-src data:
That means:
- Inline <script> and <style> only. No external scripts, stylesheets or fonts,
  no CDN libraries. Write plain JavaScript (ES2020 is fine).
- NO network access from the widget: fetch, XMLHttpRequest and WebSocket are
  blocked. All data must come through the source in widget.json.
- Images: data: URLs or https:// URLs only.
- No localStorage, cookies, alert(), forms that submit, popups or navigation
  (the iframe sandbox only allows scripts).
- The background is transparent; the kiosk draws the card behind the widget.
  Do not set a background on html or body.

Data arrives in a global function you define:
    function onData(data, info) { ... }
- data: the parsed JSON from the source (or a string when it is not JSON),
  null when there is no data.
- info: {ok: boolean, error: string or null, updated: unix time in seconds}.
- onData is called after the widget loads and again every refresh. Always handle
  info.ok === false (show info.error in a muted color) and a missing or
  unexpected data shape. Use textContent, never innerHTML with data from the
  source.
- For source type "none", start your own timers in the script instead.

Look and feel (dark theme, readable from a distance on a touchscreen):
- Available: the CSS variables --olh-text (#e6e6e6, normal text), --olh-muted
  (#a1a1a1, labels) and --olh-accent (#38bdf8, highlights). The default font is
  system-ui.
- Large, high-contrast text, little clutter, padding of about 12-18 px. Use
  overflow: hidden and text-overflow: ellipsis so long text never breaks the card.

## Actions (only when the widget must change something, e.g. switch a light)
Add to widget.json:
    "action": {"type": "script", "command": ["python3", "action.py"], "timeout": 15}
In widget.html, call olhAction(request) with a JSON-serializable request. It
returns a Promise of {ok: boolean, error: string or null, data: what the script
printed}. Disable the control or show progress until it resolves; the widget's
data refreshes automatically afterwards. Show result.error when ok is false.
action.py gets the request as JSON on stdin and OLH_SETTINGS_FILE in the
environment, prints one JSON value on success, and on failure writes the error
to stderr and exits non-zero. The request comes from the page, so action.py must
validate it against a fixed allowlist of operations and parameter types, and
never pass it to a shell or use it as a command or file path. It may only do
what the widget is meant to do. Python standard library only, like data.py.

## data.py (only for a "script" source)
- Python 3 standard library only (no pip packages), unless I say otherwise.
  Any other language is allowed if you set "command" accordingly, e.g.
  ["sh", "data.sh"].
- Runs as my normal user (never root) on Linux, in the widget folder, with the
  timeout from widget.json. It must print exactly one JSON value on stdout and
  exit. Print errors to stderr and exit with a non-zero code on failure.
- Read-only: it may read files and run commands that only read information.
  It must not change the system, install anything, need sudo, or send personal
  data anywhere. Mention every website it contacts in the description.
- Keep stdout under 1 MB.

## What I want
<describe your widget here, e.g.: "A widget that shows the current temperature
and humidity of my Home Assistant sensor sensor.living_room, refreshing every
30 seconds.">
````

After the AI answers: create the folder `~/.config/Quartercore/widgets/<id>/`,
save the files in it, and add the widget in the layout editor. If something
doesn't show up, start Quartercore from a terminal (`python3 -m quartercore`)
and look for errors about `widget.json` or the script; paste them back to the AI.
