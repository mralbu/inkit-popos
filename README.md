# inkit-popos

Voice dictation for **Pop!_OS / COSMIC (Wayland)** — type with your voice into
any application, with your words landing at the cursor.

Inspired by Cartesia's macOS [InkIt](https://github.com/cartesia-ai/InkIt), but
built for Linux/Wayland and **backend-agnostic**: use the **Cartesia Ink** cloud
API *or* a fully local **NVIDIA Parakeet** model — switch with one config line.

> Status: working MVP daemon. Hotkey-triggered record → transcribe → type at
> cursor. Tray UI and dictation history are on the roadmap.

## How it works

```
 hotkey / CLI ─▶ daemon ─▶ record (PipeWire)
                              │
                              ▼
                  STT engine: Cartesia API  │  local Parakeet (sherpa-onnx)
                              │
                              ▼
                   optional LLM "polish" (filler/punctuation cleanup)
                              │
                              ▼
              type at cursor: wtype │ ydotool │ clipboard paste
```

The daemon listens on a Unix socket. A small CLI command (`inkit-popos toggle`),
bound to a COSMIC keyboard shortcut, starts/stops dictation. On stop, the audio
is transcribed and typed into whatever window has focus.

### Why these choices on Wayland

Wayland sandboxes global hotkeys and synthetic input, so the macOS approach
doesn't port directly:

- **Hotkey:** COSMIC doesn't yet implement the `GlobalShortcuts` xdg-portal
  ([pop-os/xdg-desktop-portal-cosmic#4](https://github.com/pop-os/xdg-desktop-portal-cosmic/issues/4)),
  so we bind a COSMIC custom shortcut to `inkit-popos toggle`. (True
  press-and-hold via evdev is on the roadmap.)
- **Typing at the cursor:** tried in order — `wtype` (virtual-keyboard
  protocol), `ydotool` (kernel uinput, compositor-agnostic), then clipboard
  paste as a fallback.

## Install

Requires Python 3.9+ and PipeWire/PulseAudio.

```bash
# system dependencies (Pop!_OS / Ubuntu)
sudo apt install python3-pip libportaudio2 wtype ydotool wl-clipboard libnotify-bin

# the app — pick the engine extra(s) you want
pip install --user -e '.[parakeet]'   # local model
pip install --user -e '.[cartesia]'   # cloud API
pip install --user -e '.[all]'        # both
```

Make sure `~/.local/bin` is on your `PATH`. Then scaffold a config and check
your setup:

```bash
inkit-popos init
inkit-popos doctor
```

## Choose an engine

Edit `~/.config/inkit-popos/config.toml` and set `engine = "parakeet"` or
`engine = "cartesia"`.

### Local Parakeet (offline, no API key)

Runs on CPU at ~30× real-time via [sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx).

```bash
scripts/download-parakeet.sh        # downloads to the default model_dir
inkit-popos doctor                  # confirm the model is found
```

### Cartesia Ink (cloud)

Grab a free API key at <https://cartesia.ai> (~15k words/month), then:

```bash
export CARTESIA_API_KEY=sk_car_...   # or set cartesia.api_key in the config
```

## Bind the hotkey (COSMIC)

1. Start the daemon (and have it autostart — see below).
2. **Settings → Keyboard → Custom Shortcuts → Add**
3. Command: `inkit-popos toggle` — assign a key (e.g. `Super+Z`).

Press it once to start listening, press again to stop and type the result.

## Run as a service

Autostart the daemon on login with the bundled user unit:

```bash
mkdir -p ~/.config/systemd/user
cp data/inkit-popos.service ~/.config/systemd/user/
systemctl --user enable --now inkit-popos.service
```

`ydotool` injection also needs its daemon running:

```bash
systemctl --user enable --now ydotoold   # or run `ydotoold` manually
# may require your user in the 'input' group / udev access to /dev/uinput
```

## Usage

```bash
inkit-popos daemon       # run the background service (foreground)
inkit-popos toggle       # start/stop dictation (bind to a hotkey)
inkit-popos status       # idle | recording | processing
inkit-popos devices      # list microphones
inkit-popos transcribe FILE.mp3   # transcribe a wav/mp3/flac/ogg file (no daemon)
inkit-popos doctor       # diagnose audio / injection / engine setup
```

## Configuration

`~/.config/inkit-popos/config.toml` (created by `inkit-popos init`):

| Key | Purpose |
| --- | --- |
| `engine` | `"parakeet"` or `"cartesia"` |
| `audio.device` | mic name/index (`inkit-popos devices`) |
| `inject.method` | `auto` \| `wtype` \| `ydotool` \| `clipboard` |
| `cartesia.api_key` / `.model` / `.language` | Cartesia settings |
| `parakeet.model_dir` / `.provider` | local model dir, `cpu`/`cuda` |
| `polish.enabled` / `.provider` / `.model` | optional LLM cleanup |

### Polish (optional)

Like InkIt's Polish: strips filler words and fixes punctuation *without*
rewriting. Set `polish.enabled = true` and choose an OpenAI-compatible provider
(OpenAI/Groq/local) or `anthropic`. Uses only the standard library.

## Troubleshooting

- **Nothing types:** run `inkit-popos doctor`. If `wtype` fails on COSMIC, set
  `inject.method = "ydotool"` and ensure `ydotoold` is running, or use
  `"clipboard"`.
- **No audio captured:** check `inkit-popos devices` and set `audio.device`.
- **Parakeet model missing:** re-run `scripts/download-parakeet.sh` and verify
  `parakeet.model_dir`.

## Roadmap

- COSMIC tray + settings UI (libcosmic)
- Searchable dictation history
- True hold-to-talk via evdev
- Streaming transcription (partial results while speaking)

## Credits & license

Inspired by [cartesia-ai/InkIt](https://github.com/cartesia-ai/InkIt). Local STT
via [k2-fsa/sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx) and NVIDIA
Parakeet. Licensed under **Apache-2.0** (see `LICENSE`).
