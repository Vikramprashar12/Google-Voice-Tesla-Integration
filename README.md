# Tesla Fleet API CLI

A Python program for authenticating with and sending commands to the Tesla
Fleet API.

## How it's split up

- **Reads** (vehicle list, `vehicle_data`, `wake_up`, region lookup) go
  straight to Tesla's Fleet API.
- **Commands** (lock, honk, climate, charging, etc.) on 2021+ vehicles must be
  cryptographically signed end-to-end. Tesla does not support signing from a
  plain HTTP client, so commands are sent to a locally running
  **`tesla-http-proxy`** (Tesla's official Go binary), which signs them and
  forwards them to the car. This program talks to that proxy for anything
  under `/command/...`.

```
tesla_fleet/
  config.py   # env-driven configuration
  auth.py     # OAuth2 authorization-code flow + token cache/refresh
  api.py      # Fleet API client (direct reads + proxy-signed commands)
  commands.py # catalog of all known vehicle commands
  cli.py      # argparse CLI
tesla_cli.py  # entrypoint: python tesla_cli.py <action> ...
```

## 1. Install dependencies

```bash
pip install -r requirements.txt
```

## 2. Configure

Copy `.env.example` to `.env` and fill in the values from your existing Tesla
Developer app (developer.tesla.com):

```bash
cp .env.example .env
```

- `TESLA_CLIENT_ID` / `TESLA_CLIENT_SECRET` — from your registered app.
- `TESLA_REDIRECT_URI` — must exactly match a redirect URI registered on the
  app. `https://localhost:8585/callback` works well with the built-in login
  helper below (it spins up a throwaway local HTTPS listener to catch the
  code).
- `TESLA_SCOPES` — must be a subset of what your app requested. Needs at
  least `vehicle_cmds` for control commands, `vehicle_charging_cmds` for
  charging commands, and `offline_access` so you get a refresh token.

## 3. Log in (OAuth authorization-code flow)

```bash
python tesla_cli.py login
```

This opens the Tesla login/consent page in your browser, catches the
redirect locally, exchanges the code for tokens, and caches them in
`.tesla_tokens.json` (git-ignore this file — treat it like a credential).
Tokens are refreshed automatically on expiry by every other command.

Then discover which regional Fleet API host your account uses (also useful
to sanity-check the login worked):

```bash
python tesla_cli.py region
```

Set the returned URL as `TESLA_FLEET_API_BASE` in `.env` if it differs from
the default.

## 4. Set up command signing (`tesla-http-proxy`)

Required once per machine before any *command* (not read) will work on a
2021+ vehicle:

1. Generate an EC key pair for command signing:
   ```bash
   openssl ecparam -name prime256v1 -genkey -noout -out private-key.pem
   openssl ec -in private-key.pem -pubout -out public-key.pem
   ```
2. Host `public-key.pem` at
   `https://<your-registered-domain>/.well-known/appspecific/com.tesla.3p.public-key.pem`
   (must be the domain you verified in the Developer Portal).
3. Build/run Tesla's proxy (see
   https://github.com/teslamotors/vehicle-command for source and prebuilt
   releases):
   ```bash
   tesla-http-proxy -tls-key server-cert.key -cert server-cert.crt \
     -key-file private-key.pem -port 4443
   ```
4. Pair the key with each vehicle from a phone that has the Tesla app and is
   near/paired with the car, by visiting (on that phone):
   ```
   https://tesla.com/_ak/<your-domain>
   ```
   Approve the "add key" prompt in the Tesla app.
5. Leave `TESLA_PROXY_BASE=https://localhost:4443` in `.env` (default). The
   proxy expects the same bearer access token you already have cached — this
   program passes it through automatically.

Until this is set up, `data`, `vehicles`, `wake`, and `region` all work; any
`command`/shortcut call will fail against the proxy port with a connection
error.

## Usage

```bash
# Read-only
python tesla_cli.py vehicles
python tesla_cli.py data <vehicle_tag>
python tesla_cli.py data <vehicle_tag> --endpoints charge_state,climate_state
python tesla_cli.py wake <vehicle_tag>

# List every known command + its params
python tesla_cli.py commands

# Generic command dispatch (works for any command in the catalog)
python tesla_cli.py command <vehicle_tag> set_charge_limit --data '{"percent": 80}'

# Convenience shortcuts
python tesla_cli.py lock <vehicle_tag>
python tesla_cli.py unlock <vehicle_tag>
python tesla_cli.py honk <vehicle_tag>
python tesla_cli.py flash <vehicle_tag>
python tesla_cli.py climate-on <vehicle_tag>
python tesla_cli.py climate-off <vehicle_tag>
python tesla_cli.py set-temp <vehicle_tag> --driver 21 --passenger 21
python tesla_cli.py charge-start <vehicle_tag>
python tesla_cli.py charge-stop <vehicle_tag>
python tesla_cli.py set-charge-limit <vehicle_tag> --percent 80
python tesla_cli.py set-charging-amps <vehicle_tag> --amps 24
python tesla_cli.py trunk <vehicle_tag> --which rear
python tesla_cli.py windows <vehicle_tag> --state vent --lat 37.7 --lon -122.4
python tesla_cli.py sentry <vehicle_tag> --state on
python tesla_cli.py sunroof <vehicle_tag> --state vent
python tesla_cli.py seat-heater <vehicle_tag> --seat 0 --level 2
```

`<vehicle_tag>` is the VIN or numeric vehicle id from `python tesla_cli.py
vehicles`.

## Notes / gotchas

- A car must not be asleep for commands to land quickly — call `wake` first
  if a command times out.
- `set_sentry_mode`, `set_valet_mode`, `set_pin_to_drive`, etc. take an
  explicit `on`/`password` param; the dedicated `sentry` subcommand handles
  this correctly, but don't send those through a param-less shortcut.
- Command names/params can drift as Tesla updates the Fleet API — treat
  `tesla_fleet/commands.py` as a best-effort catalog and check
  https://developer.tesla.com/docs/fleet-api if something 404s or 400s.
- `.tesla_tokens.json` and `.env` contain secrets — keep them out of version
  control.
