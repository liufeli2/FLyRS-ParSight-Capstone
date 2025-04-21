import sqlite3
import os
import cv2
import csv
import numpy as np
from cv_bridge import CvBridge
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message

# === CONFIG ===
bag_folder = "/home/jetson/flyrs_ws/rosbag_catapult_working"   # folder containing metadata.yaml and data_0.db3
image_topic = "/camera/image_raw"       # topic used during flight
db_file = os.path.join(bag_folder, "rosbag2_2025_04_11-11_16_18_0.db3")
output_csv = "ball_distances.csv"
output_img_dir = "extracted_frames_raw"

start_frame = 454
end_frame = 1078

bridge = CvBridge()
os.makedirs(output_img_dir, exist_ok=True)

# Connect to SQLite3 DB
conn = sqlite3.connect(db_file)
cursor = conn.cursor()

# Get topic ID
cursor.execute("SELECT id FROM topics WHERE name = ?", (image_topic,))
row = cursor.fetchone()
if not row:
    print(f"❌ Topic '{image_topic}' not found in rosbag.")
    exit()

topic_id = row[0]
msg_type = get_message("sensor_msgs/msg/Image")
cursor.execute("SELECT timestamp, data FROM messages WHERE topic_id = ?", (topic_id,))
rows = cursor.fetchall()

# Distance results
results = []

for i, (timestamp, data) in enumerate(rows):
    if i < start_frame:
        continue
    if i > end_frame:
        break

    try:
        img_msg = deserialize_message(data, msg_type)

        # === FIX for 8UC3 encoding ===
        if img_msg.encoding == "8UC3":
            img = bridge.imgmsg_to_cv2(img_msg, desired_encoding="passthrough")
            # If colors look wrong, uncomment this:
            # img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        else:
            img = bridge.imgmsg_to_cv2(img_msg, desired_encoding="bgr8")

        height, width = img.shape[:2]
        cx, cy = width // 2, height // 2

        # === Green dot detection ===
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        lower_green = np.array([40, 50, 50])
        upper_green = np.array([80, 255, 255])
        mask = cv2.inRange(hsv, lower_green, upper_green)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            largest = max(contours, key=cv2.contourArea)
            M = cv2.moments(largest)
            if M["m00"] > 0:
                bx = int(M["m10"] / M["m00"])
                by = int(M["m01"] / M["m00"])
                dx = bx - cx
                dy = by - cy
                dist = np.sqrt(dx**2 + dy**2)

                results.append([i, bx, by, dx, dy, dist])

                # Optional: save visualization
                cv2.circle(img, (bx, by), 3, (255, 255, 255), -1)
                cv2.imwrite(os.path.join(output_img_dir, f"frame_{i:05d}.jpg"), img)
            else:
                results.append([i, None, None, None, None, None])
        else:
            results.append([i, None, None, None, None, None])

    except Exception as e:
        print(f"⚠️ Frame {i} error: {e}")
        results.append([i, None, None, None, None, None])

conn.close()

# === Save CSV ===
with open(output_csv, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["frame_index", "ball_x", "ball_y", "dx", "dy", "distance_from_center"])
    writer.writerows(results)

print(f"\n✅ Saved {len(results)} entries to '{output_csv}'")
