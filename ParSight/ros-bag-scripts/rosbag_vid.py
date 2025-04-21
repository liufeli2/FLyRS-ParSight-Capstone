import sqlite3
import os
import cv2
from cv_bridge import CvBridge
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message

# === CONFIG ===
bag_folder = "/home/jetson/flyrs_ws/rosbag2_2025_04_02-14_03_16"  # directory containing metadata.yaml and data_0.db3
image_topic = "/camera/segmented"  # Replace with your actual image topic
output_dir = "yolo_seg"
db_file = os.path.join(bag_folder, "rosbag2_2025_04_02-14_03_16_0.db3")

# === SETUP ===
os.makedirs(output_dir, exist_ok=True)
bridge = CvBridge()

# Connect to ROS 2 bag database
conn = sqlite3.connect(db_file)
cursor = conn.cursor()

# Get topic ID for the image topic
cursor.execute("SELECT id FROM topics WHERE name = ?", (image_topic,))
row = cursor.fetchone()

if not row:
    print(f"Topic '{image_topic}' not found in the bag.")
    exit()

topic_id = row[0]
msg_type = get_message("sensor_msgs/msg/Image")

# Query and save frames
cursor.execute("SELECT timestamp, data FROM messages WHERE topic_id = ?", (topic_id,))
rows = cursor.fetchall()

print(f"Found {len(rows)} image messages. Saving...")

for i, (timestamp, data) in enumerate(rows):
    try:
        img_msg = deserialize_message(data, msg_type)

        # Handle the encoding manually if needed
        if img_msg.encoding == "8UC3":
            # Treat as BGR manually
            cv_image = bridge.imgmsg_to_cv2(img_msg, desired_encoding="passthrough")
            cv_image = cv2.cvtColor(cv_image, cv2.COLOR_RGB2BGR)  # Assuming it's RGB-ish
        else:
            # Normal handling
            cv_image = bridge.imgmsg_to_cv2(img_msg, desired_encoding="bgr8")

        filename = f"frame_{i:05d}.jpg"
        cv2.imwrite(os.path.join(output_dir, filename), cv_image)
        print(f"Saved {filename}")

    except Exception as e:
        print(f"Frame {i} skipped due to error: {e}")


conn.close()
print(f"Saved {len(rows)} frames to '{output_dir}'")
