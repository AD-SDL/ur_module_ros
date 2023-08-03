from time import sleep
from copy import deepcopy
from typing import Optional, Tuple

import cv2
import pyrealsense2 as realsense


from transforms3d import euler, quaternions
from math import degrees

import torch
from torchvision.transforms import functional as F
from ultralytics import YOLO
import numpy as np

from robotiq_gripper_driver import RobotiqGripper
from urx import Robot


class CameraController:
    """
    CameraController is a class created for UR robots to utilize Intel Realsense D400 series cameras.
    It can detect objects based on a pre-trained YOLO model with 5 different labwares, and plan
    a robot trajectory to pick up the objects based on distance and object reference frame information obtained from the camera.
    """

    def __init__(self, robot_ip: str, ur_connection: Optional[Robot], target_object: Optional[str]) -> None:
        """
        Constructor for the CameraController class.

        Args:
            robot_IP (str): The IP address of the robot.
            ur_connection (Robot): The connection to the robot (urx.Robot instance), defaults to None.
            target_object (str): The target object for YOLO model, defaults to None.

        Raises:
            ValueError: Raised when ur_connection or target_object is not provided.
            ValueError: Raised when target_object category doesn't exist in the trained model class list.
        """
        if ur_connection is None:
            raise ValueError("UR connection is not provided!")
        if target_object is None:
            raise ValueError("Target object for YOLO model is not provided")

        self.ur_connection = ur_connection
        self.target_object = target_object.lower()
        self.model = None
        self.object_distance = 0
        self.object_reference_frame = None
        self.gripper = RobotiqGripper()

        self.MOVE_ACC = 0.5
        self.MOVE_VEL = 0.5
        self.CLASS_NAMES = ['deepwellplates', 'tipboxes', 'hammers', 'wellplates', 'wellplate_lids']

        self._validate_target_object()
        self._connect_to_gripper(robot_ip)

    def _validate_target_object(self):
        if self.target_object not in self.CLASS_NAMES:
            raise ValueError(f"Target object category '{self.target_object}' doesn't exist in the trained model class list")

    def _connect_to_gripper(self, robot_ip: str):
        print('Connecting to gripper...')
        self.gripper.connect(robot_ip, 63352)
        self.gripper.activate()
        self.gripper.move_and_wait_for_pos(0, 150, 0)

    def start_camera_stream(self) -> None:
        self.pipeline = realsense.pipeline()
        config = realsense.config()
        config.enable_stream(realsense.stream.color, 640, 480, realsense.format.rgb8, 30)
        config.enable_stream(realsense.stream.depth, 640, 480, realsense.format.z16, 30)
        self.pipeline.start(config)

    def capture_image(self) -> Tuple[np.array, 'realsense.frame', 'realsense.frame']:
        """
        Capture a new image from the camera.

        Returns:
            Tuple[np.array, 'realsense.frame', 'realsense.frame']: The captured image and the color and depth frames.
        """
        frames = self.pipeline.wait_for_frames()
        color_frame = frames.get_color_frame()
        depth_frame = frames.get_depth_frame()
        img = np.asanyarray(color_frame.get_data())
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        img = cv2.resize(img, (640, 480))

        return img, color_frame, depth_frame

    def load_yolo_model(self, model_path: Optional[str] = None):
        """
        Loads the trained YOLO model.

        Args:
            model_path (Optional[str]): Path to the model file, defaults to None.
        """
        model_file_path = model_path if model_path else "best.pt"
        # Load the trained YOLO model
        self.model = YOLO(model_file_path)

    def align_object(self) -> Optional[Tuple[int, int]]:
        """
        Aligns the robot arm to the object's center until the center is detected.

        Returns:
            Optional[Tuple[int, int]]: The x and y coordinates of the object's center if detected, otherwise None.
        """
        object_center = None
        while object_center is None:
            img, color_frame, depth_frame = self.capture_image()

            if not color_frame or not depth_frame or not img:
                return None

            boxes = self.model(img)[0].boxes
            object_center = self._get_object_center(boxes)

        return object_center

    def _get_object_center(self, boxes) -> Optional[Tuple[int, int]]:
        """
        Calculates the center of the first detected object if any objects are detected.

        Args:
            boxes (List[Box]): A list of detected objects represented as boxes.

        Returns:
            Optional[Tuple[int, int]]: The x and y coordinates of the first object's center if detected, otherwise None.
        """
        if len(boxes) > 0:
            xmin, ymin, xmax, ymax = boxes[0].xyxy[0]
            center_x = int((xmin + xmax) / 2)
            center_y = int((ymin + ymax) / 2)
            return center_x, center_y
        else:
            return None
        
    def _calculate_object_reference_frame(self, depth_frame: 'realsense.frame', center_x: int, center_y: int):
        """
        Get the object reference frame from the depth frame and center of the bounding box.

        Args:
            depth_frame (frame): Depth frame of the image.
            center_x (int): X coordinate of the object center.
            center_y (int): Y coordinate of the object center.
        """

        # Get the intrinsic parameters of the depth frame
        depth_intrin = depth_frame.profile.as_video_stream_profile().intrinsics
        # Use the depth value and the center of the bounding box to get the 3D coordinates of the object
        self.object_reference_frame = realsense.rs2_deproject_pixel_to_point(depth_intrin, [center_x, center_y], self.object_distance)
    
    @staticmethod
    def _calculate_box_center(xmin: float, xmax: float, ymin: float, ymax: float) -> Tuple[int, int]:
        return int((xmin + xmax) / 2), int((ymin + ymax) / 2)

    @staticmethod
    def _draw_on_image(img: np.array, xmin: float, ymin: float, xmax: float, ymax: float, center_x: int, center_y: int, distance: float) -> None:
        cv2.rectangle(img, (int(xmin), int(ymin)), (int(xmax), int(ymax)), (0, 255, 0), 2)
        cv2.putText(img, f"{distance:.2f}m", (int(xmin), int(ymin) - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
        cv2.circle(img, (center_x, center_y), 5, (0, 0, 255), -1)
        cv2.circle(img, (640/2, 480/2), 5, (0, 0, 255), -1)

    def move_to_object(self):
        """Method to move the robot arm to the object"""

        # Extract the x, y, and z coordinates
        trans_x = self.object_reference_frame[0]
        trans_y = self.object_reference_frame[1]
        trans_z = self.object_reference_frame[2]

        # Print out the object's 3D coordinates
        print("Object XYZ: " + str(self.object_reference_frame))

        if trans_z != 0:
            # Move the robot's tool (e.g. a gripper) to be centered over the object in the x-y plane
            self.ur_connection.translate_tool([-trans_x, -trans_y, 0], acc=self.MOVE_ACC, vel=self.MOVE_VEL)
    
    def _detect_and_move_to_object(self, img: np.array, depth_frame: 'realsense.frame'):
        """
        This function takes an image and a depth frame as input, runs the object detection model on the image,
        and checks the classes of detected objects. If the class of a detected object matches the target object,
        it calculates the center of this object, gets its distance, and draws on the image. Then, it calculates 
        the object reference frame based on the center of the object and depth frame and commands the robot to 
        move to this object. If the target object is not found in the image, it logs a message.

        Args:
            img (np.array): The image from the camera.
            depth_frame ('realsense.frame'): The depth frame from the camera.
        """

        boxes, classes = self.model(img)[0].boxes, self.model(img)[0].classes
        for (xmin, ymin, xmax, ymax), cls in zip(boxes.xyxy, classes):
            if cls == self.target_object:
                center_x, center_y = self._calculate_box_center(xmin, xmax, ymin, ymax)
                self.object_distance = depth_frame.get_distance(center_x, center_y)

                self._draw_on_image(img, xmin, ymin, xmax, ymax, center_x, center_y, self.object_distance)

                self._calculate_object_reference_frame(depth_frame, center_x, center_y)
                self.move_to_object()
                break
        else:
            print(f'Target object {self.target_object} not found in the frame.')

    def center_the_gripper(self, object_center: Optional[Tuple[int, int]] = None):
        """
        Method to center the robot gripper over the detected object in its field of view.
        
        Args:
            object_center (tuple): Optional; pre-calculated object center coordinates.

        Returns:
            None
        """

        # If no object_center is provided, the function terminates early
        if object_center is None:
            return
        
        # Capture image and get color and depth frames
        img, color_frame, depth_frame = self.capture_image()
        if not color_frame or not depth_frame or not img:
            raise ValueError("Could not capture image or retrieve color/depth frames")

        self._detect_and_move_to_object(img, depth_frame)

