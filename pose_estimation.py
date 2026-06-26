import cv2
import mediapipe as mp

class PoseDetector:
    def __init__(self, static_image_mode=False, model_complexity=1, enable_segmentation=False):
        self.mp_pose = mp.solutions.pose
        self.pose = self.mp_pose.Pose(static_image_mode=static_image_mode,
                                      model_complexity=model_complexity,
                                      enable_segmentation=enable_segmentation)
        self.mp_drawing= mp.solutions.drawing_utils

    def detect_pose(self, frame):
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.pose.process(frame_rgb)
        return results

    def draw_landmarks(self, frame, results):
        if results.pose_landmarks:
            self.mp_drawing.draw_landmarks(
                frame, 
                results.pose_landmarks, 
                self.mp_pose.POSE_CONNECTIONS)
        return frame

    def get_landmarks(self,results):
        if results.pose_landmarks:
            return results.pose_landmarks.landmark
        else:
            return None
