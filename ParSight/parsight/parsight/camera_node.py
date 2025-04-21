################################################
# Descriptions
################################################


'''
node subscribes to camera data from rgb_camera topic
node publishes message with just the image
'''


################################################
# Imports and Setup
################################################


# ros imports
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image

# image related
import cv2
from cv_bridge import CvBridge

# other imports
import time
try:
    from queue import Queue
except ModuleNotFoundError:
    from Queue import Queue
import threading

from rclpy.qos import QoSProfile, QoSReliabilityPolicy

################################################
# Class Nodes
################################################

# ros2 camera node
class RGBCameraNode(Node):

    def __init__(self, cap):
        super().__init__('rgb_camera_node')
        # initiate the node
        self.publisher_ = self.create_publisher(Image, 'camera/image_raw', 1) # qos_profile)
        self.bridge = CvBridge()
        self.cap = cap
        # check for camera starting
        if not self.cap.isOpened():
            self.get_logger().error("Failed to open camera!")
            raise RuntimeError("Failed to open camera!")
        # create the timer
        timer_period = 0.01 # 0.017 # seconds
        self.timer = self.create_timer(timer_period, self.timer_callback)  
        # ssed to convert between ROS and OpenCV images
        self.br = CvBridge()
   
    def timer_callback(self):
        ret, frame = self.cap.read()
        if ret == True:
            self.publisher_.publish(self.br.cv2_to_imgmsg(cv2.resize(frame, (128, 128))))
            self.get_logger().info('Publishing video frame')

    def stop(self):
        self.frame_reader.stop()
        self.cap.release()

################################################
# Main
################################################


def main(args=None):

    cap = cv2.VideoCapture(0)

    rclpy.init(args=args)
    node = RGBCameraNode(cap)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info('Shutting down camera node.')
        node.stop()
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    print(cv2.getBuildInformation())

    main()


################################################
# END
################################################