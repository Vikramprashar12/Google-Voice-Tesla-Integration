from __future__ import annotations

import argparse
import json
import sys

from .api import TeslaApiError, TeslaFleetClient
from .auth import TeslaAuth, TeslaAuthError
from .commands import describe, list_commands
from .config import Config


def _client() -> TeslaFleetClient:
    config = Config()
    config.validate()
    auth = TeslaAuth(config)
    return TeslaFleetClient(config, auth)


def _print(obj) -> None:
    print(json.dumps(obj, indent=2, default=str))


def cmd_login(args: argparse.Namespace) -> None:
    config = Config()
    config.validate()
    auth = TeslaAuth(config)
    tokens = auth.login_interactive(open_browser=not args.no_browser)
    print("Login successful. Tokens cached at", config.token_file)
    _print({k: v for k, v in tokens.items() if k != "access_token" and k != "refresh_token"})


def cmd_refresh(args: argparse.Namespace) -> None:
    config = Config()
    auth = TeslaAuth(config)
    tokens = auth.load_tokens()
    if not tokens:
        print("No cached tokens; run `login` first.", file=sys.stderr)
        sys.exit(1)
    new_tokens = auth.refresh(tokens["refresh_token"])
    print("Token refreshed.")
    _print({k: v for k, v in new_tokens.items() if k not in ("access_token", "refresh_token")})


def cmd_region(args: argparse.Namespace) -> None:
    _print(_client().discover_region())


def cmd_vehicles(args: argparse.Namespace) -> None:
    _print(_client().list_vehicles())


def cmd_data(args: argparse.Namespace) -> None:
    endpoints = args.endpoints.split(",") if args.endpoints else None
    _print(_client().vehicle_data(args.vehicle_tag, endpoints=endpoints))


def cmd_wake(args: argparse.Namespace) -> None:
    _print(_client().wake_up(args.vehicle_tag))


def cmd_commands(args: argparse.Namespace) -> None:
    for name in list_commands():
        print(describe(name))


def cmd_command(args: argparse.Namespace) -> None:
    params = json.loads(args.data) if args.data else {}
    _print(_client().command(args.vehicle_tag, args.command_name, params))


# ---- convenience wrappers for the most common commands ----

def _simple(name: str):
    def handler(args: argparse.Namespace) -> None:
        _print(_client().command(args.vehicle_tag, name, {}))

    return handler


def cmd_set_temp(args: argparse.Namespace) -> None:
    _print(
        _client().command(
            args.vehicle_tag, "set_temps", {"driver_temp": args.driver, "passenger_temp": args.passenger}
        )
    )


def cmd_set_charge_limit(args: argparse.Namespace) -> None:
    _print(_client().command(args.vehicle_tag, "set_charge_limit", {"percent": args.percent}))


def cmd_set_charging_amps(args: argparse.Namespace) -> None:
    _print(_client().command(args.vehicle_tag, "set_charging_amps", {"charging_amps": args.amps}))


def cmd_trunk(args: argparse.Namespace) -> None:
    _print(_client().command(args.vehicle_tag, "actuate_trunk", {"which_trunk": args.which}))


def cmd_windows(args: argparse.Namespace) -> None:
    _print(
        _client().command(
            args.vehicle_tag,
            "window_control",
            {"command": args.state, "lat": args.lat, "lon": args.lon},
        )
    )


def cmd_sentry(args: argparse.Namespace) -> None:
    _print(_client().command(args.vehicle_tag, "set_sentry_mode", {"on": args.state == "on"}))


def cmd_sunroof(args: argparse.Namespace) -> None:
    _print(_client().command(args.vehicle_tag, "sun_roof_control", {"state": args.state}))


def cmd_seat_heater(args: argparse.Namespace) -> None:
    _print(_client().command(args.vehicle_tag, "remote_seat_heater_request", {"heater": args.seat, "level": args.level}))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tesla_cli", description="Talk to the Tesla Fleet API.")
    sub = parser.add_subparsers(dest="action", required=True)

    p = sub.add_parser("login", help="Run the OAuth authorization-code flow and cache tokens.")
    p.add_argument("--no-browser", action="store_true", help="Don't auto-open a browser; print the URL instead.")
    p.set_defaults(func=cmd_login)

    p = sub.add_parser("refresh", help="Refresh the cached access token.")
    p.set_defaults(func=cmd_refresh)

    p = sub.add_parser("region", help="Discover the correct regional Fleet API base URL for this account.")
    p.set_defaults(func=cmd_region)

    p = sub.add_parser("vehicles", help="List vehicles on this account.")
    p.set_defaults(func=cmd_vehicles)

    p = sub.add_parser("data", help="Fetch vehicle_data.")
    p.add_argument("vehicle_tag", help="VIN or vehicle id.")
    p.add_argument("--endpoints", help="Comma-separated endpoint list, e.g. charge_state,climate_state")
    p.set_defaults(func=cmd_data)

    p = sub.add_parser("wake", help="Wake up a vehicle.")
    p.add_argument("vehicle_tag")
    p.set_defaults(func=cmd_wake)

    p = sub.add_parser("commands", help="List the full known command catalog.")
    p.set_defaults(func=cmd_commands)

    p = sub.add_parser("command", help="Send an arbitrary command by name (goes through the signing proxy).")
    p.add_argument("vehicle_tag")
    p.add_argument("command_name")
    p.add_argument("--data", help="JSON object of command params, e.g. '{\"percent\": 80}'")
    p.set_defaults(func=cmd_command)

    # Convenience shortcuts
    shortcuts = {
        "lock": "door_lock",
        "unlock": "door_unlock",
        "honk": "honk_horn",
        "flash": "flash_lights",
        "climate-on": "auto_conditioning_start",
        "climate-off": "auto_conditioning_stop",
        "charge-start": "charge_start",
        "charge-stop": "charge_stop",
        "charge-port-open": "charge_port_door_open",
        "charge-port-close": "charge_port_door_close",
        "remote-start": "remote_start_drive",
    }
    for cli_name, command_name in shortcuts.items():
        p = sub.add_parser(cli_name, help=f"Shortcut for command '{command_name}'.")
        p.add_argument("vehicle_tag")
        p.set_defaults(func=_simple(command_name))

    p = sub.add_parser("set-temp", help="Set cabin target temperatures (Celsius).")
    p.add_argument("vehicle_tag")
    p.add_argument("--driver", type=float, required=True)
    p.add_argument("--passenger", type=float, required=True)
    p.set_defaults(func=cmd_set_temp)

    p = sub.add_parser("set-charge-limit", help="Set charge limit percentage.")
    p.add_argument("vehicle_tag")
    p.add_argument("--percent", type=int, required=True)
    p.set_defaults(func=cmd_set_charge_limit)

    p = sub.add_parser("set-charging-amps", help="Set charge current in amps.")
    p.add_argument("vehicle_tag")
    p.add_argument("--amps", type=int, required=True)
    p.set_defaults(func=cmd_set_charging_amps)

    p = sub.add_parser("trunk", help="Open/close front or rear trunk.")
    p.add_argument("vehicle_tag")
    p.add_argument("--which", choices=["front", "rear"], required=True)
    p.set_defaults(func=cmd_trunk)

    p = sub.add_parser("windows", help="Vent or close windows.")
    p.add_argument("vehicle_tag")
    p.add_argument("--state", choices=["vent", "close"], required=True)
    p.add_argument("--lat", type=float, required=True)
    p.add_argument("--lon", type=float, required=True)
    p.set_defaults(func=cmd_windows)

    p = sub.add_parser("sentry", help="Turn Sentry Mode on/off.")
    p.add_argument("vehicle_tag")
    p.add_argument("--state", choices=["on", "off"], required=True)
    p.set_defaults(func=cmd_sentry)

    p = sub.add_parser("sunroof", help="Vent/close/comfort the sunroof.")
    p.add_argument("vehicle_tag")
    p.add_argument("--state", choices=["vent", "close", "comfort"], required=True)
    p.set_defaults(func=cmd_sunroof)

    p = sub.add_parser("seat-heater", help="Set a seat heater level (0-3).")
    p.add_argument("vehicle_tag")
    p.add_argument("--seat", type=int, required=True, help="Seat index (0=driver, 1=passenger, ...).")
    p.add_argument("--level", type=int, required=True, choices=[0, 1, 2, 3])
    p.set_defaults(func=cmd_seat_heater)

    return parser


def main(argv=None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except TeslaAuthError as e:
        print(f"Auth error: {e}", file=sys.stderr)
        sys.exit(1)
    except TeslaApiError as e:
        print(f"API error: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
