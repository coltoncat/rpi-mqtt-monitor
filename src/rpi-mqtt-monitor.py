# -*- coding: utf-8 -*-
# Python script (runs on 2 and 3) to check cpu load, cpu temperature and free space etc.
# on a Raspberry Pi or Ubuntu computer and publish the data to a MQTT server.
# RUN pip install paho-mqtt
# RUN sudo apt-get install python-pip

import configparser
import json
import logging.handlers
import shutil
import socket
import subprocess
import sys
import time
import uuid

import paho.mqtt.client as mqtt
import psutil

# Only run on Python 3.6 or higher...
assert sys.version_info >= (3, 6)

# Some globals
CONFIG_FILE = "config.ini"

# Setup Logging

logger = logging.getLogger("Logger")
logger.setLevel(logging.DEBUG)
handler = logging.handlers.SysLogHandler(address='/dev/log')
formatter = logging.Formatter('%(asctime)s %(message)s')
handler.setLevel(logging.DEBUG)
handler.setFormatter(formatter)
logger.addHandler(handler)

# get device host name - used in mqtt topic
hostname = socket.gethostname().split('.', 1)[0]


def get_disk_usage(path):
    total, used, free = shutil.disk_usage(path)
    return round(used / total * 100, 2)


def get_cpu_load():
    load1, load5, load15 = psutil.getloadavg()
    ncpu = psutil.cpu_count()
    return round(load1 / ncpu * 100, 2)


def get_voltage(block="core"):
    full_cmd = f"vcgencmd measure_volts {block}| cut -f2 -d= | sed 's/.$//'"
    try:
        result = subprocess.Popen(full_cmd, shell=True, stdout=subprocess.PIPE).communicate()[0]
    except OSError as e:
        logger.error(e)
        result = 0
    result = result.decode('utf8')[:-1]
    logger.info(f"CPU {block} voltage: {result}V")
    return round(float(result), 2)


def get_swap_usage():
    result = psutil.swap_memory()
    return round(result[3], 2)


def get_memory_usage():
    result = psutil.virtual_memory()
    return round(result[2], 2)


def get_temperature():
    full_cmd = "vcgencmd measure_temp | cut -f2 -d= | sed 's/..$//'"
    try:
        result = subprocess.Popen(full_cmd, shell=True, stdout=subprocess.PIPE).communicate()[0]
    except OSError as e:
        logger.error(e)
        result = 0
    result = result.decode('utf8')[:-1]
    logger.info(f"CPU Temperature: {result}C")
    return round(float(result), 2)


def get_current_clock_speed(clock="arm"):
    full_cmd = f"vcgencmd measure_clock {clock} | cut  -f2 -d="
    try:
        result = subprocess.Popen(full_cmd, shell=True, stdout=subprocess.PIPE).communicate()[0]
    except OSError as e:
        logger.error(e)
        result = 0
    result = result.decode('utf8')[:-1]
    logger.info(f"{clock} clock speed: {result}.")
    return round(float(result) / 1000 ** 3, 2)


def get_uptime():
    uptime = time.time() - psutil.boot_time()
    return f"{int(uptime // 86400)}:{int((uptime % 86400) // 3600):02d}:{int((uptime % 3600) // 60):02d}." \
           f"{int(uptime % 60):02d}"


def generate_config_json(what_config, parsed_config):
    data = {
        "state_topic": f"{config['broker'].get('mqtt_topic_prefix')}/{hostname}/state",
        "unique_id": f"{hostname}_{what_config}"
    }

    if what_config == "cpu_load":
        data["icon"] = "mdi:speedometer"
        data["name"] = f"{hostname} CPU Usage"
        data["unit_of_measurement"] = "%"
        data["value_template"] = "{{ value_json.cpu_load}}"
    elif what_config == "cpu_temperature":
        data["icon"] = "hass:thermometer"
        data["name"] = f"{hostname} CPU Temperature"
        data["temperature_unit"] = "C"
        data["unit_of_measurement"] = "°C"
        data["value_template"] = "{{ value_json.cpu_temp}}"
    elif what_config == "disk_usage":
        data["icon"] = "mdi:harddisk"
        data["name"] = f"{hostname} Disk Usage"
        data["unit_of_measurement"] = "%"
        data["value_template"] = "{{ value_json.disk_usage}}"
    elif what_config == "cpu_voltage":
        data["icon"] = "mdi:speedometer"
        data["name"] = f"{hostname} CPU Voltage"
        data["unit_of_measurement"] = "V"
        data["value_template"] = "{{ value_json.cpu_voltage}}"
    elif what_config == "swap_usage":
        data["icon"] = "mdi:harddisk"
        data["name"] = f"{hostname} Disk Swap"
        data["unit_of_measurement"] = "%"
        data["value_template"] = "{{ value_json.swap_utilization}}"
    elif what_config == "memory_utilization":
        data["icon"] = "mdi:memory"
        data["name"] = f"{hostname} Memory Usage"
        data["unit_of_measurement"] = "%"
        data["value_template"] = "{{ value_json.memory_utilization}}"
    elif what_config == "clock_speed":
        data["icon"] = "mdi:speedometer"
        data["name"] = f"{hostname} CPU Clock Speed"
        data["unit_of_measurement"] = "GHz"
        data["value_template"] = "{{ value_json.clock_speed}}"
    elif what_config == "uptime":
        data["icon"] = "mdi:timer"
        data["name"] = f"{hostname} Uptime"
        data["unit_of_measurement"] = "days"
        data["value_template"] = "{{ value_json.uptime}}"
    else:
        return False
    logger.info(json.dumps(data))
    return json.dumps(data)


def generate_update_payload():
    payload = {
        "cpu_load": get_cpu_load(),
        "cpu_temp": get_temperature(),
        "disk_usage": get_disk_usage("/"),
        "cpu_voltage": get_voltage("core"),
        "swap_usage": get_swap_usage(),
        "memory_utilization": get_memory_usage(),
        "clock_speed": get_current_clock_speed("arm"),
        "uptime": get_uptime()
    }
    logger.info(json.dumps(payload))
    return payload


def on_publish(client, userdata, result):
    logger.info("Data published.")
    pass


def open_mqtt_connection(broker_config):
    logger.info(
        f"Connecting to MQTT server at {broker_config['broker'].get('mqtt_broker')}:{int(broker_config['broker'].get('mqtt_port'))}.")
    client_id = hostname + "-" + uuid.uuid4().hex[16:]
    client = mqtt.Client(client_id=client_id)
    client.on_publish = on_publish
    client.username_pw_set(broker_config['broker'].get('mqtt_user'), broker_config['broker'].get('mqtt_password'))
    client.connect(broker_config['broker'].get('mqtt_broker'), int(broker_config['broker'].get('mqtt_port')))
    logger.info("done.")
    return client


def close_mqtt_connection(client):
    logger.info("Closing connection to MQTT server.")
    return client.disconnect()


def publish_to_mqtt(topic, payload, qos, mqtt_client):
    logger.info("Publishing to MQTT Server.")
    mqtt_client.publish(topic, payload, qos=qos)

    return


def read_config(config_file):
    parsed_config = configparser.ConfigParser()
    parsed_config.read(filenames=config_file)

    # A valid config file has two compulsory named sections.
    if not (parsed_config.has_section('broker') and parsed_config.has_section('facets')):
        raise ValueError(f"Invalid config file: {config_file}.")

    return parsed_config


def publish_hass_mqtt_discovery_message(parsed_config):
    client = open_mqtt_connection(parsed_config)
    for key in parsed_config['facets']:
        if not parsed_config.has_section('state') \
                or not parsed_config.getboolean('state', f'{hostname}_{key}_configured', fallback=False):
            if parsed_config['facets'].getboolean(key):
                config_topic = f"homeassistant/sensor/{parsed_config['broker'].get('mqtt_topic_prefix')}/{hostname}_{key}/config"
                payload = generate_config_json(key, parsed_config)
                publish_to_mqtt(config_topic, payload, 0, client)
                if not parsed_config.has_section('state'):
                    parsed_config.add_section('state')
                parsed_config.set('state', f"{hostname}_{key}_configured", str(True))
    # We save the config file, for each active measurement, so we only have to do this once.
    with open(CONFIG_FILE, 'wt') as configfile:
        config.write(configfile)
    return client


if __name__ == '__main__':
    logger.info("Starting to get system status")
    logger.info(f"Reading config file: {CONFIG_FILE}.")

    config = read_config(CONFIG_FILE)
    client = publish_hass_mqtt_discovery_message(config)
    state_topic = f"{config['broker'].get('mqtt_topic_prefix')}/{hostname}/state"
    payload = generate_update_payload()
    publish_to_mqtt(state_topic, json.dumps(payload), 0, client)
    close_mqtt_connection(client)
