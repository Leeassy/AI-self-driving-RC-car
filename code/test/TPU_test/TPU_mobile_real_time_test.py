import argparse
import cv2
import os
import time

from pycoral.adapters.common import input_size
from pycoral.adapters.detect import get_objects
from pycoral.utils.dataset import read_label_file
from pycoral.utils.edgetpu import make_interpreter
from pycoral.utils.edgetpu import run_inference
 
def main():
    
    model = '/home/pi/AI-self-driving-RC-car/code/test/data/mobilenet_v2_haram.tflite'
    labels = '/home/pi/AI-self-driving-RC-car/code/test/data/labelmap_haram.txt'
    top_k = 10
    threshold = 0.1

    print('Loading {} with {} labels.'.format(model, labels))
    interpreter = make_interpreter(model)
    interpreter.allocate_tensors()
    labels = read_label_file(labels)
    inference_size = input_size(interpreter)
 
    #cap = cv2.VideoCapture(args.camera_idx)
    cap = cv2.VideoCapture('/home/pi/AI-self-driving-RC-car/code/test/data/tmp/object2.avi')

    while cap.isOpened():
        start_time = time.time()
        try:
            ret, frame = cap.read()
            if not ret:
                break

            cv2_im = frame
    
            cv2_im_rgb = cv2.cvtColor(cv2_im, cv2.COLOR_BGR2RGB)
            cv2_im_rgb = cv2.resize(cv2_im_rgb, inference_size)
            run_inference(interpreter, cv2_im_rgb.tobytes())
            objs = get_objects(interpreter, threshold)[:top_k]
            cv2_im = append_objs_to_img(cv2_im, inference_size, objs, labels)

            # FPS
            elapse_time = time.time() - start_time
            fps = 1/elapse_time
            
            cv2.putText(cv2_im, f"FPS: {fps:.2f}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.imshow('frame', cv2_im)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                cap.release()
                cv2.destroyAllWindows()
                break

        except Exception as e:
                print('Exception:', e)
                print('fail')
                break
        
    
 
def append_objs_to_img(cv2_im, inference_size, objs, labels):
    height, width, channels = cv2_im.shape
    scale_x, scale_y = width / inference_size[0], height / inference_size[1]
    for obj in objs:
        bbox = obj.bbox.scale(scale_x, scale_y)
        x0, y0 = int(bbox.xmin), int(bbox.ymin)
        x1, y1 = int(bbox.xmax), int(bbox.ymax)
 
        percent = int(100 * obj.score)
        label = '{}% {}'.format(percent, labels.get(obj.id, obj.id))
 
        cv2_im = cv2.rectangle(cv2_im, (x0, y0), (x1, y1), (0, 255, 0), 2)
        cv2_im = cv2.putText(cv2_im, label, (x0, y0+30),
                             cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 0, 0), 2)
    return cv2_im
 
if __name__ == '__main__':
    main()