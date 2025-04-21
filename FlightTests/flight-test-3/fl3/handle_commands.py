################################################
# IMPORTS and SETUP
################################################

# math imports
import numpy as np

# ros2 imports
import rclpy
from rclpy.node import Node
from std_srvs.srv import Trigger

# topic imports
from geometry_msgs.msg import PoseArray, PoseStamped, Point, Quaternion
from nav_msgs.msg import Odometry

# reliability imports
from rclpy.qos import QoSProfile, QoSReliabilityPolicy
qos_profile = QoSProfile(reliability=QoSReliabilityPolicy.BEST_EFFORT, depth=1)

################################################
# NODES
################################################

class CommNode(Node):

    def __init__(self, test_type):
        super().__init__('rob498_drone_1') 

        ###############
        # SERVICE CALLS

        self.srv_launch = self.create_service(Trigger, 'rob498_drone_1/comm/launch', self.callback_launch)
        self.srv_test = self.create_service(Trigger, 'rob498_drone_1/comm/test', self.callback_test)
        self.srv_land = self.create_service(Trigger, 'rob498_drone_1/comm/land', self.callback_land)
        self.srv_abort = self.create_service(Trigger, 'rob498_drone_1/comm/abort', self.callback_abort)
        self.sub_waypoints = self.create_subscription(PoseArray, 'rob498_drone_1/comm/waypoints', self.callback_waypoints, 10)
        print('services created')

        ################
        # VARIABLE SETUP

        # for the launching, we start ready to set the waypoint
        self.height = 0.8
        self.z_offset = 0.17
        self.scaling = 1.5

        # for vision_pose to know where it is
        self.realsense_position = Point()
        self.realsense_orientation = Quaternion()
        self.realsense_timestamp = None
        self.frame_id = "map"

        self.vicon_position = Point()
        self.vicon_orientation = Quaternion()
        self.vicon_timestamp = None

        # for setpoint_vision to know where to go
        self.set_position = Point()
        self.set_orientation = Quaternion()
        self.set_orientation.w = -1.0
        
        # to fix the vicon storage system
        self.offset_position = Point()
        self.offset_acquired = False

        # tolerance for grading
        self.tol_radius = 0.2 #0.4
        self.in_test = False

        # # inital global variables
        # self.WAYPOINTS = None
        # self.WAYPOINTS_RECEIVED = False
        # self.set_this_waypoint = False
        # self.waypoint_index = 0
        # self.waypoint = None

        # # inital global variables
        # h = 1
        # self.WAYPOINTS = np.array([[0, 0, h],[0, h, 0.1],[h, 0, 0.1],[h, h, h]])
        # self.WAYPOINTS_RECEIVED = True
        # self.set_this_waypoint = False
        # self.waypoint_index = 0
        # self.waypoint = None

        # inital global variables
        self.WAYPOINTS = np.array([[-2.3, 2.3, 0.5], 
                                   [0.0, 2.3, 0.5],
                                   [2.8, 2.3, 0.5], 
                                   [1.5, 0.1, 0.5]])
        self.WAYPOINTS_RECEIVED = True
        self.set_this_waypoint = False
        self.waypoint_index = 0
        self.waypoint = None
        
        self.test_type = test_type

        ############################
        # SUBSCRIBER/PUBLISHER SETUP

        if test_type == "realsense":
            # Subscriber to RealSense pose data
            self.realsense_subscriber = self.create_subscription(Odometry, '/camera/pose/sample', self.realsense_callback, qos_profile)
            self.get_logger().info('Subscribing to RealSense!')
            # Subscriber to Vicon pose data
            self.vicon_subscriber = self.create_subscription(PoseStamped, '/vicon/ROB498_Drone/ROB498_Drone', self.vicon_callback, 1)
            self.get_logger().info('Subscribing to Vicon!')
        else: 
            # Subscriber to Vicon pose data
            self.vicon_subscriber = self.create_subscription(PoseStamped, '/vicon/ROB498_Drone/ROB498_Drone', self.vicon_callback, 1)
            self.get_logger().info('Subscribing to Vicon!')
        
        # Publisher for VisionPose topic
        self.vision_pose_publisher = self.create_publisher(PoseStamped, '/mavros/vision_pose/pose', 1)
        self.get_logger().info('Publishing to VisionPose')

        # Publisher for SetPoint topic
        self.setpoint_publisher = self.create_publisher(PoseStamped, '/mavros/setpoint_position/local', qos_profile)
        self.get_logger().info('Publishing to SetPoint')

        # Statement to end the inits
        self.get_logger().info('Nodes All Setup and Started!')
        

    ################################################
    # SERVICE CALLS 
    ################################################

    def callback_launch(self, request, response):
        print('Launch Requested. Your drone should take off.')
        self.set_pose_initial()
        self.set_position.z = self.height
        return response

    def callback_test(self, request, response):
        print('Test Requested. Your drone should perform the required tasks. Recording starts now.')
        self.in_test = True
        return response
    
    def calculate_offset(self):
        if self.in_test==False and self.realsense_position and self.vicon_position:
            offset_position = Point()
            offset_position.x = self.realsense_position.x - self.vicon_position.x
            offset_position.y = self.realsense_position.y - self.vicon_position.y
            offset_position.z = self.realsense_position.z - self.vicon_position.z
            self.offset_position = offset_position
            self.offset_acquired = True
        return

    def test_loop(self):
        # check if we're got points and are good to go
        # print(self.in_test)
        print(self.offset_position)
        if self.in_test and self.WAYPOINTS_RECEIVED:
            # loop through the waypoints
            if self.waypoint_index < len(self.WAYPOINTS):
                print(self.waypoint_index, self.waypoint)

                if not self.set_this_waypoint:
                    self.waypoint = self.WAYPOINTS[self.waypoint_index]
                    self.set_waypoint(self.waypoint)
                    self.set_this_waypoint = True

                # changing to the next index when close enough
                if self.close_enough(self.waypoint):
                    self.set_this_waypoint = False
                    self.waypoint_index += 1
                    print('Waypoint Reached:', self.waypoint)

            else:
                self.in_test = False
                print("Done traversing waypoints!")
        else:
            print('No waypoints received. Cannot test.')


    def callback_land(self, request, response):
        print('Land Requested. Your drone should land.')
        self.set_position.z = 0.1
        response.success = True
        response.message = "Success"
        return response

    def callback_abort(self, request, response):
        print('Abort Requested. Your drone should land immediately due to safety considerations.')
        self.set_position.z = 0.0
        response.success = True
        response.message = "Success"
        return response


    ################################################
    # SERVICE CALLS 
    ################################################
    
    def realsense_callback(self, msg):
        # get the info
        self.realsense_position = msg.pose.pose.position
        self.realsense_orientation = msg.pose.pose.orientation
        self.realsense_timestamp = self.get_clock().now().to_msg()
        # frame conversion
        self.realsense_orientation.x *= -1
        self.realsense_orientation.y *= -1
        self.realsense_orientation.z *= -1
        self.realsense_orientation.w *= -1
        # WRITE BOTH IMMEDIATELY
        self.send_vision_pose()
        self.send_setpoint()
        self.calculate_offset()
        self.test_loop()

    def vicon_callback(self, msg):
        # get the info
        self.vicon_position = msg.pose.position
        self.vicon_orientation = msg.pose.orientation
        self.vicon_timestamp = self.get_clock().now().to_msg()
        # frame conversion
        self.vicon_orientation.x *= -1
        self.vicon_orientation.y *= -1
        self.vicon_orientation.z *= -1
        self.vicon_orientation.w *= -1
        # WRITE BOTH IMMEDIATELY
        self.send_vision_pose()
        self.send_setpoint()
        self.test_loop()

    def send_vision_pose(self):
        if self.test_type == "realsense":
            timestamp = self.realsense_timestamp
            position = self.realsense_position
            orientation = self.realsense_orientation
        else:
            timestamp = self.vicon_timestamp
            position = self.vicon_position
            orientation = self.vicon_orientation
        # other parts of the message
        vision_pose_msg = PoseStamped()
        vision_pose_msg.pose.orientation = orientation
        vision_pose_msg.header.stamp = timestamp
        vision_pose_msg.header.frame_id = self.frame_id
        # change for the testing type
        if self.offset_acquired:
            # Create a new PoseStamped message to publish to vision_pose topic
            send_pos = Point()
            # send_pos.x = position.x - self.offset_position.x
            # send_pos.y = position.y - self.offset_position.y
            # send_pos.z = position.z - self.offset_position.z
            send_pos.x = position.x * self.scaling
            send_pos.y = position.y * self.scaling
            send_pos.z = (position.z+self.z_offset) * self.scaling
            vision_pose_msg.pose.position = send_pos
        else:
            vision_pose_msg.pose.position = position
        # Publish the message to the /mavros/vision_pose/pose topic
        self.vision_pose_publisher.publish(vision_pose_msg)

    def send_setpoint(self):
        # use the correct type
        if self.test_type == "realsense": timestamp = self.realsense_timestamp
        else: timestamp = self.vicon_timestamp
        # Create a new PoseStamped message to publish to setpoint topic
        setpoint_msg = PoseStamped()
        setpoint_msg.header.stamp = timestamp
        setpoint_msg.header.frame_id = self.frame_id
        setpoint_msg.pose.position = self.set_position
        setpoint_msg.pose.orientation = self.set_orientation
        # Publish the message to the /mavros/setpoint_position/local topic
        self.setpoint_publisher.publish(setpoint_msg)

    def callback_waypoints(self, msg):
        if self.WAYPOINTS_RECEIVED:
            return
        print('Waypoints Received')
        self.WAYPOINTS_RECEIVED = True
        self.WAYPOINTS = np.empty((0,3))
        for pose in msg.poses:
            pos = np.array([pose.position.x, pose.position.y, pose.position.z])
            self.WAYPOINTS = np.vstack((self.WAYPOINTS, pos))


    ################################################
    # HELPER FUNCTIONS
    ################################################

    def set_pose_initial(self):
        # Put the current position into maintained position
        self.set_position.x = 0.0
        self.set_position.y = 0.0
        self.set_position.z = 0.0
        self.set_orientation.x = 0.0
        self.set_orientation.y = 0.0
        self.set_orientation.z = 0.0
        self.set_orientation.w = -1.0

    def set_waypoint(self, waypoint):
        # Put the current position into maintained position
        self.set_position.x = waypoint[0]
        self.set_position.y = waypoint[1]
        self.set_position.z = waypoint[2]
        self.set_orientation.x = 0.0
        self.set_orientation.y = 0.0
        self.set_orientation.z = 0.0
        self.set_orientation.w = -1.0

    def close_enough(self, waypoint):
        # extract the current and waypoint positions
        if self.test_type == "realsense": position = self.realsense_position
        else: position = self.vicon_position
        curr_x, curr_y, curr_z = position.x, position.y, position.z
        w_x, w_y, w_z = waypoint[0], waypoint[1], waypoint[2]
        # check if the drone is close enough to the waypoint
        # using euclidean distance
        if np.sqrt((curr_x - w_x)**2 + (curr_y - w_y)**2 + (curr_z - w_z)**2) < self.tol_radius:
            return True
        # otherwise, not close enough yet
        return False


################################################
# MAIN
################################################
        
def main(args=None):

    # global and local variables
    # global STATE, WAYPOINTS, WAYPOINTS_RECEIVED, set_this_waypoint, waypoint_index
    test_type = "vicon"

    # setup the node the run
    rclpy.init(args=args)
    comm_node = CommNode(test_type)
    print("FLIGHT TEST #3 LET'S GO!")
    rclpy.spin(comm_node) 
    comm_node.destroy_node()

    rclpy.shutdown()


if __name__ == "__main__":
    main()

