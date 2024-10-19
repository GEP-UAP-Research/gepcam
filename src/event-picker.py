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


file = config['event-picker']['events_logfile']
if file[0] != '/':
    file = log_path + file

system_hostname = config['global']['hostname']
event_path = config['event-picker']['event_path']
if sys.platform == 'win32':
    ffmpeg = own_path + 'ffmpeg.exe'
else:
    ffmpeg = '/usr/bin/ffmpeg'

show_seconds_before = datetime.timedelta(seconds=1.0)
show_seconds_after = datetime.timedelta(seconds=5.0)
min_seconds = 0.5
workingrange_min_age = datetime.timedelta(minutes=1)
workingrange_max_age = datetime.timedelta(minutes=80)


def main():
    while True:
        pick_video_files()
        time.sleep(11)
        find_combine_and_cut_videofiles(event_path)
        time.sleep(66)
    pass


def pick_video_files():
    events = parse_events(file)
    events = events_consolidieren(
        eventlist=events, min_seconds_between_events=15)
   # events = events_add_time_at_beginning_and_end(
   #     events, add_seconds_begin=-0.9, add_seconds_end=0.9)
    videofiles = {}
    for camname in config['recording']:
        videofiles[camname] = get_video_path_files_and_dates(
            video_path=config['recording'][camname]['store_path'] + 'video/')
    now_time = datetime.datetime.now()
    for begin, end in events:
        if now_time - end > workingrange_min_age and now_time - begin < workingrange_max_age:
            if (end - begin).seconds >= min_seconds:
                json_out = {'hostname': system_hostname,
                            'begin': begin.isoformat(), 'end': end.isoformat()}
                foldername = generate_event_folder_name(
                    begin, end, system_hostname)
                videofiles_found = {}
                for camname in videofiles:
                    videofiles_found[camname] = find_videofiles_at_event_time(
                        begin=begin - show_seconds_before, end=end + show_seconds_after, videofiles=videofiles[camname])
                json_out['videofiles'] = videofiles_found
                if not os.path.isdir(event_path + foldername):
                    print("-----------------------------------------------------------")
                    print(begin, end)
                    print(event_path + foldername)
                    os.makedirs(event_path + foldername)
                    for camname in videofiles_found:
                        os.makedirs(event_path + foldername + camname)
                        for videofile in videofiles_found[camname]:
                            videofiles_without_path = a = re.sub(
                                "^.*/", "", videofile)
                            print(videofile, event_path + foldername +
                                  camname + '/' + videofiles_without_path)
                            shutil.copyfile(videofile, event_path + foldername +
                                            camname + '/' + videofiles_without_path)
                    with open(event_path + foldername + 'event_data.json', 'w') as f:
                        json.dump(json_out, f)


def find_combine_and_cut_videofiles(path: str):
    for eventfolder in os.listdir(path):
        if os.path.isdir(path + eventfolder):
            data = load_event_data_json(
                path + eventfolder + '/' + 'event_data.json')
            if "videofiles" in data:
                for cam in data["videofiles"]:
                    if cam in config["recording"]:
                        output_file = path + eventfolder + '/' + cam + '.mp4'
                        if os.path.isfile(output_file):
                            os.remove(output_file)
                        output_file = path + eventfolder + '/' + eventfolder + '_' + cam + '.mp4'
                        Turn_180 = False
                        if "turn_180" in config["recording"][cam]:
                            if config["recording"][cam]["turn_180"]:
                                Turn_180 = True
                        if not os.path.isfile(output_file):
                            combine_and_cut_videofiles(begin=data['begin'], end=data['end'], path=path + eventfolder + '/' +
                                                       cam + '/', videofiles=data["videofiles"][cam], Turn_180=Turn_180, output_file=output_file)


def generate_event_folder_name(begin: datetime.datetime, end: datetime.datetime, name: str):
    return 'event_' + name + begin.strftime("_%Y-%m-%d_%H%M%S__") + str(int((end - begin).seconds)) + 's/'


def find_videofiles_at_event_time(begin: datetime.datetime, end: datetime.datetime, videofiles: dict) -> list:
    return_list = []
    for filetimestamp, filename in list(videofiles.items())[-1::-1]:
        if filetimestamp > begin and filetimestamp < end:
            return_list.append(filename)
        elif filetimestamp <= begin:
            return_list.append(filename)
            break
    return sorted(return_list)


def parse_events(file: str) -> list:
    with open(file) as f:
        text = f.read()
    event_dates = []
    event_dates = re.findall(
        "[0-9][0-9][0-9][0-9]\-[0-9][0-9]\-[0-9][0-9] [0-9][0-9]:[0-9][0-9]:[0-9][0-9]\.[0-9]+", text)
    event_dates = sorted(event_dates)
    event_dates_timestamp = []
    for i in event_dates:
        event_dates_timestamp.append(
            datetime.datetime.strptime(i, "%Y-%m-%d %H:%M:%S.%f"))
    return (event_dates_timestamp)


def events_consolidieren(eventlist: list, min_seconds_between_events: float) -> list:
    min_timedelta = datetime.timedelta(seconds=min_seconds_between_events)
    consolidiert = []
    last_event = eventlist[0]
    event_begin = eventlist[0]
    for i in eventlist[1:]:
        if i - last_event > min_timedelta:
            consolidiert.append([event_begin, last_event])
            event_begin = i
        last_event = i
    return consolidiert


def events_add_time_at_beginning_and_end(eventlist: list, add_seconds_begin: float, add_seconds_end: float) -> list:
    new_eventlist = []
    for begin, end in eventlist:
        new_eventlist.append(
            [begin + datetime.timedelta(seconds=add_seconds_begin), end + datetime.timedelta(seconds=add_seconds_end)])
    return new_eventlist


def get_video_path_files_and_dates(video_path: str) -> dict:
    allfiles = dict()
    for datefolder in os.listdir(video_path):
        if os.path.isdir(video_path + datefolder):
            for hourfolder in os.listdir(video_path + datefolder):
                if os.path.isdir(video_path + datefolder + '/' + hourfolder):
                    for file in os.listdir(video_path + datefolder + '/' + hourfolder):
                        filename_timestamp = re.search(
                            "[0-9]{4}-[0-9]{2}-[0-9]{2}_[0-9]{6}\.[0-9]+", file)
                        if filename_timestamp:
                            allfiles[datetime.datetime.strptime(
                                filename_timestamp[0], "%Y-%m-%d_%H%M%S.%f")] = video_path + datefolder + '/' + hourfolder + '/' + file
    sorted_allfiles = dict()
    for file in sorted(allfiles):
        sorted_allfiles[file] = allfiles[file]
    return sorted_allfiles


def combine_and_cut_videofiles(begin: datetime.datetime, end: datetime.datetime, path: str, videofiles: list, Turn_180: bool, output_file: str):
    videofiles_in = []
    cmd = [ffmpeg]
    if not videofiles:
        return
    first_file_time = re.search(
        "([0-9]{4}-[0-9]{2}-[0-9]{2}_[0-9]{6}\.[0-9]{3})\.", videofiles[0])[1]
    first_file_time = datetime.datetime.strptime(
        first_file_time, "%Y-%m-%d_%H%M%S.%f")
    for file in videofiles:
        videofiles_in.append(path + file)
        cmd.append('-i')
        cmd.append(path + file)
    begin_in_video = begin - first_file_time
    end_in_video = end - begin
    print(">", str(begin_in_video.total_seconds()),
          str(end_in_video.total_seconds()))
    cmd.append('-filter_complex')
    if Turn_180:
        cmd.append('concat=n=' + str(len(videofiles_in)) +
                   ':v=1:a=0,  vflip, hflip')
    else:
        cmd.append('concat=n=' + str(len(videofiles_in)) + ':v=1:a=0')
    cmd.append('-ss')
    cmd.append(str(begin_in_video.total_seconds()))
    cmd.append('-t')
    cmd.append(str(end_in_video.total_seconds()))
    cmd = cmd + ['-vsync', '2']  # sonst probleme mit roalink
    cmd = cmd + ['-an', '-y', output_file]
    print(cmd)
    subprocess.run(cmd, shell=False)


def load_event_data_json(filename: str) -> dict:
    if not os.path.isfile(filename):
        return {}
    data = {"videofiles": []}
    try:
        with open(filename) as f:
            data = json.load(f)
            data["begin"] = datetime.datetime.fromisoformat(data["begin"])
            data["end"] = datetime.datetime.fromisoformat(data["end"])
            for cam in data["videofiles"]:
                new_list = list()
                for file in sorted(list(data["videofiles"][cam])):
                    new_list.append(re.sub("^.*\/", "", file))
                data["videofiles"][cam] = new_list
    except:
        pass
    finally:
        pass
    return data


main()
