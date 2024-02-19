"""A JSON API for a soil sensor.

Some notes on the sensor

Sensor used:
https://thepihut.com/products/capacitive-soil-moisture-sensor

The sensor returns the following values (in u16):
- 20,000 in a glass of water
- 27,000 in not dry, not wet soil
- 50,000 in the air

I am therefore concluding that the lower the value, the wetter the soil.
I will attempt to use 40000 as a threshold for "too dry". We will see how
this goes. The max value for a u16 reading is 65535, so 40000 is about 60%
of the way to the max value.
"""

import network
import socket
import time
import ubinascii
import json

from machine import ADC


# Plant settings
PLANT_NAME = "Andrew's Yucca Plant"
MAX_DRYNESS_PERCENTAGE = 60.0

# WiFi settings
SSID = "Fast Internet"
PASSWORD = "your_wifi_password"
MAX_WIFI_CONNECTION_ATTEMPTS = 30
LISTENING_PORT = 80

# Pin settings
DATA_PIN = ADC(28)
LED_PIN = "LED"


def connect_to_wifi() -> str:
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    mac_address = ubinascii.hexlify(network.WLAN().config('mac'), ':').decode()
    print(f"Connecting to WiFi network {SSID}...")
    print(f"MAC Address: {mac_address}")

    wlan.connect(SSID, PASSWORD)

    max_wait = MAX_WIFI_CONNECTION_ATTEMPTS
    while max_wait > 0:
        if wlan.status() < 0 or wlan.status() >= 3:
            break

        max_wait -= 1
        print("Waiting for connection to WiFi...")
        time.sleep(1)

    if wlan.status() != 3:
        raise RuntimeError("Network connection failed!")

    status = wlan.ifconfig()
    ip_address = status[0]

    print(f"Connected to WiFi network {SSID}!")
    print(f"IP Address: {ip_address}")
    return ip_address


def make_socket(port=80) -> socket.socket:
    addr = socket.getaddrinfo('0.0.0.0', port)[0][-1]
    s = socket.socket()
    s.bind(addr)
    s.listen(1)
    return s


def get_soil_data() -> tuple[float, bool]:
    """Get data from the soil sensor.

    Returns a tuple containing the dryness of the soil (as a percentage) and
    whether the soil is too dry.
    """
    value = round(DATA_PIN.read_u16() / 65535 * 100, 1)

    return (
        value,
        value > MAX_DRYNESS_PERCENTAGE,
    )


def main_loop(
    listener: socket.socket,
) -> None:
    try:
        client, addr = listener.accept()
        request_ip, _ = addr
        print(f"Request received from {request_ip}.")

        dryness, is_too_dry = get_soil_data()

        result = json.dumps({
            "plant": PLANT_NAME,
            "dryness_percent": dryness,
            "max_allowable_dryness": MAX_DRYNESS_PERCENTAGE,
            "is_plant_too_dry": is_too_dry,
        })

        response = (
            "HTTP/1.1 200 OK\n"
            f"Content-Length: " + str(len(result)) + "\n"
            "Content-Type: application/json\n\n"
            f"{result}\n"
        ).encode("utf-8")

        client.send(response)

        print(f"Sent to {request_ip}: {response}")

        time.sleep(1)
        client.close()
    except Exception as err:
        client.close()
        print(f"Connection closed: {err}")


def main() -> None:
    print("Started! Configuring pins...")

    ip_address = connect_to_wifi()
    listener = make_socket(LISTENING_PORT)

    print(f"Listening for requests on http://{ip_address}:{LISTENING_PORT}...")
    while True:
        main_loop(listener)


if __name__ == "__main__":
    main()
