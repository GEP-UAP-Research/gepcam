import argparse
import json
import re
import time
import datetime
import os
import sys
import subprocess
import gepcamlib as gepcam

own_path, conf_path, log_path = gepcam.get_own_path_conf_path_log_path()

timestamp_from_last_action = datetime.datetime.now().timestamp()


parser = argparse.ArgumentParser()
parser.add_argument("--cam", help="cam name", required=True)
args = parser.parse_args()
cam_name = args.cam
own_path, conf_path, log_path = gepcam.get_own_path_conf_path_log_path()
config = gepcam.load_config(conf_path + "gepcamconfig.json")


def main():
    if os.name == 'nt':
        ffmpeg_Filename = own_path + "ffmpeg.exe"
    else:
        ffmpeg_Filename = "/usr/bin/ffmpeg"

    config = gepcam.load_config(conf_path + "gepcamconfig.json")["recording"]

    gepcam.fatal_if_file_not_exist(ffmpeg_Filename)

    if not cam_name in config:
        Message("cam name " + cam_name + " not found in config")
        sys.exit(1)

    config = config[cam_name]

    for value in ['name', 'stream_url', 'store_path']:
        if not value in config:
            Message(f"Value for {value} not found in config.", fatal=True)
            sys.exit()
        if config[value] == '':
            Message(f"Value for {value} is empty in config.", fatal=True)
            sys.exit()
    if config['store_path'][-1] != '/':
        config['store_path'] = config['store_path'] + '/'
    path = config['store_path']
    gepcam.fatal_if_dir_not_exist(path)
    temp_path = path + 'temp/'
    video_path = path + 'video/'
    os.makedirs(temp_path, exist_ok=True)
    os.makedirs(video_path, exist_ok=True)

    p = start_ffmpeg(config=config, temp_path=temp_path,
                     ffmpeg_path=ffmpeg_Filename, output_path=temp_path)

    while True:
        if config['max_store_diskspace']:
            if config['max_store_diskspace'] > 0:
                delete_file_to_keep_under_max_space(
                    video_path=video_path, max_space_byte=config['max_store_diskspace'] * 1024 * 1024)
                remove_empty_directorys(video_path)

        for i in range(100):
            move_video_files(temp_path=temp_path,
                             video_path=video_path, camera_name=config['name'])
            if datetime.datetime.now().timestamp() - timestamp_from_last_action > 61:
                Message("video stream dead, try restart")
                stop_ffmpeg(p)
                p = start_ffmpeg(config=config, temp_path=temp_path,
                                 ffmpeg_path=ffmpeg_Filename, output_path=temp_path)
                time.sleep(11)
            time.sleep(8)


def delete_file_to_keep_under_max_space(video_path: str, max_space_byte: int):
    allfiles = get_video_path_files_and_sizes(video_path=video_path)
    space_byte = 0
    for file in allfiles:
        space_byte += allfiles[file]
    exceeding_space = space_byte - max_space_byte
    if exceeding_space > 0:
        for file in allfiles:
            Message("delete file " + file)
            os.remove(file)
            exceeding_space -= allfiles[file]
            if exceeding_space < 1:
                break


def get_video_path_files_and_sizes(video_path: str) -> dict:
    allfiles = dict()
    for datefolder in os.listdir(video_path):
        if os.path.isdir(video_path + datefolder):
            for hourfolder in os.listdir(video_path + datefolder):
                if os.path.isdir(video_path + datefolder + '/' + hourfolder):
                    for file in os.listdir(video_path + datefolder + '/' + hourfolder):
                        allfiles[video_path + datefolder + '/' + hourfolder + '/' + file] = os.path.getsize(
                            video_path + datefolder + '/' + hourfolder + '/' + file)
    sorted_allfiles = dict()
    for file in sorted(allfiles):
        sorted_allfiles[file] = allfiles[file]
    return sorted_allfiles


def move_video_files(temp_path: str, video_path: str, camera_name: str):
    files_in_temp = sorted(os.listdir(temp_path), reverse=True)
    if len(files_in_temp) > 1:
        for file in files_in_temp[1:]:
            if re.search("\.mp4$", file):
                filedate = format_date(
                    get_file_creation_time(temp_path + file))
                long_videopath = video_path + \
                    filedate[:10] + '/' + filedate[11:13] + '/'
                new_filename = camera_name + '_' + filedate + '.mp4'
                new_filename = re.sub(":", "", new_filename)
                os.makedirs(long_videopath, exist_ok=True)
                os.rename(temp_path + file, long_videopath + new_filename)
                Message(
                    f"moved finished videofile {temp_path + file} {long_videopath + new_filename}")
                VideoIsAlive()


def format_date(timestamp: float) -> str:
    text = datetime.datetime.fromtimestamp(
        timestamp).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    text = text[:10] + '_' + text[11:]
    return text


def VideoIsAlive():
    global timestamp_from_last_action
    timestamp_from_last_action = datetime.datetime.now().timestamp()


def start_ffmpeg(config: dict, temp_path: str, ffmpeg_path: str, output_path: str):
    parameter = [ffmpeg_path, '-rtsp_transport', 'tcp', '-reorder_queue_size', '60', '-buffer_size', '2000000', '-i', config['stream_url'], '-map', '0', '-c', 'copy', '-acodec',
                 'copy', '-vcodec', 'copy', '-an', '-f', 'segment', '-segment_atclocktime', '1', '-segment_time', '60', '-segment_format', 'mp4', '-reset_timestamps', '1', '-strftime', '1', output_path + 'record-cam1-%Y-%m-%d_%H-%M-%S.mp4']
    return (subprocess.Popen(parameter, shell=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))


def stop_ffmpeg(p: subprocess.Popen):
    if p.returncode == None:
        #    if os.name == 'nt':
        #       p.send_signal(signal.CTRL_C_EVENT)
        #  else:
        #     p.send_signal(signal.SIGINT)
        p.terminate()
       # p.wait(timeout=5)
        if p.returncode == None:
            p.kill()
            time.sleep(3)
        rc = p.returncode
        print(rc)
        p.wait()


def clean_temp_path(temp_path: str):
    if len(temp_path) > 2:
        for file in os.listdir(temp_path):
            if file[0] != '.':
                os.remove(temp_path + file)


def remove_empty_directorys(path: str):
    for entry in os.listdir(path):
        if os.path.isdir(path + entry):
            remove_empty_directorys(path + entry + '/')
    if len(os.listdir(path)) == 0:
        print("delete " + path)
        os.rmdir(path)


def Message(text: str, error=False, fatal=False):
    if fatal:
        text = f"FATAL ERROR: {text}"
    elif error:
        text = f"ERROR: {text}"
    sys.stderr.write(
        '[' + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] + '] ' + text + "\r\n")
    return


def get_file_creation_time(filename: str) -> float:
    ctime = os.path.getctime(filename)
    if os.name != 'nt':  # workaround to get the right file creation time at linux
        result = subprocess.run(
            ['stat', '--format', '%.W', filename], stdout=subprocess.PIPE)
        ctime = result.stdout.decode(encoding="utf-8")
        ctime = re.sub(",", ".", ctime)
        ctime = float(re.sub(f"\n", "", ctime))
    return ctime


main()
