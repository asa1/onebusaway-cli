#!/usr/bin/env python3
import argparse
import configparser
import sys
import time
from datetime import datetime
from hashlib import md5
from pathlib import Path

import requests
from blessed import Terminal

#Convert direction abbrevation to word:
def human_direction(direction):
    directions = {
        "N": "North",
        "NE": "Northeast",
        "E": "East",
        "SE": "Southeast",
        "S": "South",
        "SW": "Southwest",
        "W": "West",
        "NW": "Northwest",
    }
    return directions.get(direction, "")

def get_config_int(config, section, option, default):
    value = config.get(section, option, fallback=str(default))
    try:
        return int(value)
    except ValueError:
        raise ValueError(f"{option} must be an integer, got {value!r}")

def fetch_json(url, show_errors=True):
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as error:
        if show_errors:
            print(f"Error fetching data from the server: {error}")
    except ValueError as error:
        if show_errors:
            print(f"Error decoding server response: {error}")
    return None

#Get bus arrivals at a stop:
def get_bus_arrivals(url):
    data = fetch_json(url)
    if data is None:
        return None

    entry = (data.get("data") or {}).get("entry") or {}
    return entry.get("arrivalsAndDepartures") or []

#Get information about bus stop:
def get_stop(url, show_errors=True):
    data = fetch_json(url, show_errors)
    if data is None:
        return None

    return (data.get("data") or {}).get("entry") or None

def list_config_stops(config, defaults):
    sections = config.sections()
    if len(sections) == 0:
        raise ValueError("no stops found in config file")

    name_pad = max(len(section) for section in sections)
    code_pad = max(
        len(config.get(section, 'stop_code', fallback=defaults['stop_code']))
        for section in sections
    )

    for section in sections:
        stop_code = config.get(section, 'stop_code', fallback=defaults['stop_code'])
        api_server = config.get(section, 'api_server', fallback=defaults['api_server'])
        api_key = config.get(section, 'api_key', fallback=defaults['api_key'])
        stop_url = f"{api_server}/api/where/stop/{stop_code}.json?key={api_key}"
        stop_info = get_stop(stop_url, show_errors=False)
        if stop_info is None:
            stop_description = "unavailable"
        else:
            stop_name = stop_info.get("name", "unavailable")
            direction_name = human_direction(stop_info.get("direction"))
            stop_description = f"{stop_name}: {direction_name}" if direction_name else stop_name
        print(f"{section.ljust(name_pad)}  {stop_code.ljust(code_pad)}  {stop_description}")

def display_bus_info(bus, t, color_salt, name_pad, time_format):
    name = bus["routeShortName"]

    # Use the hash value to pick a color from the 256-color range
    hash_value = int(md5((name * color_salt).encode()).hexdigest(), 16)
    route_color = (hash_value % 207) + 21

    scheduled_time = bus["scheduledArrivalTime"]
    predicted_time = bus["predictedArrivalTime"]

    now_epoch = int(time.time()) * 1000
    time_from_now = round((predicted_time - now_epoch) / 60000) if predicted_time else round((scheduled_time - now_epoch) / 60000)
    arrival_time = predicted_time if predicted_time else scheduled_time
    if time_format == 12:
        formatted_time = datetime.fromtimestamp(arrival_time / 1000).strftime("%-I:%M%p").rjust(7).lower()
    elif time_format == 24:
        formatted_time = datetime.fromtimestamp(arrival_time / 1000).strftime("%H:%M")
    else:
        raise ValueError(f"time_format must be 12 or 24, got {time_format}")

    if predicted_time == 0:
        arrival_text = 'Scheduled: '
        status_color = 27  # Blue in 256-color
    elif -1 < time_from_now < 6:
        arrival_text = 'Arrives:   '
        status_color = 226  # Yellow in 256-color
    elif time_from_now < 0:
        arrival_text = 'Departed:  '
        status_color = 196  # Red in 256-color
    else:
        arrival_text = 'Arrives:   '
        status_color = 46  # Green in 256-color

    delta = round((scheduled_time - arrival_time) / 60000)

    # Generate display text:
    if delta < 0:
        delta_text = t.color(241)(f"({abs(delta)}min late)    ")
    elif delta == 0 or predicted_time == 0:
        # Lazy method to overwrite old text on terminal refresh:
        delta_text = '                 '
    else:
        delta_text = t.color(241)(f"({delta}min early)     ")

    route_text = t.bold(t.color(route_color)(f"{name.rjust(name_pad)}"))
    time_text = t.color(status_color)(f"{time_from_now}min".rjust(6))
    formatted_time_text = t.color(110)(f"{formatted_time}")
    print(f" ┃ {route_text} ┃ {formatted_time_text} ┃ {arrival_text}{time_text} {delta_text}")

def wait_for_quit(t, sleep_seconds):
    deadline = time.monotonic() + sleep_seconds
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False

        key = t.inkey(timeout=min(0.1, remaining))
        if str(key).lower() == 'q':
            return True

if __name__ == "__main__":
    config = configparser.ConfigParser()
    defaults = {
        'api_server': 'https://api.pugetsound.onebusaway.org',
        'api_key': '5654bb33-edab-4322-8688-94b9d262abe4',
        'stop_code': '1_860',
        'sleep_seconds': '20',
        'color_salt': 1,
        'minutes_after': 240,
        'time_format': 24,
    }
    default_config_path = Path('~/.config/onebuscli/config.ini').expanduser()

    parser = argparse.ArgumentParser(description='OneBusAway CLI Stop Monitor')
    parser.add_argument('-c', '--config', default=default_config_path, help='Config file path. Default path is ~/.config/onebuscli/config.ini')
    parser.add_argument('-s', '--stop', help='Stop section name from config. Defaults to \'Default\'')
    parser.add_argument('-l', '--list-stops', action='store_true', help='List stops configured in the config file and exit')
    args = parser.parse_args()

    config.read(args.config)

    if args.list_stops:
        try:
            list_config_stops(config, defaults)
        except ValueError as error:
            parser.error(str(error))
        sys.exit(0)

    # Stop codes for Puget Sound can be found by searching for addresses here: https://pugetsound.onebusaway.org/m/
    # (Look for something in the format of <short integer>_<long integer>. For example, Seattle bus stops are 1_<stop number>
    if args.stop:
        if args.stop not in config.sections():
            parser.error(f"stop section {args.stop!r} not found in {args.config}")
        selected_stop = args.stop
    else:
        selected_stop = 'Default'
    stop_code = config.get(selected_stop, 'stop_code', fallback=defaults['stop_code'])
    # color_salt allows changing random set of colors (use any integer):
    try:
        color_salt = get_config_int(config, selected_stop, 'color_salt', defaults['color_salt'])
        minutes_after = get_config_int(config, selected_stop, 'minutes_after', defaults['minutes_after'])
        time_format = get_config_int(config, selected_stop, 'time_format', defaults['time_format'])
        sleep_seconds = get_config_int(config, selected_stop, 'sleep_seconds', defaults['sleep_seconds'])
        max_list = get_config_int(config, selected_stop, 'max_list', 0)
    except ValueError as error:
        parser.error(str(error))

    if time_format not in (12, 24):
        parser.error(f"time_format must be 12 or 24, got {time_format}")
    if sleep_seconds < 1:
        parser.error(f"sleep_seconds must be at least 1, got {sleep_seconds}")
    if minutes_after < 0:
        parser.error(f"minutes_after must be non-negative, got {minutes_after}")

    api_server = config.get(selected_stop, 'api_server', fallback=defaults['api_server'])
    api_key = config.get(selected_stop, 'api_key', fallback=defaults['api_key'])

    arrivals_url = f"{api_server}/api/where/arrivals-and-departures-for-stop/{stop_code}.json?key={api_key}&minutesAfter={minutes_after}"
    stop_url = f"{api_server}/api/where/stop/{stop_code}.json?key={api_key}"
    stop_info = get_stop(stop_url)
    if stop_info is None:
        print(f"Could not load stop information for {stop_code}.")
        sys.exit(1)

    t = Terminal()
    print(t.clear)
    try:
        with t.hidden_cursor(), t.cbreak():
            while True:
                print(t.move_y(0))
                buses = get_bus_arrivals(arrivals_url)
                if buses is None:
                    if wait_for_quit(t, sleep_seconds):
                        break
                    continue

                direction_name = human_direction(stop_info.get('direction'))
                stop_name_text = t.bold(t.color(135)(f"{stop_info.get('name', stop_code)}"))
                stop_direction_text = t.bold(t.color(123)(f"{direction_name}"))
                print(f" {stop_name_text}: {stop_direction_text}\n")  
                if len(buses) == 0:
                    print(f" No scheduled stops in the next {minutes_after} minutes")
                else:
                    # If set, max_list only lists the upcoming <max_list> number of buses:
                    if max_list > 0:
                        del buses[max_list:]
                    name_pad = max(len(bus['routeShortName']) for bus in buses)
                    for bus in buses:
                        display_bus_info(bus, t, color_salt, name_pad, time_format)
                if wait_for_quit(t, sleep_seconds):
                    break
    except KeyboardInterrupt:
        pass
