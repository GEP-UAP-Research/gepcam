import cv2
import numpy as np
import subprocess
import sys
import time
import re
import os
import json
import gepcamlib as gepcam


Flag_Startup = True
Flag_AfterInit = True
Minimum_Read_time_otherwise_drop_frame_ns = 5000000

Flag_Display = True
if not os.environ.get('DISPLAY'):
    Flag_Display = False
if os.name == 'nt':
    Flag_Display = True
# Flag_Display = False

own_path, conf_path, log_path = gepcam.get_own_path_conf_path_log_path()
python_path = sys.executable
config = gepcam.load_config(conf_path + "gepcamconfig.json")['tracking']


p = subprocess.Popen([python_path, own_path + 'ptz-controller.py'],
                     shell=False, stdin=subprocess.PIPE, universal_newlines=True)

cap = cv2.VideoCapture(config['stream_config']['url'])  # open videostream
ret, frame = cap.read()


summary_mask = 0

while True:
    if gepcam.CheckFileHasNewModifyTime(conf_path + "gepcamconfig.json", conf_path + "mask.png") or Flag_Startup:
        print("startover")
        gepcam.runtime_stats('initiate new config')
        gepcam.load_config(conf_path + "gepcamconfig.json")['tracking']
        ptz_width = config['settings']['ptz_width']
        ptz_height = config['settings']['ptz_height']
        # if 0 -> will be calculated
        small_width = config['settings']['downscale_width']
        # 0 means no downzising
        small_height = config['settings']['downscale_height']
        skip_frames_between = config['settings']['skip_frames_between']

        width = int(cap.get(3))
        height = int(cap.get(4))
        print(f"Video input resolution: {width}*{height}")
        if small_height == 0 or small_height > height:
            small_height = height
        if small_width == 0:
            small_width = int((small_height / height) * width)
        print(f"Video processing resolution: {small_width}*{small_height}")
        small_to_ptz_width_divisor = small_width / ptz_width
        small_to_ptz_height_divisor = small_height / ptz_height
        DoDownsizing = True
        if small_height == height and small_width == width:
            DoDownsizing = False
        Flag_AfterInit = True

        if DoDownsizing:
            frame = cv2.resize(frame, (small_width, small_height))
        cv2.imwrite(conf_path + "prep_mask.png", frame)

        privacy_mask = cv2.imread(conf_path + "mask.png")
        privacy_mask = np.clip(privacy_mask, a_min=0, a_max=1) * 255
        privacy_mask = cv2.blur(privacy_mask, (1, 1))
        privacy_mask = cv2.resize(privacy_mask, (small_width, small_height))
        privacy_mask_gray = cv2.cvtColor(privacy_mask, cv2.COLOR_BGR2GRAY)

        p.stdin.write("started\n")
        if Flag_Display:
            cv2.imshow('frame', frame)
        skip_counter = skip_frames_between

        object_detector = cv2.createBackgroundSubtractorMOG2(
            history=config['settings']['object_detector_history'], varThreshold=config['settings']['object_detector_Threshold'])

    for i in range(200):
        time_before_read = time.time_ns()
        gepcam.runtime_stats('read frame')
        ret, frame = cap.read()
        if Minimum_Read_time_otherwise_drop_frame_ns > time.time_ns() - time_before_read:
            print("error: dropping frames to empty queue")
            drop_cnt = 1
            while Minimum_Read_time_otherwise_drop_frame_ns > time.time_ns() - time_before_read:
                gepcam.runtime_stats('dropping frames')
                time_before_read = time.time_ns()
                ret, frame = cap.read()
                drop_cnt += 1
            print(drop_cnt, "frames dropped")

        gepcam.runtime_stats('shorts')

        if skip_counter:
            skip_counter -= config['settings']['skip_frames_between']
            continue
        skip_counter = skip_frames_between
        if type(frame) != np.ndarray:
            print("error: frame missing")
            time.sleep(0.8)
            continue

        if DoDownsizing:
            gepcam.runtime_stats('Downsize')
            frame = cv2.resize(frame, (small_width, small_height))

        width = int(cap.get(3))
        height = int(cap.get(4))

        gepcam.runtime_stats('Object_Detector')
        mask = object_detector.apply(frame)

        if Flag_Startup:
            summary_mask = mask
        summary_mask = cv2.bitwise_or(mask, summary_mask)

        gepcam.runtime_stats('Privacy Mask')
        mask = cv2.bitwise_and(mask, privacy_mask_gray)

        gepcam.runtime_stats('fundContoures')
        contours, _ = cv2.findContours(
            mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_NONE)

        frame = cv2.bitwise_and(frame, privacy_mask)

        gepcam.runtime_stats('check all objects')
        if Flag_AfterInit:  # ignore objects on first frames after init or configchange
            if i > 10:
                Flag_AfterInit = False
            continue

        if len(contours) > 50:
            print("too much movements")
        else:
            for cnt in contours:
                area = cv2.contourArea(cnt)
                if area > 1:
                    #  cv2.drawContours(frame, [cnt], -1, (0, 255, 0), 2)
                    # print(cnt, area)
                    x, y, w, h = cv2.boundingRect(cnt)
                    cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0))
                    cmd = f"go{int(x/small_to_ptz_width_divisor)},{int(y/small_to_ptz_height_divisor)}\n"
                    p.stdin.write(cmd)
                    p.stdin.flush()
                    print(cmd, end='')

        if Flag_Display:
            gepcam.runtime_stats('imshow')
            cv2.imshow('frame', frame)
            cv2.imshow('mask', summary_mask)
            gepcam.runtime_stats('wait')
            if cv2.waitKey(1) == ord('q'):
                cv2.destroyAllWindows()
                p.stdin.close()
                p.terminate()
                rc = p.wait()
                sys.exit()
        gepcam.runtime_stats('next')

    print("color average: ", np.average(frame))
    Flag_Startup = False
