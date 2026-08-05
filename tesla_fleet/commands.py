"""Catalog of Tesla Fleet API vehicle commands.

Each entry maps a command name (as used in the
`/api/1/vehicles/{vehicle_tag}/command/{name}` endpoint) to the list of
parameter names it accepts and a short description. This is used for CLI
help/validation; unknown extra params are still passed through untouched.

Reference: https://developer.tesla.com/docs/fleet-api/endpoints/vehicle-commands
Command availability, names, and params can change with Tesla's API — treat
this as a best-effort catalog, not a guarantee.
"""

from __future__ import annotations

from typing import NamedTuple


class CommandSpec(NamedTuple):
    params: tuple[str, ...]
    description: str


COMMANDS: dict[str, CommandSpec] = {
    # --- Actuation ---
    "door_lock": ((), "Lock the doors."),
    "door_unlock": ((), "Unlock the doors."),
    "actuate_trunk": (("which_trunk",), "Open/close front or rear trunk. which_trunk: 'front'|'rear'."),
    "flash_lights": ((), "Flash the lights."),
    "honk_horn": ((), "Honk the horn."),
    "remote_start_drive": ((), "Enable keyless driving for the next 2 minutes."),
    "charge_port_door_open": ((), "Open the charge port door."),
    "charge_port_door_close": ((), "Close the charge port door."),
    "window_control": (("command", "lat", "lon"), "Vent or close windows. command: 'vent'|'close'."),
    "sun_roof_control": (("state",), "Vent or close the sunroof. state: 'vent'|'close'|'comfort'."),
    "remote_boombox": (("sound",), "Play a sound through the exterior speaker."),

    # --- Charging ---
    "charge_start": ((), "Start charging."),
    "charge_stop": ((), "Stop charging."),
    "charge_max_range": ((), "Set charge limit to max range."),
    "charge_standard": ((), "Set charge limit to the standard (daily) level."),
    "set_charge_limit": (("percent",), "Set charge limit percentage."),
    "set_charging_amps": (("charging_amps",), "Set the charge current in amps."),
    "add_charge_schedule": (
        (
            "days_of_week",
            "enabled",
            "lat",
            "lon",
            "start_enabled",
            "start_time",
            "end_enabled",
            "end_time",
            "one_time",
        ),
        "Add/update a charge schedule.",
    ),
    "remove_charge_schedule": (("id",), "Remove a charge schedule by id."),
    "add_precondition_schedule": (
        ("days_of_week", "enabled", "lat", "lon", "precondition_time", "one_time"),
        "Add/update a preconditioning schedule.",
    ),
    "remove_precondition_schedule": (("id",), "Remove a preconditioning schedule by id."),

    # --- Climate ---
    "auto_conditioning_start": ((), "Turn on climate control."),
    "auto_conditioning_stop": ((), "Turn off climate control."),
    "set_temps": (("driver_temp", "passenger_temp"), "Set cabin target temperatures (Celsius)."),
    "set_preconditioning_max": (("on", "manual_override"), "Toggle max defrost / preconditioning."),
    "remote_seat_heater_request": (("heater", "level"), "Set a seat heater level (0-3). heater is seat index."),
    "remote_seat_cooler_request": (("seat_position", "seat_cooler_level"), "Set a seat cooler level."),
    "remote_steering_wheel_heater_request": (("on",), "Toggle steering wheel heater."),
    "remote_auto_seat_climate_request": (("auto_seat_position", "auto_climate_on"), "Toggle auto seat climate."),
    "set_bioweapon_mode": (("on", "manual_override"), "Toggle Bioweapon Defense Mode."),
    "set_climate_keeper_mode": (("climate_keeper_mode",), "Set climate keeper mode (off/on/dog/camp)."),
    "set_cabin_overheat_protection": (("on", "fan_only"), "Toggle cabin overheat protection."),

    # --- Security / access ---
    "set_sentry_mode": (("on",), "Toggle Sentry Mode."),
    "set_valet_mode": (("on", "password"), "Toggle valet mode."),
    "reset_valet_pin": ((), "Reset the valet mode PIN."),
    "speed_limit_activate": (("pin",), "Activate speed limit mode."),
    "speed_limit_deactivate": (("pin",), "Deactivate speed limit mode."),
    "speed_limit_set_limit": (("limit_mph",), "Set the speed limit (mph)."),
    "speed_limit_clear_pin": (("pin",), "Clear the speed limit PIN."),
    "speed_limit_clear_pin_admin": ((), "Admin clear of the speed limit PIN."),
    "guest_mode": (("enable",), "Toggle Guest Mode."),
    "set_pin_to_drive": (("on", "password"), "Toggle PIN to Drive."),
    "reset_pin_to_drive_pin": ((), "Reset the PIN to Drive code."),
    "trigger_homelink": (("lat", "lon", "token"), "Trigger a paired HomeLink device."),

    # --- Media / navigation ---
    "media_toggle_playback": ((), "Play/pause media."),
    "media_next_track": ((), "Skip to next track."),
    "media_prev_track": ((), "Skip to previous track."),
    "media_next_fav": ((), "Skip to next favorite."),
    "media_prev_fav": ((), "Skip to previous favorite."),
    "media_volume_up": ((), "Increase volume."),
    "media_volume_down": ((), "Decrease volume."),
    "navigation_request": (("type", "locale", "timestamp_ms", "value"), "Send a navigation request (e.g. share address)."),
    "navigation_gps_request": (("lat", "lon", "order"), "Navigate to raw GPS coordinates."),
    "navigation_sc_request": (("id", "order"), "Navigate to a Supercharger by id."),

    # --- Software / sharing ---
    "schedule_software_update": (("offset_sec",), "Schedule a pending software update."),
    "cancel_software_update": ((), "Cancel a scheduled software update."),
    "share": (("type", "value", "locale", "timestamp_ms"), "Share an address/link to the car."),

    # --- Misc ---
    "set_vehicle_name": (("vehicle_name",), "Rename the vehicle."),
}


def describe(command_name: str) -> str:
    spec = COMMANDS.get(command_name)
    if not spec:
        return f"{command_name}: (not in local catalog — will still be sent as-is)"
    param_names, description = spec
    params = ", ".join(param_names) if param_names else "no params"
    return f"{command_name}: {description} [{params}]"


def list_commands() -> list[str]:
    return sorted(COMMANDS.keys())
