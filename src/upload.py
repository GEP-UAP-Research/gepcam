import re
import json
import sys
import os
import datetime
import time
import shutil
import subprocess
import gepcamlib as gepcam

own_path, conf_path, log_path = gepcam.get_own_path_conf_path_log_path()
config = gepcam.load_config(conf_path + "gepcamconfig.json")

daily_upload_limit = 500
runtime_status = {"today_upload_volume": 0}
upload_path = "10.123.0.1:/home/video.hessdalen"


min_upload_age = datetime.timedelta(minutes=30)
max_upload_age = datetime.timedelta(days=2)


def main():
    while True:
        list_of_event_folders = os.listdir(
            config["event-picker"]["event_path"])

        oldest_upload_timestamp = (
            datetime.datetime.now() - max_upload_age).strftime("%Y-%m-%d_%H%M")
        newest_upload_timestamp = (
            datetime.datetime.now() - min_upload_age).strftime("%Y-%m-%d_%H%M")
        # print(oldest_upload_timestamp, newest_upload_timestamp)

        list_of_events_in_timerange = []
        for event in list_of_event_folders:
            if re.match(".*_[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]_[0-9][0-9][0-9][0-9]", event):
                timestamp = re.findall(
                    "_([0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]_[0-9][0-9][0-9][0-9])", event)[0]
                if timestamp > oldest_upload_timestamp and timestamp < newest_upload_timestamp:
                    if not os.path.isfile(config["event-picker"]["event_path"] + event + "/uploaded.flag"):
                        list_of_events_in_timerange.append(event)
        list_of_events_in_timerange = sorted(
            list_of_events_in_timerange, reverse=True)
        # print(list_of_events_in_timerange)

        for event in list_of_events_in_timerange:
            folder = config["event-picker"]["event_path"] + event + "/"
            print("in folder", folder)
            for file in os.listdir(folder):
                if not re.match(".*\.mp4$", file):
                    print("file ignore", file)
                    continue
                size = int(os.stat(folder + file).st_size / (1024 * 1024))
                if size == 0:
                    size = 1
                if runtime_status["today_upload_volume"] + size > daily_upload_limit:
                    print("uploadlimit hit")
                    break
                print("start upload of " + folder + file, size, "MB")
                runtime_status["today_upload_volume"] += size
                if not upload_file(folder + file):
                    print("upload failed")
                    break
            else:
                with open(config["event-picker"]["event_path"] + event + "/uploaded.flag", "w") as f:
                    f.write("")
                print("daily remaining upload volume", daily_upload_limit -
                      runtime_status["today_upload_volume"])
                continue
            break
        print("-----------")
        time.sleep(55)


def upload_file(file: str):
    status = subprocess.call(
        ["scp", file, upload_path])
    if (status == 0):
        print("upload ok")
        return True
    print("upload failed")
    return False


main()
