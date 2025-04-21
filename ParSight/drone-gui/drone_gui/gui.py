# import rclpy
# from rclpy.node import Node
# from std_srvs.srv import Empty, Trigger

# from nav_msgs.msg import Odometry
# from geometry_msgs.msg import PoseStamped
# from rclpy.qos import QoSProfile, QoSReliabilityPolicy

# from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout
# from PyQt5.QtCore import QTimer, QThread
# import sys

# qos_profile = QoSProfile(reliability=QoSReliabilityPolicy.BEST_EFFORT, depth=1)

# class CommNode(Node):
#     def __init__(self):
#         super().__init__('gui')  # Properly initialize the ROS2 node

#         print('enter')

#         # RealSense Subscriber
#         self.realsense_subscriber = self.create_subscription(Odometry, '/camera/pose/sample', self.realsense_callback, qos_profile)
#         self.get_logger().info("Subscribed to RealSense!")

#         # Vicon
#         self.vicon_subscriber = self.create_subscription(PoseStamped, '/vicon/ROB498_Drone/ROB498_Drone', self.vicon_callback, qos_profile)
#         self.get_logger().info('Subscribing to Vicon!')

#         # Setpoint
#         self.setpoint_subscriber = self.create_subscription(PoseStamped, '/mavros/setpoint_position/local', self.setpoint_callback, qos_profile)
#         self.get_logger().info('Subscribing to setpoint!')

#         # Drone pose reading
#         self.pose_subscriber = self.create_subscription(PoseStamped, '/mavros/local_position/pose', self.pose_callback, qos_profile)
#         self.get_logger().info('Subscribing to local pose!')

#     def realsense_callback(self, msg):
#         self.position = msg.pose.pose.position
#         self.update_realsense(self.position)

#     def vicon_callback(self, msg):
#         self.position = msg.pose.position
#         self.update_vicon(self.position)

#     def setpoint_callback(self, msg):
#         self.set_position = msg.pose.position
#         self.update_setpoint(self.set_position)

#     def pose_callback(self, msg):
#         self.position = msg.pose.position
#         self.update_pose(self.position)

#     def update_realsense(self, position):
#         self.realsense_label.setText(f"RealSense Position: x={position.x}, y={position.y}, z={position.z}")

#     def update_vicon(self, position):
#         self.vicon_label.setText(f"Vicon Position: x={position.x}, y={position.y}, z={position.z}")

#     def update_setpoint(self, position):
#         self.setpoint_label.setText(f"Setpoint Position: x={position.x}, y={position.y}, z={position.z}")

#     def update_pose(self, position):
#         self.pose_label.setText(f"Drone Pose Position: x={position.x}, y={position.y}, z={position.z}")


# class ROS2SpinThread(QThread):
#     def __init__(self, node):
#         super().__init__()
#         self.node = node
#         self.running = True  # Add a running flag

#     def run(self):
#         print("[THREAD] ROS2 Spin Thread Started")  # Debug message
#         while self.running and rclpy.ok():
#             rclpy.spin_once(self.node, timeout_sec=0.1)  # Use spin_once() to avoid blocking forever
#             print("[THREAD] Spinning...")  # Debug message


# class DroneGUI(QWidget):
#     def __init__(self, comm_node):
#         super().__init__()  # Properly initialize the GUI window
#         self.comm_node = comm_node  # Assign the CommNode instance

#         print("Node Initialized")

#         self.initUI()
        
#         # Timer to periodically update the GUI
#         self.timer = QTimer()
#         self.timer.timeout.connect(self.update_gui)
#         self.timer.start(50)  # Update every 50ms

#         # Start spinning ROS2 node in a separate thread
#         self.ros_thread = ROS2SpinThread(self.comm_node)
#         self.ros_thread.start()

#     def initUI(self):
#         self.layout = QVBoxLayout()
#         self.realsense_label = QLabel("RealSense Position: x=0, y=0, z=0")
#         self.vicon_label = QLabel("Vicon Position: x=0, y=0, z=0")
#         self.setpoint_label = QLabel("Setpoint Position: x=0, y=0, z=0")
#         self.pose_label = QLabel("Drone Pose Position: x=0, y=0, z=0")

#         self.layout.addWidget(self.realsense_label)
#         self.layout.addWidget(self.vicon_label)
#         self.layout.addWidget(self.setpoint_label)
#         self.layout.addWidget(self.pose_label)

#         self.setLayout(self.layout)
#         self.setWindowTitle("Drone Data GUI")
#         self.show()

#     def update_gui(self):
#         # Perform any periodic updates needed in the GUI
#         pass


# def main(args=None):
#     rclpy.init(args=args)
#     app = QApplication(sys.argv)

#     comm_node = CommNode()  # Create CommNode instance
#     gui = DroneGUI(comm_node)  # Pass CommNode to GUI
#     sys.exit(app.exec_())  # Start GUI loop

#     gui.comm_node.destroy_node()
#     rclpy.shutdown()


# if __name__ == '__main__':
#     main()

import rclpy
from rclpy.node import Node
from std_srvs.srv import Empty, Trigger
from nav_msgs.msg import Odometry
from geometry_msgs.msg import PoseStamped
from rclpy.qos import QoSProfile, QoSReliabilityPolicy

from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout
from PyQt5.QtCore import QTimer, QThread, pyqtSignal, QObject
import sys

qos_profile = QoSProfile(reliability=QoSReliabilityPolicy.BEST_EFFORT, depth=1)


class RosThread(QThread):
    update_signal = pyqtSignal()  # Signal to update the GUI

    def __init__(self, node):
        super().__init__()
        self.node = node
        self.running = True

    def run(self):
        print("[THREAD] ROS2 Spin Thread Started")
        while self.running and rclpy.ok():
            rclpy.spin_once(self.node, timeout_sec=0.1)
            self.update_signal.emit()  # Emit signal to GUI

        print("[THREAD] ROS2 Spin Thread Stopped")

    def stop(self):
        self.running = False


class CommNode(Node):
    def __init__(self, gui):
        super().__init__('gui')
        self.gui = gui

        # Subscribers
        self.realsense_subscriber = self.create_subscription(Odometry, '/camera/pose/sample', self.realsense_callback, qos_profile)
        self.get_logger().info("Subscribed to RealSense!")

        self.vicon_subscriber = self.create_subscription(PoseStamped, '/vicon/ROB498_Drone/ROB498_Drone', self.vicon_callback, qos_profile)
        self.get_logger().info('Subscribed to Vicon!')

        self.setpoint_subscriber = self.create_subscription(PoseStamped, '/mavros/setpoint_position/local', self.setpoint_callback, qos_profile)
        self.get_logger().info('Subscribed to Setpoint!')

        self.pose_subscriber = self.create_subscription(PoseStamped, '/mavros/local_position/pose', self.pose_callback, qos_profile)
        self.get_logger().info('Subscribed to Local Pose!')

    def realsense_callback(self, msg):
        position = msg.pose.pose.position
        self.gui.update_realsense(position)

    def vicon_callback(self, msg):
        position = msg.pose.position
        self.gui.update_vicon(position)

    def setpoint_callback(self, msg):
        position = msg.pose.position
        self.gui.update_setpoint(position)

    def pose_callback(self, msg):
        position = msg.pose.position
        self.gui.update_pose(position)


class DroneGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.comm_node = CommNode(self)

        # ROS Background Thread
        self.ros_thread = RosThread(self.comm_node)
        self.ros_thread.update_signal.connect(self.update_labels)  # Connect signal to GUI update
        self.ros_thread.start()  # Start ROS2 in separate thread

    def initUI(self):
        self.layout = QVBoxLayout()

        self.realsense_label = QLabel("RealSense Position: x=0, y=0, z=0")
        self.vicon_label = QLabel("Vicon Position: x=0, y=0, z=0")
        self.setpoint_label = QLabel("Setpoint Position: x=0, y=0, z=0")
        self.pose_label = QLabel("Drone Pose Position: x=0, y=0, z=0")

        self.layout.addWidget(self.realsense_label)
        self.layout.addWidget(self.vicon_label)
        self.layout.addWidget(self.setpoint_label)
        self.layout.addWidget(self.pose_label)

        self.setLayout(self.layout)
        self.setWindowTitle("Drone Data GUI")
        self.show()

    def update_labels(self):
        # Just refresh labels every 100ms
        pass

    def update_realsense(self, position):
        self.realsense_label.setText(f"RealSense Position: x={position.x:.2f}, y={position.y:.2f}, z={position.z:.2f}")

    def update_vicon(self, position):
        self.vicon_label.setText(f"Vicon Position: x={position.x:.2f}, y={position.y:.2f}, z={position.z:.2f}")

    def update_setpoint(self, position):
        self.setpoint_label.setText(f"Setpoint Position: x={position.x:.2f}, y={position.y:.2f}, z={position.z:.2f}")

    def update_pose(self, position):
        self.pose_label.setText(f"Drone Pose Position: x={position.x:.2f}, y={position.y:.2f}, z={position.z:.2f}")

    def closeEvent(self, event):
        print("[GUI] Closing Window")
        self.ros_thread.stop()
        self.ros_thread.wait()
        self.comm_node.destroy_node()
        rclpy.shutdown()
        print("[GUI] Shutdown Complete")
        event.accept()


def main(args=None):
    rclpy.init(args=args)
    app = QApplication(sys.argv)
    gui = DroneGUI()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()

