import cv2
import numpy as np
import logging
import math
import datetime
import sys
import os

_SHOW_IMAGE = False


class HandCodedLaneFollower(object):

    def __init__(self, car=None):
        logging.info('Creating a HandCodedLaneFollower...')
        self.car = car
        self.curr_steering_angle = 90

    def follow_lane(self, frame):

        lane_lines, lane_lines_image = detect_lane(frame)
        final_frame = self.steer(lane_lines_image, lane_lines)

        return final_frame

    def steer(self, lane_lines_image, lane_lines):
        logging.debug('steering...')
        if len(lane_lines) == 0:
            logging.error('No lane lines detected, nothing to do.')
            return lane_lines_image

        new_steering_angle = compute_steering_angle(lane_lines_image, lane_lines)
        self.curr_steering_angle = stabilize_steering_angle(self.curr_steering_angle, new_steering_angle, len(lane_lines))

        if self.car is not None:
            self.car.front_wheels.turn(self.curr_steering_angle)
        curr_heading_image = display_heading_line(lane_lines_image, self.curr_steering_angle)
        # show_image("heading", curr_heading_image)

        return curr_heading_image


############################
# Frame processing steps
############################
def detect_lane(frame):
    logging.debug('detecting lane lines...')

    cropped_edges = detect_edges(frame)
   

    line_segments = detect_line_segments(cropped_edges)
    # line_segment_image = display_lines(frame, line_segments)
    

    lane_lines = average_slope_intercept(cropped_edges, line_segments)
    lane_lines_image = display_lines(frame, lane_lines)
    # print("display", lane_lines_image)


    return lane_lines, lane_lines_image


def detect_edges(frame):
    
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    
    # crop image
    # height, width = gray.shape
     
    # mask = np.zeros((height, width))
    
    # polygon = np.array([[
    # (0, 0),
    # (0, height * 7/10),
    # (width , height * 7/10),
    # (width , 0),
    # ]], np.int32)
    
    # cropped_image = cv2.fillPoly(mask, polygon, (0,0,0)) 
    cropped_image = gray[336:480,0:640]

    
    # masked_image = cv2.bitwise_and(frame, cropped_image)
    
    img_blurred = cv2.GaussianBlur(cropped_image, ksize = (21,21), sigmaX= 0)
    
    cropped_edges = cv2.adaptiveThreshold(
    img_blurred,
    maxValue = 255.0 ,
    adaptiveMethod = cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
    thresholdType = cv2.THRESH_BINARY_INV,
    blockSize = 23, # block size와 c의 값을 이용하여 controus의 영역을 강조함.
    C = 7)
    
    return cropped_edges



def detect_line_segments(cropped_edges):
    # tuning min_threshold, minLineLength, maxLineGap is a trial and error process by hand
    rho = 10  # precision in pixel, i.e. 1 pixel
    angle = np.pi / 180  # degree in radian, i.e. 1 degree
    min_threshold = 10  # minimal of votes
    line_segments = cv2.HoughLinesP(cropped_edges, rho, angle, min_threshold, np.array([]), minLineLength=8,
                                    maxLineGap=3)

    # if line_segments is not None:
    #     for line_segment in line_segments:
    #         logging.debug('detected line_segment:')
    #         logging.debug("%s of length %s" % (line_segment, length_of_line_segment(line_segment[0])))

    return line_segments


def average_slope_intercept(cropped_edges, line_segments):
    """
    This function combines line segments into one or two lane lines
    If all line slopes are < 0: then we only have detected left lane
    If all line slopes are > 0: then we only have detected right lane
    """
    lane_lines = []
    if line_segments is None:
        logging.info('No line_segment segments detected')
        return lane_lines

    height, width= cropped_edges.shape
    left_fit = []
    right_fit = []

    boundary = 1/3
    left_region_boundary = width * (1 - boundary)  # left lane line segment should be on left 2/3 of the screen
    right_region_boundary = width * boundary # right lane line segment should be on left 2/3 of the screen

    for line_segment in line_segments:
        for x1, y1, x2, y2 in line_segment:
            if x1 == x2:
                logging.info('skipping vertical line segment (slope=inf): %s' % line_segment)
                continue
            if abs(y1-y2) > 30:
                fit = np.polyfit((x1, x2), (y1, y2), 1)
                slope = fit[0]
                intercept = fit[1]
                if slope < 0:
                    if x1 < left_region_boundary and x2 < left_region_boundary:
                        left_fit.append((slope, intercept))
                else:
                    if x1 > right_region_boundary and x2 > right_region_boundary:
                        right_fit.append((slope, intercept))

    left_fit_average = np.average(left_fit, axis=0)
    if len(left_fit) > 0:
        lane_lines.append(make_points(cropped_edges, left_fit_average))

    right_fit_average = np.average(right_fit, axis=0)
    if len(right_fit) > 0:
        lane_lines.append(make_points(cropped_edges, right_fit_average))

    logging.debug('lane lines: %s' % lane_lines)  # [[[316, 720, 484, 432]], [[1009, 720, 718, 432]]]

    return lane_lines


def compute_steering_angle(frame, lane_lines):
    """ Find the steering angle based on lane line coordinate
        We assume that camera is calibrated to point to dead center
    """
    if len(lane_lines) == 0:
        logging.info('No lane lines detected, do nothing')
        return -90

    height, width, _ = frame.shape
    if len(lane_lines) == 1:
        logging.debug('Only detected one lane line, just follow it. %s' % lane_lines[0])
        x1, _, x2, _ = lane_lines[0][0]
        x_offset = x2 - x1
    else:
        _, _, left_x2, _ = lane_lines[0][0]
        _, _, right_x2, _ = lane_lines[1][0]
        camera_mid_offset_percent = 0.0 # 0.0 means car pointing to center, -0.03: car is centered to left, +0.03 means car pointing to right
        mid = int(width / 2 * (1 + camera_mid_offset_percent))
        x_offset = (left_x2 + right_x2) / 2 - mid

    # find the steering angle, which is angle between navigation direction to end of center line
    y_offset = int(height / 2)

    angle_to_mid_radian = math.atan(x_offset / y_offset)  # angle (in radian) to center vertical line
    angle_to_mid_deg = int(angle_to_mid_radian * 180.0 / math.pi)  # angle (in degrees) to center vertical line
    steering_angle = angle_to_mid_deg + 90  # this is the steering angle needed by picar front wheel

    logging.debug('new steering angle: %s' % steering_angle)
    return steering_angle


def stabilize_steering_angle(curr_steering_angle, new_steering_angle, num_of_lane_lines, max_angle_deviation_two_lines=5, max_angle_deviation_one_lane=1):
    """
    Using last steering angle to stabilize the steering angle
    This can be improved to use last N angles, etc
    if new angle is too different from current angle, only turn by max_angle_deviation degrees
    """
    if num_of_lane_lines == 2 :
        # if both lane lines detected, then we can deviate more
        max_angle_deviation = max_angle_deviation_two_lines
    else :
        # if only one lane detected, don't deviate too much
        max_angle_deviation = max_angle_deviation_one_lane
    
    angle_deviation = new_steering_angle - curr_steering_angle
    if abs(angle_deviation) > max_angle_deviation:
        stabilized_steering_angle = int(curr_steering_angle
                                        + max_angle_deviation * angle_deviation / abs(angle_deviation))
    else:
        stabilized_steering_angle = new_steering_angle
    logging.info('Proposed angle: %s, stabilized angle: %s' % (new_steering_angle, stabilized_steering_angle))
    return stabilized_steering_angle


############################
# Utility Functions
############################
def display_lines(frame, lines, line_color=(0, 255, 0), line_width=10):
    line_image = np.zeros_like(frame)
    if lines is not None:
        for line in lines:
            for x1, y1, x2, y2 in line:
                if abs(y1-y2) > 10:
                    cv2.line(line_image, (x1, y1+336), (x2, y2+336), line_color, line_width)
    line_image = cv2.addWeighted(frame, 0.8, line_image, 1, 1)
    
    return line_image


def display_heading_line(frame, steering_angle, line_color=(0, 0, 255), line_width=5, ):
    heading_image = np.zeros_like(frame)
    height, width, _ = frame.shape

    # figure out the heading line from steering angle
    # heading line (x1,y1) is always center bottom of the screen
    # (x2, y2) requires a bit of trigonometry

    # Note: the steering angle of:
    # 0-89 degree: turn left
    # 90 degree: going straight
    # 91-180 degree: turn right 
    steering_angle_radian = steering_angle / 180.0 * math.pi
    x1 = int(width / 2)
    y1 = height
    x2 = int(x1 - height / 2 / math.tan(steering_angle_radian))
    y2 = int(height / 2)

    cv2.line(heading_image, (x1, y1), (x2, y2), line_color, line_width)
    heading_image = cv2.addWeighted(frame, 0.8, heading_image, 1, 1)

    return heading_image


def length_of_line_segment(line):
    x1, y1, x2, y2 = line
    return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)


def show_image(title, frame, show=_SHOW_IMAGE):
    if show:
        cv2.imshow(title, frame)


def make_points(frame, line):
    height, width = frame.shape
    slope, intercept = line
    y1 = height  # bottom of the frame
    y2 = int(y1 * 1 / 2)  # make points from middle of the frame down

    # bound the coordinates within the frame
    x1 = max(-width, min(2 * width, int((y1 - intercept) / slope)))
    x2 = max(-width, min(2 * width, int((y2 - intercept) / slope)))
    return [[x1, y1, x2, y2]]


############################
# Test Functions
############################
def test_photo(file):
    land_follower = HandCodedLaneFollower()
    frame = cv2.imread(file)
    combo_image = land_follower.follow_lane(frame)
    show_image('final', combo_image, True)
    cv2.waitKey(0)
    cv2.destroyAllWindows()


def test_video(video_file):
    lane_follower = HandCodedLaneFollower()
    cap = cv2.VideoCapture(video_file)
    os.makedirs("frame_image", exist_ok=True)
    folder_name = video_file.split(".")[1].split("/")[1]
    os.makedirs(f"./frame_image/{folder_name}", exist_ok=True)
    
    # # skip first second of video.
    # for i in range(3):
    #     _, frame = cap.read()

    video_type = cv2.VideoWriter_fourcc(*'mp4v')
    video_overlay = cv2.VideoWriter("%s_overlay.mp4" % (video_file), video_type, 20.0, (320, 240))
    try:
        i = 0
        while cap.isOpened():
            _, frame = cap.read()
            
            print('frame %s' % i )
            combo_image= lane_follower.follow_lane(frame)
            
            cv2.imwrite("./frame_image/%s/%s_%03d_%03d.png" % (folder_name,folder_name, i, lane_follower.curr_steering_angle), frame)
            
            cv2.imwrite("./frame_image/%s/%s_overlay_%03d.png" % (folder_name,folder_name, i), combo_image)
            video_overlay.write(combo_image)
            cv2.imshow("Road with Lane line", combo_image)

            i += 1
            if cv2.waitKey(10) & 0xFF == ord('q'):
                break
    finally:
        cap.release()
        video_overlay.release()
        cv2.destroyAllWindows()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    test_video("./RC_car_230822.mp4")
    # test_photo("./frame_image/RC_car_230822/RC_car_230822_305_086.png")
    #test_photo(sys.argv[1])
    #test_video(sys.argv[1])