from collections import defaultdict
import time
import re
import os
import sys
import json

runtime_statistics_switch = True

runtime_statistics_timer = {"timers": {}, "last_event": "",
                            "last_time": 0, "last_reset": 0, "interval": 100000000000}

FilesLastModificationTime = defaultdict(float)


def get_own_path_conf_path_log_path():
    own_path = re.sub(
        "\\\\", "/", os.path.dirname(os.path.abspath(sys.argv[0]))) + '/'
    conf_path = re.sub("/[^/]*/$", "/conf/", own_path)
    log_path = re.sub("/[^/]*/$", "/log/", own_path)
    fatal_if_dir_not_exist(own_path)
    fatal_if_dir_not_exist(conf_path)
    fatal_if_dir_not_exist(log_path)
    return own_path, conf_path, log_path


def load_config(configfilename: str):
    with open(configfilename) as f:
        config = json.load(f)
    return config


def save_config(config: dict, configfilename: str):
    with open(configfilename, "w") as f:
        json.dump(config, f, indent=2)
        print("config saved to " + configfilename)


def fatal_if_dir_not_exist(path: str):
    if not os.path.isdir(path):
        print(f"directory {path} does not exist, exiting")
        sys.exit(1)


def fatal_if_file_not_exist(path: str):
    if not os.path.isfile(path):
        print(f"file {path} does not exist, exiting")
        sys.exit(1)


def CheckFileHasNewModifyTime(*files) -> bool:
    global FilesLastModificationTime
    HasModify = False
    try:
        for i in files:
            FileDate = os.path.getmtime(i)
            if FileDate != FilesLastModificationTime[i]:
                HasModify = True
                FilesLastModificationTime[i] = FileDate
    except:
        pass
    return HasModify


def runtime_stats(next_event: str):
    global runtime_statistics_switch
    global runtime_statistics_timer
    if not runtime_statistics_switch:
        return
    now_time = time.time_ns()

    if runtime_statistics_timer['last_event']:
        if not runtime_statistics_timer['last_event'] in runtime_statistics_timer['timers']:
            runtime_statistics_timer['timers'][runtime_statistics_timer['last_event']] = list(
            )
        runtime_statistics_timer['timers'][runtime_statistics_timer['last_event']].append(
            now_time - runtime_statistics_timer['last_time'])
    statistics = {}
    if runtime_statistics_timer['interval'] < now_time - runtime_statistics_timer['last_reset']:
        if runtime_statistics_timer['last_reset']:
            print('------- runtime statistics -------')
        for name in runtime_statistics_timer['timers']:
            max = 0
            min = 1000000000000000000
            sum = 0
            for value in runtime_statistics_timer['timers'][name]:
                if value > max:
                    max = value
                if value < min:
                    min = value
                sum += value
            statistics[name] = {'count': len(runtime_statistics_timer['timers'][name]), 'max': max // 1000000,
                                'min': min // 1000000, 'average': int(sum / (len(runtime_statistics_timer['timers'][name])-0.00001) // 1000000)}
            runtime_statistics_timer['timers'][name] = []
            print(statistics)
            statistics = {}
        runtime_statistics_timer['last_reset'] = now_time
    runtime_statistics_timer['last_event'] = next_event
    runtime_statistics_timer['last_time'] = time.time_ns()
