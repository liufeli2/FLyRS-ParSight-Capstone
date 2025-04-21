import rclpy
from rclpy.node import Node
from nav_msgs.msg import Odometry
from rclpy.qos import QoSProfile, QoSReliabilityPolicy
from geometry_msgs.msg import PoseStamped, Quaternion, Point
import numpy as np
import scipy.spatial.transform as stf

qos_profile = QoSProfile(reliability=QoSReliabilityPolicy.BEST_EFFORT, depth=1)

class RealSense(Node):
    def __init__(self):
        super().__init__('realsense')
        
        # Initialize storage variables
        self.position = None
        self.orientation = Quaternion()
        self.timestamp = None
        self.frame_id = "map"

        # Initialize SENDING storage variables
        self.set_position = None
        self.set_orientation = None

        # Subscriber to Vicon pose data
        self.vicon_subscriber = self.create_subscription(PoseStamped, '/vicon/ROB498_Drone/ROB498_Drone', self.vicon_callback, 1)
        self.get_logger().info('Subscribing to Vicon!')

        # Subscriber to RealSense pose data
        # self.realsense_subscriber = self.create_subscription(Odometry, '/camera/pose/sample', self.realsense_callback, qos_profile)
        # self.get_logger().info('Subscribing to RealSense!')
        
        # Publisher for VisionPose topic
        self.vision_pose_publisher = self.create_publisher(PoseStamped, '/mavros/vision_pose/pose', 1)
        self.get_logger().info('Publishing to VisionPose')
        
        # Publisher for SetPoint topic
        self.setpoint_publisher = self.create_publisher(PoseStamped, '/mavros/setpoint_position/local', qos_profile)
        self.get_logger().info('Publishing to SetPoint')

        self.convert = stf.Rotation.from_euler('xyz', angles=[np.pi/2,0,-np.pi/2])

        # Statement to end the inits
        self.get_logger().info('Realsense Node All Setup and Started!')

    def realsense_callback(self, msg):
        # quat = [msg.pose.pose.orientation.x, msg.pose.pose.orientation.y,
        #         msg.pose.pose.orientation.z, msg.pose.pose.orientation.w]
        # quat = stf.Rotation.from_quat(quat)

        # twist = quat  * self.convert
        # print(twist.as_quat())
        # print(self.orientation)
        self.position = msg.pose.pose.position

        # self.orientation.x = twist.as_quat()[0]
        # self.orientation.y = twist.as_quat()[1]
        # self.orientation.z = twist.as_quat()[2]
        # self.orientation.w = twist.as_quat()[3]
        self.orientation = msg.pose.pose.orientation
        self.orientation.x *= -1
        self.orientation.y *= -1
        self.orientation.z *= -1
        self.orientation.w *= -1

        print(self.orientation)

        self.timestamp = self.get_clock().now().to_msg() #msg.header.stamp
        # Everytime we get stuff, write both immediately
        self.send_vision_pose()
        self.send_setpoint()
        
    def vicon_callback(self, msg):
        self.get_logger().info("Recieved Vicon Input")

        quat = [msg.pose.orientation.x, msg.pose.orientation.y,
                msg.pose.orientation.z, msg.pose.orientation.w]
        quat = stf.Rotation.from_quat(quat)

        twist = quat  * self.convert

        self.position = msg.pose.position
        
        # self.orientation.x = twist.as_quat()[0]
        # self.orientation.y = twist.as_quat()[1]
        # self.orientation.z = twist.as_quat()[2]
        # self.orientation.w = twist.as_quat()[3]
        self.orientation = msg.pose.orientation
        self.orientation.x *= -1
        self.orientation.y *= -1
        self.orientation.z *= -1
        self.orientation.w *= -1

        self.timestamp = self.get_clock().now().to_msg()
        # Everytime we get stuff, write both immediately
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


    def send_setpoint(self):
        # Create a new PoseStamped message to publish to setpoint topic
        setpoint_msg = PoseStamped()
        setpoint_msg.pose.position = self.position
        setpoint_msg.pose.orientation = self.orientation
        setpoint_msg.header.stamp = self.timestamp
        setpoint_msg.header.frame_id = self.frame_id
        # Publish the message to the /mavros/setpoint_position/local topic
        self.setpoint_publisher.publish(setpoint_msg)


def main(args=None):
    rclpy.init(args=args)
    node = RealSense()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
