################################################
# Descriptions
################################################

'''
node subscribes to camera data from rgb_camera topic
node computes the bounding box via red colour mask
node computes the distances and sends vision_pose and setpoint_position 
accordingly to move the amount required
'''


################################################
# Imports and Setup
################################################

# ros imports
import rclpy
from rclpy.node import Node
from std_srvs.srv import Trigger

# ros imports for realsense and mavros
from geometry_msgs.msg import PoseArray, PoseStamped, Point, Quaternion
from nav_msgs.msg import Odometry
from sensor_msgs.msg import Image

# reliability imports
from rclpy.qos import QoSProfile, QoSReliabilityPolicy
qos_profile = QoSProfile(reliability=QoSReliabilityPolicy.BEST_EFFORT, depth=1)

# image related
import cv2
from cv_bridge import CvBridge
import numpy as np
import time
import os

bridge = CvBridge()

################################################
# Class Nodes
################################################


class DroneControlNode(Node):

    def __init__(self, test_type):
        super().__init__('drone_control_node') 

        ###############
        # SERVICE CALLS

        self.srv_launch = self.create_service(Trigger, 'rob498_drone_1/comm/launch', self.callback_launch)
        self.srv_test = self.create_service(Trigger, 'rob498_drone_1/comm/test', self.callback_test)
        self.srv_land = self.create_service(Trigger, 'rob498_drone_1/comm/land', self.callback_land)
        self.srv_abort = self.create_service(Trigger, 'rob498_drone_1/comm/abort', self.callback_abort)
        print('services created')

        ###########################
        # USER CONTROLLED VARIABLES

        # tuning parameters
        self.desired_flight_height = 2.3        # height we fly at
        self.max_searching_height = 2.5         # safety on top height
        self.square_size = 3.0                  # safety on the side movement
        self.init_x, self.init_y = 2.0, 1.8     # where we start the drone
        
        # movement parameters 
        self.frame_pixel_tol = 5                # how to center to only hover
        self.Kp = 0.020 #0.0141                 # proportional gain
        self.Kd = 0.002 #0.001                  # derivative gain

        # colour filter settings
        target_rgb=(200, 29, 32)  # target color to track, in RGB format (ex: red)
        hue_tol=10                # tolerance range for hue in HSV space (large = less strict)
        sat_tol=100               # tolerance for saturation (large = more dull and bright)
        val_tol=100               # tolerance for value/brightness (large = more lighting conds)

        ###########################
        # OTHER SETUP (DON'T TOUCH)

        # init the colour filter
        self.set_target_color(target_rgb, hue_tol, sat_tol, val_tol)

        # safety net on the ball
        self.bounds = {"x_min": -1*self.square_size, "x_max": self.square_size, "y_min": -1*self.square_size, "y_max": self.square_size, "z_min": 0.0, "z_max": self.max_searching_height}

        # for vision_pose to know where it is
        self.position = Point()
        self.orientation = Quaternion()
        self.timestamp = None
        self.frame_id = "map"

        # for setpoint_vision to know where to go
        self.set_position = Point()
        self.set_orientation = Quaternion()
        self.set_orientation.w = -1.0

        # booleans for enabling testing
        self.testing = False
        self.t1 = time.time()
        self.t2 = time.time()

        # camera parameters
        self.REAL_DIAMETER_MM = 42.67       # Standard golf ball diameter in mm
        self.FOCAL_LENGTH_MM = 26           # iPhone 14 Plus main camera focal length in mm
        self.SENSOR_WIDTH_MM = 4.93         # Approximate sensor size: 5.095 mm (H) × 4.930 mm (W)
        self.DOWN_SAMPLE_FACTOR = 4         # Downsample factor used in calculation

        # frame parameters (updated in first frame)
        self.frame_width, self.frame_height = None, None
        self.camera_frame_center = None
        self.FOCAL_LENGTH_PIXELS = None

        # derivative parameters
        self.prev_p_error_x = 0
        self.prev_p_error_y = 0
        self.prev_time = self.get_clock().now()
        
        ############################
        # SUBSCRIBER/PUBLISHER SETUP

        # ROS subscriber to RGB camera messages
        self.camera_subscriber = self.create_subscription(Image, '/camera/image_raw', self.frame_input_callback, 1)
        self.get_logger().info('Subscribed to Camera Input!')
        self.br = CvBridge()

        self.image_publisher = self.create_publisher(Image, '/camera/segmented', 1)
        self.get_logger().info('Publishing to Processed Camera Output!')

        # subscriber to RealSense or Vicon pose data
        if test_type == "realsense":
            # Subscriber to RealSense pose data
            self.realsense_subscriber = self.create_subscription(Odometry, '/camera/pose/sample', self.realsense_callback, qos_profile)
            self.get_logger().info('Subscribing to RealSense!')
        else: 
            # Subscriber to Vicon pose data
            self.vicon_subscriber = self.create_subscription(PoseStamped, '/vicon/ROB498_Drone/ROB498_Drone', self.vicon_callback, 1)
            self.get_logger().info('Subscribing to Vicon!')
        
        # publisher for VisionPose topic
        self.vision_pose_publisher = self.create_publisher(PoseStamped, '/mavros/vision_pose/pose', 1)
        self.get_logger().info('Publishing to VisionPose')

        # publisher for SetPoint topic
        self.setpoint_publisher = self.create_publisher(PoseStamped, '/mavros/setpoint_position/local', qos_profile)
        self.get_logger().info('Publishing to SetPoint')

        # statement to end the inits
        self.get_logger().info('Nodes All Setup and Started!')

    ################################################
    # SERVICE CALLS 
    ################################################

    def callback_launch(self, request, response):
        print('Launch Requested. Drone takes off to find the golf ball and hover overtop.')
        self.launching_procedure()
        return response

    def callback_test(self, request, response):
        print('Test Requested. Drone is read_error_y to follow whever the ball may go.')
        self.testing_procedure()
        return response
        
    def callback_land(self, request, response):
        print('Land Requested. Drone will return to starting position where the humans are.')
        self.landing_procedure()
        return response

    def callback_abort(self, request, response):
        print('Abort Requested. Drone will land immediately due to safety considerations.')
        self.abort_procedure()
        return response

    ################################################
    # SERVICE FUNCTIONS
    ################################################

    def launching_procedure(self):
        # start by taking off and flying higher to search for the ball
        # continuously search until a valid center point is found
        # once the ball is detected, lower the drone to the desired height
        # center the drone over the ball
        # capture the current position for landing
        self.set_pose_initial()
        self.set_position.z = self.desired_flight_height
        return

    def testing_procedure(self):
        # set the drone to continuously hover and track the ball
        self.testing = True
        return

    def landing_procedure(self):
        # drone will land at the captured position (back where the people are)
        # also at a lower height
        self.testing = False
        self.set_position.z = 0.1
        return

    def abort_procedure(self):
        # safety land will just immediately lower the drone
        self.testing = False
        self.set_position.z = 0.0
        response.success = True
        response.message = "Success"

    ################################################
    # CALLBACKS
    ################################################

    def realsense_callback(self, msg):
        # get the info
        self.position = msg.pose.pose.position
        self.orientation = msg.pose.pose.orientation
        self.timestamp = self.get_clock().now().to_msg()
        # frame conversion
        self.orientation.x *= -1
        self.orientation.y *= -1
        self.orientation.z *= -1
        self.orientation.w *= -1
        # WRITE BOTH IMMEDIATELY
        self.send_vision_pose()
        self.send_setpoint()

    def vicon_callback(self, msg):
        # get the info
        self.position = msg.pose.position
        self.orientation = msg.pose.orientation
        self.timestamp = self.get_clock().now().to_msg()
        # frame conversion
        self.orientation.x *= -1
        self.orientation.y *= -1
        self.orientation.z *= -1
        self.orientation.w *= -1
        # WRITE BOTH IMMEDIATELY
        self.send_vision_pose()
        self.send_setpoint()

    def send_vision_pose(self):
        # Create a new PoseStamped message to publish to vision_pose topic
        vision_pose_msg = PoseStamped()
        vision_pose_msg.header.stamp = self.timestamp
        vision_pose_msg.header.frame_id = self.frame_id
        vision_pose_msg.pose.position = self.position
        vision_pose_msg.pose.orientation = self.orientation
        # Publish the message to the /mavros/vision_pose/pose topic
        self.vision_pose_publisher.publish(vision_pose_msg)

    def clamp_position(self, position):
        # Apply safety bounds to the setpoints so the drone never tries to go outside
        position.x = max(self.bounds["x_min"], min(position.x, self.bounds["x_max"]))
        position.y = max(self.bounds["y_min"], min(position.y, self.bounds["y_max"]))
        position.z = max(self.bounds["z_min"], min(position.z, self.bounds["z_max"]))
        return position

    def send_setpoint(self):
        # Create a new PoseStamped message to publish to setpoint topic
        current_position = self.clamp_position(self.set_position)
        setpoint_msg = PoseStamped()
        setpoint_msg.header.stamp = self.timestamp
        setpoint_msg.header.frame_id = self.frame_id
        setpoint_msg.pose.position = current_position
        setpoint_msg.pose.orientation = self.set_orientation
        # Publish the message to the /mavros/setpoint_position/local topic
        self.setpoint_publisher.publish(setpoint_msg)

    def frame_input_callback(self, msg):
        # convert ROS Image message to OpenCV image
        current_frame = self.br.imgmsg_to_cv2(msg)
        # run the full processing on the frame to change setpoint
        self.full_image_processing(current_frame)
        return

    ################################################
    # IMAGE PROCESSING
    ################################################

    def full_image_processing(self, frame):
        self.t1 = time.time()
        # the first time, we set up parameters
        if self.FOCAL_LENGTH_PIXELS is None: self.first_time_setup_image_parameters(frame)
        # take the frame and find the object center
        center = self.find_object_center(frame)
        # if the center exists, we assign to current ball position
        if center:
            self.curr_center = center
            # draw the center on the frame
            cv2.circle(frame, self.curr_center, 1, (0, 255, 0), -1)
            # calculate the offset from the frame center
            offset_x_pixels, offset_y_pixels = self.mini_calculate_golf_ball_metrics()
            # then based on how far off we are, instruct the drone's setpoint to move that much
            self.move_drone(offset_x_pixels, offset_y_pixels)
        # always publish the images regadless if a frame was drawn in or not
        self.image_publisher.publish(bridge.cv2_to_imgmsg(frame))
        return

    def find_object_center(self, frame):
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        # Main red mask
        target_mask = cv2.inRange(hsv, self.lower_bound, self.upper_bound)

        # Remove green
        lower_green = np.array([35, 50, 50])
        upper_green = np.array([85, 255, 255])
        green_mask = cv2.inRange(hsv, lower_green, upper_green)

        # Remove blue
        lower_blue = np.array([90, 50, 50])
        upper_blue = np.array([130, 255, 255])
        blue_mask = cv2.inRange(hsv, lower_blue, upper_blue)

        # Invert green and blue masks (we want areas *not* green/blue)
        not_green = cv2.bitwise_not(green_mask)
        not_blue = cv2.bitwise_not(blue_mask)

        # Combine masks: keep red, remove green & blue
        combined_mask = cv2.bitwise_and(target_mask, not_green)
        combined_mask = cv2.bitwise_and(combined_mask, not_blue)

        # Blur to reduce noise
        blurred_mask = cv2.GaussianBlur(combined_mask, (9, 9), 2)

        # Find contours
        contours, _ = cv2.findContours(blurred_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            print("111")
            largest = max(contours, key=cv2.contourArea)
            M = cv2.moments(largest)
            if M["m00"] > 0:
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
                return (cx, cy)

        # Fallback: center of mass of whole mask
        M = cv2.moments(blurred_mask)
        if M["m00"] > 0:
            print("222")
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])
            return (cx, cy)

        return None


    def mini_calculate_golf_ball_metrics(self):
        # using the frame center and current ball center, find offset
        offset_x_pixels = self.curr_center[0] - self.camera_frame_center[0]
        offset_y_pixels = self.curr_center[1] - self.camera_frame_center[1]
        return offset_x_pixels, offset_y_pixels


    def move_drone(self, p_error_x, p_error_y):
        # calculate the vector length
        vector_length = self.calculate_pixel_difference(p_error_x, p_error_y)
        print("moving drone triggered", vector_length)
        # if the length is close enough, no change to setpoint, we don't move
        if vector_length <= self.frame_pixel_tol: 
            print("*** HOVERING ***")
            if self.testing:
                self.set_position.x = self.position.x
                self.set_position.y = self.position.y
                self.set_position.z = self.desired_flight_height
            return
        # if we made it past here, then we want to move
        print("*** MOVE ***")
        # calculate derivative component
        curr_time = self.get_clock().now()
        dt = (curr_time - self.prev_time).nanoseconds / 1e9  # convert ns to seconds
        if dt == 0: dt = 1e-6  # prevent division by zero
        d_error_x = (p_error_x - self.prev_p_error_x) / dt
        d_error_y = (p_error_y - self.prev_p_error_y) / dt
        # PD control signal
        move_x = self.Kp * p_error_x + self.Kd * d_error_x
        move_y = self.Kp * p_error_y + self.Kd * d_error_y
        # update the drone's position with the scaled values
        if self.testing:
            self.set_position.x = self.position.x - move_y
            self.set_position.y = self.position.y - move_x
            self.set_position.z = self.desired_flight_height
        # save current state for next iteration
        self.prev_p_error_x = p_error_x
        self.prev_p_error_y = p_error_y
        self.prev_time = curr_time
        self.t2 = time.time()

        print(self.t2 - self.t1)


    ################################################
    # IMAGE PROCESSING HELPERS
    ################################################

    def rgb_to_hsv(self, rgb):
        # convert RGB to HSV
        rgb_array = np.uint8([[list(rgb)]])
        hsv_array = cv2.cvtColor(rgb_array, cv2.COLOR_RGB2HSV)
        return tuple(hsv_array[0][0]) 

    def set_target_color(self, rgb_color, hue_tol=10, sat_tol=100, val_tol=100):
        # set the colour and give bounds for tolerance
        hsv_color = self.rgb_to_hsv(rgb_color)
        h, s, v = hsv_color
        self.lower_bound = np.array([
            max(h - hue_tol, 0),
            max(s - sat_tol, 0),
            max(v - val_tol, 0)])
        self.upper_bound = np.array([
            min(h + hue_tol, 179),
            min(s + sat_tol, 255),
            min(v + val_tol, 255)])

    def calculate_pixel_difference(self, x, y):
        # calculate vector lengths
        vector_length = (x ** 2 + y ** 2) ** 0.5
        return vector_length

    def first_time_setup_image_parameters(self, frame):
        self.frame_height, self.frame_width, _ = frame.shape
        self.camera_frame_center = (self.frame_width / 2, self.frame_height / 2)
        self.FOCAL_LENGTH_PIXELS = ((self.FOCAL_LENGTH_MM / self.SENSOR_WIDTH_MM) * self.frame_width) / self.DOWN_SAMPLE_FACTOR
        return

    def set_pose_initial(self):
        # Put the current position into maintained position
        self.set_position.x = self.init_x
        self.set_position.y = self.init_y
        self.set_position.z = 0.0
        self.set_orientation.x = 0.0
        self.set_orientation.y = 0.0
        self.set_orientation.z = 0.0
        self.set_orientation.w = -1.0


################################################
# MAIN EXECUTION
################################################

def main(args=None):
    rclpy.init(args=args)
    test_type = "vicon"
    node = DroneControlNode(test_type)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info('SHUTTING DOWN NODE.')
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == "__main__":
    main()


################################################
# END
################################################