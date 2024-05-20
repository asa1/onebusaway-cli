#!/usr/bin/env python3
import requests, time, os, configparser, argparse
from datetime import datetime
from hashlib import md5
from blessings import Terminal

#Convert direction abbrevation to word:
def human_direction(direction):
    match direction:
        case "N":
            direction_name = 'North'
        case "NE":
            direction_name = 'Northeast'
        case "E":
            direction_name = 'East'
        case "SE":
            direction_name = 'Southeast'
        case "S":
            direction_name = 'South'
        case "SW":
            direction_name = 'Southwest'
        case "W":
            direction_name = 'West'
        case "NW":
            direction_name = 'Northwest'
        case "":
            direction_name = ''
    return direction_name

#Get bus arrivals at a stop:
def get_bus_arrivals(url):
    response = requests.get(url)
    if response.status_code != 200:
        print("Error fetching data from the server.")
        return

    data = response.json()
    return data["data"]["entry"]["arrivalsAndDepartures"]

#Get information about bus stop:
def get_stop(url):
    response = requests.get(url)
    if response.status_code != 200:
        print("Error fetching data from the server.")
        return

    data = response.json()
    return data["data"]["entry"]

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
        print(f"Time format {time_format} invalid, expecting 12 or 24")
        raise

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
    default_config_path = os.path.expanduser('~/.config/onebuscli/config.ini')

    parser = argparse.ArgumentParser(description='OneBusAway CLI Stop Monitor')
    parser.add_argument('-c', '--config', default=default_config_path, help='Config file path. Default path is ~/.config/onebuscli/config.ini')
    args = parser.parse_args()

    config.read(args.config)
    api_server = config.get('Settings', 'api_server', fallback=defaults['api_server'])
    api_key = config.get('Settings', 'api_key', fallback=defaults['api_key'])

    # Stop codes for Puget Sound can be found by searching for addresses here: https://pugetsound.onebusaway.org/m/
    # (Look for something in the format of <short integer>_<long integer>. For example, Seattle bus stops are 1_<stop number>
    stop_code = config.get('Settings', 'stop_code', fallback=defaults['stop_code'])
    # color_salt allows changing random set of colors (use any integer):
    color_salt = int(config.get('Settings', 'color_salt', fallback=defaults['color_salt']))
    minutes_after = int(config.get('Settings', 'minutes_after', fallback=defaults['minutes_after']))
    time_format = int(config.get('Settings', 'time_format', fallback=defaults['time_format']))
    arrivals_url = f"{api_server}/api/where/arrivals-and-departures-for-stop/{stop_code}.json?key={api_key}&minutesAfter={minutes_after}&_=1701366161699"
    stop_url = f"{api_server}/api/where/stop/{stop_code}.json?key={api_key}"
    stop_info = get_stop(stop_url)
    t = Terminal()
    os.system('clear')
    try:
        with t.hidden_cursor():
            while True:
                print(t.move_y(0))
                buses = get_bus_arrivals(arrivals_url)
                direction_name = human_direction(stop_info['direction'])
                stop_name_text = t.bold(t.color(135)(f"{stop_info['name']}"))
                stop_direction_text = t.bold(t.color(123)(f"{direction_name}"))
                print(f" {stop_name_text}: {stop_direction_text}\n")  
                if len(buses) == 0:
                    print(f" No scheduled stops in the next {minutes_after} minutes")
                else:
                    try:
                        # If set, max_list will only list the upcoming <max_list> number of buses:
                        max_list = int(config.get('Settings', 'max_list'))
                        del buses[max_list:]
                    except:
                        pass
                    name_pad = max(len(bus['routeShortName']) for bus in buses)
                    for bus in buses:
                        display_bus_info(bus, t, color_salt, name_pad, time_format)
                time.sleep(config.getint('General', 'sleep_seconds', fallback=int(defaults['sleep_seconds'])))
    except KeyboardInterrupt:
        pass
