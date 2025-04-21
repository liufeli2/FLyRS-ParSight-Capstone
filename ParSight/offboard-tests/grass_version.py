import cv2
import numpy as np

import datetime
import imageio

class ColorObjectTracker:
    def __init__(self):
        # Target color to track (red), and HSV tolerance values
        self.target_rgb = (252, 253, 253)
        self.hue_tol = 20
        self.sat_tol = 50
        self.val_tol = 100

        self.false_positive_mode = False
        self.false_positive_total_frames = 0
        self.false_positive_wrong_detections = 0

        self.assessment_mode = False
        self.assessment_total_frames = 0
        self.assessment_detected_frames = 0

        self.gif_recording = False
        self.gif_frames = []

        # Initialize color bounds
        self.set_target_color()

        # Initialize camera
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            raise Exception("Error: Could not access the camera.")

    def rgb_to_hsv(self):
        rgb_array = np.uint8([[list(self.target_rgb)]])
        hsv_array = cv2.cvtColor(rgb_array, cv2.COLOR_RGB2HSV)
        return tuple(hsv_array[0][0]) 

    def set_target_color(self):
        hsv_color = self.rgb_to_hsv()
        h, s, v = hsv_color
        self.lower_bound = np.array([
            max(h - self.hue_tol, 0),
            max(s - self.sat_tol, 0),
            max(v - self.val_tol, 0)])
        self.upper_bound = np.array([
            min(h + self.hue_tol, 255),
            min(s + self.sat_tol, 255),
            min(v + self.val_tol, 255)])

    def find_object_contour_and_center(self, frame):
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, self.lower_bound, self.upper_bound)
        mask = cv2.GaussianBlur(mask, (5, 5), 2)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        best_contour, best_center, best_score, valid_contours = None, None, 0.0, []
        for cnt in contours:
            valid_contours.append(cnt)
            area = cv2.contourArea(cnt)
            perimeter = cv2.arcLength(cnt, True)
            if perimeter == 0 or area < 20: continue
            circularity = 4 * np.pi * area / (perimeter ** 2)
            if circularity > 0.8:
                score = circularity * 2*np.log(area)
                if score > best_score and score > 7:
                    M = cv2.moments(cnt)
                    if M["m00"] > 0:
                        cx = int(M["m10"] / M["m00"])
                        cy = int(M["m01"] / M["m00"])
                        best_contour = cnt
                        best_center = (cx, cy)
                        best_score = score
                        # print(f"Best contour score: {best_score:.2f}")
        return best_contour, best_center, valid_contours
    
    def start(self):
        try:
            while True:
                ret, frame = self.cap.read()
                if not ret:
                    print("Failed to grab frame.")
                    break

                # Crop to center square
                h, w, _ = frame.shape
                min_dim = min(h, w)
                start_x = (w - min_dim) // 2
                start_y = (h - min_dim) // 2
                cropped_frame = frame[start_y:start_y + min_dim, start_x:start_x + min_dim]

                # Blur and resize
                blurred_frame = cv2.GaussianBlur(cropped_frame, (5, 5), 0)
                resized_frame = cv2.resize(blurred_frame, (128, 128))

                # Find object
                contour, center, valid_contours = self.find_object_contour_and_center(resized_frame)

                # --- Evaluation logic ---
                if self.assessment_mode:
                    self.assessment_total_frames += 1
                    if contour is not None:
                        self.assessment_detected_frames += 1

                if self.false_positive_mode:
                    self.false_positive_total_frames += 1
                    if contour is not None:
                        self.false_positive_wrong_detections += 1


                # Draw all valid contours in dark blue
                for cnt in valid_contours:
                    if np.array_equal(cnt, contour):
                        continue  # Skip best contour (we'll draw that separately)
                    cv2.drawContours(resized_frame, [cnt], -1, (139, 0, 0), 1)  # Dark blue

                # Draw best contour in white
                if contour is not None:
                    x, y, w, h = cv2.boundingRect(contour)
                    cv2.rectangle(resized_frame, (x, y), (x + w, y + h), (255, 255, 255), 1)

                if center:
                    cv2.circle(resized_frame, center, 1, (0, 255, 0), -1)

                # Display
                display_frame = cv2.resize(resized_frame, (200, 200), interpolation=cv2.INTER_NEAREST)
                # display_frame = cv2.resize(resized_frame, (800, 800), interpolation=cv2.INTER_NEAREST)
                cv2.imshow('Color Object Tracker', display_frame)

                # Key controls
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    # Final calculations
                    tp = self.assessment_detected_frames
                    fn = self.assessment_total_frames - tp
                    fp = self.false_positive_wrong_detections
                    tn = self.false_positive_total_frames - fp

                    total = tp + tn + fp + fn
                    accuracy = (tp + tn) / total * 100 if total > 0 else 0
                    precision = tp / (tp + fp) * 100 if (tp + fp) > 0 else 0
                    recall = tp / (tp + fn) * 100 if (tp + fn) > 0 else 0
                    fpr = fp / (fp + tn) * 100 if (fp + tn) > 0 else 0

                    print("\n🧾 FINAL REPORT")
                    print(f"               Predicted Positive    Predicted Negative")
                    print(f"Actual Positive     {tp:>5}                  {fn:>5}")
                    print(f"Actual Negative     {fp:>5}                  {tn:>5}")
                    print("\nMetrics:")
                    print(f"    Accuracy:               {accuracy:.2f}%")
                    print(f"    Precision:              {precision:.2f}%")
                    print(f"    Recall (TPR):           {recall:.2f}%")
                    print(f"    False Positive Rate:    {fpr:.2f}%")
                    break
                elif key == ord('a'):
                    self.assessment_mode = not self.assessment_mode
                    if self.assessment_mode:
                        print("🔴 IN-FRAME Assessment started.")
                        self.assessment_total_frames = 0
                        self.assessment_detected_frames = 0
                    else:
                        print("\n🟢 IN-FRAME Assessment stopped.")
                        print(f"    Total frames: {self.assessment_total_frames}")
                        print(f"    Detected frames: {self.assessment_detected_frames}")
                        if self.assessment_total_frames > 0:
                            accuracy = (self.assessment_detected_frames / self.assessment_total_frames) * 100
                            print(f"    Detection Accuracy: {accuracy:.2f}%")
                        else:
                            print("    No frames assessed.")

                elif key == ord('z'):
                    self.false_positive_mode = not self.false_positive_mode
                    if self.false_positive_mode:
                        print("🟡 FALSE POSITIVE Assessment started.")
                        self.false_positive_total_frames = 0
                        self.false_positive_wrong_detections = 0
                    else:
                        print("\n🔵 FALSE POSITIVE Assessment stopped.")
                        print(f"    Total frames: {self.false_positive_total_frames}")
                        print(f"    Wrong detections: {self.false_positive_wrong_detections}")
                        if self.false_positive_total_frames > 0:
                            fp_rate = (self.false_positive_wrong_detections / self.false_positive_total_frames) * 100
                            print(f"    False Positive Rate: {fp_rate:.2f}%")
                        else:
                            print("    No frames assessed.")

                elif key == ord('s'):
                    self.gif_recording = not self.gif_recording
                    if self.gif_recording:
                        print("🟠 GIF recording started...")
                        self.gif_frames = []
                    else:
                        print("🟣 GIF recording stopped. Saving...")
                        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                        filename = f"recording_{timestamp}.gif"
                        imageio.mimsave(filename, self.gif_frames, fps=80, loop=0)
                        print(f"✅ Saved GIF as {filename}")


                if self.gif_recording:
                    # Convert to RGB for GIF and append
                    rgb_frame = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
                    self.gif_frames.append(rgb_frame)

        finally:
            self.cap.release()
            cv2.destroyAllWindows()

# Example usage
if __name__ == "__main__":
    tracker = ColorObjectTracker()
    tracker.start()