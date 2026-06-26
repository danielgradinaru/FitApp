# exercise_evaluation.py
import cv2
import math
import feedback_rules as fr
from feedback_rules import (
    calculate_body_alignment,
    calculate_elbow_angle,
    evaluate_pushup_alignment,
    evaluate_pushup_depth,
    evaluate_pushup_elbow_angle,
    evaluate_pushup_hip_stability,
    generate_pushup_feedback,
    analizeaza_postura_fandare,
    evalueaza_fandare,
)


def evaluate_pushup_form(frame, landmarks, ground_y=1.0, hip_movement_variation=0.0):
    """
    Evalueaza biomecanic o flotare completa.
    """
    left_shoulder = (landmarks[11].x, landmarks[11].y)
    left_hip = (landmarks[23].x, landmarks[23].y)
    left_ankle = (landmarks[27].x, landmarks[27].y)
    left_elbow = (landmarks[13].x, landmarks[13].y)
    left_wrist = (landmarks[15].x, landmarks[15].y)
    right_ankle = (landmarks[28].x, landmarks[28].y)
    chest = (landmarks[12].x, landmarks[12].y)
    right_wrist = (landmarks[16].x, landmarks[16].y)

    ground_candidates_y = [
        left_wrist[1],
        right_wrist[1],
        left_ankle[1],
        right_ankle[1],
    ]
    ground_y = max(ground_candidates_y) if ground_candidates_y else 1.0

    body_alignment_angle = calculate_body_alignment(left_shoulder, left_hip, left_ankle)
    elbow_angle = calculate_elbow_angle(left_shoulder, left_elbow, left_wrist)
    chest_distance_to_ground = max(0.0, ground_y - chest[1])

    alignment_score = evaluate_pushup_alignment(body_alignment_angle)
    depth_score = evaluate_pushup_depth(chest_distance_to_ground)
    elbow_score = evaluate_pushup_elbow_angle(elbow_angle)
    hip_stability_score = evaluate_pushup_hip_stability(hip_movement_variation)

    total_score = int((alignment_score + depth_score + elbow_score + hip_stability_score) / 4)

    feedback_list = generate_pushup_feedback(
        body_alignment_angle,
        chest_distance_to_ground,
        elbow_angle,
        hip_movement_variation
    )

    metrics = {
        'exercise_type': 'flotare',
        'landmarks': landmarks,
        'body_alignment_angle': body_alignment_angle,
        'elbow_angle': elbow_angle,
        'chest_distance_to_ground': chest_distance_to_ground,
        'hip_movement_variation': hip_movement_variation,
        'total_score': total_score,
    }

    return frame, metrics, feedback_list

def evaluate_plank_form(frame, landmarks):
    """
    Evaluează postura pentru plank.
    Plank-ul este tratat ca exercițiu static, nu ca repetare.
    """

    state = fr.plank_state(landmarks)

    body_alignment = state["body_alignment"]
    hip_deviation = state["hip_deviation"]
    hip_position = state.get("hip_position", "neutral")
    pelvis_tilt = state["pelvis_tilt"]
    shoulder_elbow_offset = state["shoulder_elbow_offset"]

    alignment_score = fr.evaluate_plank_alignment(body_alignment)
    hip_score = fr.evaluate_plank_hip_position(hip_deviation)
    pelvis_score = fr.evaluate_plank_pelvis_stability(pelvis_tilt)
    elbow_score = fr.evaluate_plank_elbow_position(shoulder_elbow_offset)

    total_score = int(
        0.35 * alignment_score +
        0.30 * hip_score +
        0.20 * pelvis_score +
        0.15 * elbow_score
    )

    feedback_list = fr.generate_plank_feedback(
        body_alignment,
        hip_deviation,
        pelvis_tilt,
        shoulder_elbow_offset,
        hip_position
    )

    metrics = {
        "exercise_type": "plank",
        "landmarks": landmarks,
        "body_alignment_angle": body_alignment,
        "hip_deviation": hip_deviation,
        "hip_signed_deviation": state.get("hip_signed_deviation", 0.0),
        "hip_position": hip_position,
        "pelvis_tilt": pelvis_tilt,
        "shoulder_elbow_offset": shoulder_elbow_offset,
        "alignment_score": alignment_score,
        "hip_score": hip_score,
        "pelvis_score": pelvis_score,
        "elbow_score": elbow_score,
        "total_score": total_score,
    }

    return frame, metrics, feedback_list

def evaluate_bench_press_form(frame, landmarks):
    """
    Evaluează forma pentru bench press pe cadrul de jos al repetării.
    """

    state = fr.bench_press_rep_state(landmarks)

    elbow_avg = state["elbow_avg"]
    left_elbow_angle = state["left_elbow_angle"]
    right_elbow_angle = state["right_elbow_angle"]
    wrist_elbow_offset = state["wrist_elbow_offset"]
    torso_vertical_motion_proxy = state["torso_vertical_motion_proxy"]

    depth_score = fr.evaluate_bench_elbow_depth(elbow_avg)
    symmetry_score = fr.evaluate_bench_symmetry(left_elbow_angle, right_elbow_angle)
    wrist_score = fr.evaluate_bench_wrist_alignment(wrist_elbow_offset)
    stability_score = fr.evaluate_bench_body_stability(torso_vertical_motion_proxy)

    total_score = int(
        0.35 * depth_score +
        0.25 * symmetry_score +
        0.20 * wrist_score +
        0.20 * stability_score
    )

    feedback_list = fr.generate_bench_press_feedback(
        elbow_avg,
        left_elbow_angle,
        right_elbow_angle,
        wrist_elbow_offset,
        torso_vertical_motion_proxy
    )

    metrics = {
        "exercise_type": "bench_press",
        "landmarks": landmarks,
        "elbow_avg": elbow_avg,
        "left_elbow_angle": left_elbow_angle,
        "right_elbow_angle": right_elbow_angle,
        "wrist_elbow_offset": wrist_elbow_offset,
        "torso_vertical_motion_proxy": torso_vertical_motion_proxy,
        "depth_score": depth_score,
        "symmetry_score": symmetry_score,
        "wrist_score": wrist_score,
        "stability_score": stability_score,
        "total_score": total_score,
    }

    return frame, metrics, feedback_list


def evaluate_biceps_curl_form(frame, landmarks):
    state = fr.biceps_curl_rep_state(landmarks)
    amplitude_score, symmetry_score, torso_score, elbow_score = fr.score_biceps_curl(
        state["elbow_avg"],
        state["left_elbow_angle"],
        state["right_elbow_angle"],
        state["torso_lean"],
        state["elbow_drift"],
    )
    total_score = int((amplitude_score + symmetry_score + torso_score + elbow_score) / 4)
    feedback_list = fr.generate_biceps_curl_feedback(
        state["elbow_avg"],
        state["left_elbow_angle"],
        state["right_elbow_angle"],
        state["torso_lean"],
        state["elbow_drift"],
    )
    metrics = {
        "exercise_type": "biceps_curl",
        "landmarks": landmarks,
        **state,
        "amplitude_score": amplitude_score,
        "symmetry_score": symmetry_score,
        "torso_score": torso_score,
        "elbow_stability_score": elbow_score,
        "total_score": total_score,
    }
    return frame, metrics, feedback_list


def evaluate_mountain_climber_form(frame, landmarks):
    state = fr.mountain_climber_rep_state(landmarks)
    active_side = state.get("active_side", "none")
    if active_side == "left":
        knee_to_chest = state["left_knee_to_chest"]
    elif active_side == "right":
        knee_to_chest = state["right_knee_to_chest"]
    else:
        knee_to_chest = min(state["left_knee_to_chest"], state["right_knee_to_chest"])

    alignment_score = fr.evaluate_mountain_climber_body_alignment(state["body_alignment"])
    knee_drive_score = fr.evaluate_mountain_climber_knee_drive(knee_to_chest)
    hip_stability_score = fr.evaluate_mountain_climber_hip_stability(
        state["hip_deviation"],
        state["pelvis_tilt"],
    )
    arm_support_score = fr.evaluate_mountain_climber_arm_support(
        state["elbow_avg"],
        state["shoulder_wrist_offset"],
    )
    total_score = int(
        0.30 * alignment_score +
        0.30 * knee_drive_score +
        0.25 * hip_stability_score +
        0.15 * arm_support_score
    )
    feedback_list = fr.generate_mountain_climber_feedback(
        state["body_alignment"],
        knee_to_chest,
        state["hip_deviation"],
        state["pelvis_tilt"],
        state["elbow_avg"],
        state["shoulder_wrist_offset"],
    )
    metrics = {
        "exercise_type": "mountain_climbers",
        "landmarks": landmarks,
        "active_side": active_side,
        "body_alignment": state["body_alignment"],
        "left_knee_to_chest": state["left_knee_to_chest"],
        "right_knee_to_chest": state["right_knee_to_chest"],
        "knee_drive_score": knee_drive_score,
        "alignment_score": alignment_score,
        "hip_stability_score": hip_stability_score,
        "arm_support_score": arm_support_score,
        "total_score": total_score,
        **state,
    }
    return frame, metrics, feedback_list


def evaluate_lateral_raise_form(frame, landmarks):
    state = fr.lateral_raise_rep_state(landmarks)
    height_score, elbow_height_score, elbow_bend_score, symmetry_score, torso_score = fr.score_lateral_raise(
        state["elbow_avg"],
        state["wrist_level"],
        state["elbow_level"],
        state["arm_symmetry"],
        state["torso_lean"],
    )
    total_score = int((height_score + elbow_height_score + elbow_bend_score + symmetry_score + torso_score) / 5)
    feedback_list = fr.generate_lateral_raise_feedback(
        state["elbow_avg"],
        state["wrist_level"],
        state["elbow_level"],
        state["arm_symmetry"],
        state["torso_lean"],
    )
    metrics = {
        "exercise_type": "lateral_raise",
        "landmarks": landmarks,
        **state,
        "height_score": height_score,
        "elbow_height_score": elbow_height_score,
        "elbow_bend_score": elbow_bend_score,
        "symmetry_score": symmetry_score,
        "torso_score": torso_score,
        "total_score": total_score,
    }
    return frame, metrics, feedback_list


def evaluate_form(frame, landmarks):
    """
    Evaluare genoflexiune.
    """
    left_shoulder = (landmarks[11].x, landmarks[11].y)
    right_shoulder = (landmarks[12].x, landmarks[12].y)
    left_hip = (landmarks[23].x, landmarks[23].y)
    right_hip = (landmarks[24].x, landmarks[24].y)
    left_knee = (landmarks[25].x, landmarks[25].y)
    left_ankle = (landmarks[27].x, landmarks[27].y)
    right_knee = (landmarks[26].x, landmarks[26].y)
    right_ankle = (landmarks[28].x, landmarks[28].y)

    trunk_angle = fr.calculate_trunk_angle(left_hip, left_shoulder)
    squat_angle = fr.calculate_squat_angle(left_hip, left_knee, left_ankle)
    knee_offset, max_offset, _ = fr.check_knee_position(left_hip, left_knee, left_ankle)

    delta_x = right_hip[0] - left_hip[0]
    delta_y = right_hip[1] - left_hip[1]
    if delta_x == 0:
        pelvis_angle = 90
    else:
        pelvis_angle = math.degrees(math.atan(abs(delta_y / delta_x)))

    trunk_score = fr.evaluate_trunk(trunk_angle)
    squat_score = fr.evaluate_squat_depth(squat_angle)
    knee_score = fr.evaluate_knee_position(knee_offset, max_offset)
    butt_score = fr.evaluate_butt_wink(left_hip, left_knee, left_ankle)
    pelvis_score = fr.evaluate_pelvic_tilt(left_hip, right_hip)

    left_off_rel = fr.knee_offset_relative(left_hip, left_knee, left_ankle)
    right_off_rel = fr.knee_offset_relative(right_hip, right_knee, right_ankle)
    symmetry = fr.symmetry_score(left_off_rel, right_off_rel)

    total_score = int((trunk_score + squat_score + knee_score + butt_score + pelvis_score + symmetry) / 6)

    feedback_list = fr.generate_feedback(
        trunk_angle, squat_angle, knee_offset, max_offset,
        left_hip, left_knee, left_ankle, right_hip
    )

    metrics = {
        'exercise_type': 'genoflexiune',
        'landmarks': landmarks,
        'trunk_angle': trunk_angle,
        'squat_angle': squat_angle,
        'knee_offset': knee_offset,
        'max_offset': max_offset,
        'pelvis_angle': pelvis_angle,
        'total_score': total_score,
        'symmetry_score': symmetry,
        'left_knee_offset_rel': left_off_rel,
        'right_knee_offset_rel': right_off_rel
    }

    return frame, metrics, feedback_list


def evaluate_deadlift_form(frame, landmarks):
    """
    Evalueaza biomecanic forma unui deadlift.
    """
    from feedback_rules import (
        calculate_trunk_angle,
        check_knee_position,
        calculate_squat_angle,
        evaluate_deadlift_trunk,
        evaluate_deadlift_knee_offset,
        evaluate_deadlift_squat_angle,
        evaluate_deadlift_spine_neutrality,
        generate_deadlift_feedback
    )

    left_shoulder = (landmarks[11].x, landmarks[11].y)
    left_hip = (landmarks[23].x, landmarks[23].y)
    left_knee = (landmarks[25].x, landmarks[25].y)
    left_ankle = (landmarks[27].x, landmarks[27].y)
    mid_back = (landmarks[12].x, landmarks[12].y)

    trunk_angle = calculate_trunk_angle(left_hip, left_shoulder)
    knee_offset, max_offset, _ = check_knee_position(left_hip, left_knee, left_ankle)
    squat_angle = calculate_squat_angle(left_hip, left_knee, left_ankle)

    trunk_score = evaluate_deadlift_trunk(trunk_angle)
    knee_score = evaluate_deadlift_knee_offset(knee_offset)
    squat_score = evaluate_deadlift_squat_angle(squat_angle)
    spine_score, spine_feedback = evaluate_deadlift_spine_neutrality(left_hip, mid_back, left_shoulder)

    total_score = int((trunk_score + knee_score + squat_score + spine_score) / 4)
    feedback_list = generate_deadlift_feedback(trunk_angle, knee_offset, squat_angle)

    if feedback_list is None:
        feedback_list = []

    feedback_list.append(spine_feedback)

    metrics = {
        'exercise_type': 'deadlift',
        'landmarks': landmarks,
        'trunk_angle': trunk_angle,
        'knee_offset': knee_offset,
        'max_offset': max_offset,
        'squat_angle': squat_angle,
        'spine_score': spine_score,
        'total_score': total_score
    }

    return frame, metrics, feedback_list


def evaluate_situp_form(frame, landmarks):
    """
    Evaluare simpla pentru abdomene pe un frame relevant al repetarii.
    """
    left_shoulder = (landmarks[11].x, landmarks[11].y)
    right_shoulder = (landmarks[12].x, landmarks[12].y)
    left_hip = (landmarks[23].x, landmarks[23].y)
    right_hip = (landmarks[24].x, landmarks[24].y)
    left_knee = (landmarks[25].x, landmarks[25].y)
    nose = (landmarks[0].x, landmarks[0].y)

    torso_angle = fr.calculate_angle(left_shoulder, left_hip, left_knee)
    hip_variation = abs(left_hip[1] - right_hip[1])
    shoulder_delta = abs(left_shoulder[1] - right_shoulder[1])
    neck_angle = fr.calculate_angle(nose, left_shoulder, left_hip)

    amplitude_proxy = max(0.0, 180 - torso_angle)

    amplitude_score = fr.evaluate_situp_amplitude(amplitude_proxy)
    neck_score = fr.evaluate_situp_neck(neck_angle)
    hip_score = fr.evaluate_situp_hip_stability(hip_variation)
    symmetry_score = fr.evaluate_situp_symmetry(shoulder_delta)

    total_score = int((amplitude_score + neck_score + hip_score + symmetry_score) / 4)

    feedback_list = fr.generate_situp_feedback(
        amplitude_proxy,
        neck_angle,
        hip_variation,
        shoulder_delta
    )

    metrics = {
        'exercise_type': 'abdomene',
        'landmarks': landmarks,
        'torso_angle': torso_angle,
        'amplitude_proxy': amplitude_proxy,
        'neck_angle': neck_angle,
        'hip_variation': hip_variation,
        'shoulder_delta': shoulder_delta,
        'total_score': total_score,
    }

    return frame, metrics, feedback_list


def evaluate_pullup_form(frame, landmarks):
    """
    Evaluare simpla pentru tractiuni pe un frame relevant al repetarii.
    """
    left_shoulder = (landmarks[11].x, landmarks[11].y)
    right_shoulder = (landmarks[12].x, landmarks[12].y)
    left_elbow = (landmarks[13].x, landmarks[13].y)
    right_elbow = (landmarks[14].x, landmarks[14].y)
    left_wrist = (landmarks[15].x, landmarks[15].y)
    right_wrist = (landmarks[16].x, landmarks[16].y)
    left_hip = (landmarks[23].x, landmarks[23].y)
    right_hip = (landmarks[24].x, landmarks[24].y)
    left_ankle = (landmarks[27].x, landmarks[27].y)
    right_ankle = (landmarks[28].x, landmarks[28].y)

    left_elbow_angle = fr.calculate_angle(left_shoulder, left_elbow, left_wrist)
    right_elbow_angle = fr.calculate_angle(right_shoulder, right_elbow, right_wrist)
    avg_elbow_angle = (left_elbow_angle + right_elbow_angle) / 2.0

    shoulder_mid = (
        (left_shoulder[0] + right_shoulder[0]) / 2.0,
        (left_shoulder[1] + right_shoulder[1]) / 2.0
    )
    hip_mid = (
        (left_hip[0] + right_hip[0]) / 2.0,
        (left_hip[1] + right_hip[1]) / 2.0
    )
    ankle_mid = (
        (left_ankle[0] + right_ankle[0]) / 2.0,
        (left_ankle[1] + right_ankle[1]) / 2.0
    )

    body_alignment_angle = fr.calculate_angle(shoulder_mid, hip_mid, ankle_mid)
    swing_amount = abs(shoulder_mid[0] - hip_mid[0])

    top_score = fr.evaluate_pullup_top_position(avg_elbow_angle)
    bottom_score = fr.evaluate_pullup_bottom_position(avg_elbow_angle)
    alignment_score = fr.evaluate_pullup_body_alignment(body_alignment_angle)
    symmetry_score = fr.evaluate_pullup_symmetry(left_elbow_angle, right_elbow_angle)
    swing_score = fr.evaluate_pullup_swing(swing_amount)

    total_score = int((top_score + bottom_score + alignment_score + symmetry_score + swing_score) / 5)

    feedback_list = fr.generate_pullup_feedback(
        avg_elbow_angle,
        avg_elbow_angle,
        body_alignment_angle,
        left_elbow_angle,
        right_elbow_angle,
        swing_amount
    )

    metrics = {
        'exercise_type': 'tractiuni',
        'landmarks': landmarks,
        'left_elbow_angle': left_elbow_angle,
        'right_elbow_angle': right_elbow_angle,
        'avg_elbow_angle': avg_elbow_angle,
        'body_alignment_angle': body_alignment_angle,
        'swing_amount': swing_amount,
        'total_score': total_score,
    }

    return frame, metrics, feedback_list


def evalueaza_forma_fandare(frame, puncte):
    """
    Returneaza (frame, date_postura, feedback_list).
    - date_postura: dict prietenos (chei in romana) + 'scor_total' si 'puncte_cheie'
    """
    date_postura = analizeaza_postura_fandare(puncte)
    scor, feedback = evalueaza_fandare(date_postura)

    date_postura = {
        **date_postura,
        'scor_total': scor,
        'tip_exercitiu': 'fandare',
        'exercise_type': 'fandare',
        'landmarks': puncte,
        'total_score': scor,
        'puncte': puncte
    }
    return frame, date_postura, feedback


def draw_colored_landmarks(
    frame,
    landmarks,
    trunk_angle=None,
    squat_angle=None,
    knee_offset=None,
    max_offset=None,
    exercise_type="genoflexiune",
    date_postura=None,
):
    """
    Deseneaza linii colorate intre punctele relevante in functie de corectitudine si tipul exercitiului.
    """
    h, w = frame.shape[:2]

    def get_point(index):
        return int(landmarks[index].x * w), int(landmarks[index].y * h)

    if exercise_type == "genoflexiune":
        shoulder = get_point(11)
        hip = get_point(23)
        knee = get_point(25)
        ankle = get_point(27)

        cv2.line(frame, shoulder, hip, (255, 0, 0), 4)

        color_thigh = (0, 255, 0) if (squat_angle or 180) <= 110 else (0, 0, 255)
        cv2.line(frame, hip, knee, color_thigh, 4)

        if max_offset is None:
            max_offset = 1.0
        color_shin = (0, 255, 0) if abs(knee_offset or 0) <= max_offset else (0, 0, 255)
        cv2.line(frame, knee, ankle, color_shin, 4)

    elif exercise_type == "flotare":
        shoulder = get_point(11)
        elbow = get_point(13)
        wrist = get_point(15)
        hip = get_point(23)

        color_trunk = (0, 255, 0) if 169 <= (trunk_angle or 0) <= 190 else (0, 0, 255)
        cv2.line(frame, shoulder, hip, color_trunk, 4)

        cv2.line(frame, shoulder, elbow, (255, 0, 0), 4)
        cv2.line(frame, elbow, wrist, (255, 0, 0), 4)

        cv2.putText(
            frame,
            f"Aliniere corp: {(trunk_angle or 0):.1f}°",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2,
            cv2.LINE_AA
        )

    elif exercise_type == "deadlift":
        shoulder = get_point(11)
        mid_back = get_point(23)
        hip = get_point(23)
        knee = get_point(25)
        ankle = get_point(27)

        trunk_color = (0, 255, 0) if 0 <= (trunk_angle or 999) <= 10 else (0, 0, 255)
        cv2.line(frame, shoulder, mid_back, trunk_color, 4)

        thigh_color = (0, 255, 0) if 70 <= (squat_angle or 0) <= 90 else (0, 0, 255)
        cv2.line(frame, hip, knee, thigh_color, 4)

        if max_offset is None:
            max_offset = 1.0
        shin_color = (0, 255, 0) if abs(knee_offset or 0) <= max_offset else (0, 0, 255)
        cv2.line(frame, knee, ankle, shin_color, 4)

    elif exercise_type == "abdomene":
        shoulder = get_point(11)
        hip = get_point(23)
        knee = get_point(25)
        nose = get_point(0)

        torso_angle_local = fr.calculate_angle(
            (landmarks[11].x, landmarks[11].y),
            (landmarks[23].x, landmarks[23].y),
            (landmarks[25].x, landmarks[25].y)
        )
        amplitude_proxy = max(0.0, 180 - torso_angle_local)
        neck_angle = fr.calculate_angle(
            (landmarks[0].x, landmarks[0].y),
            (landmarks[11].x, landmarks[11].y),
            (landmarks[23].x, landmarks[23].y)
        )

        trunk_color = (0, 255, 0) if amplitude_proxy >= 25 else (0, 0, 255)
        neck_color = (0, 255, 0) if 145 <= neck_angle <= 190 else (0, 0, 255)

        cv2.line(frame, shoulder, hip, trunk_color, 4)
        cv2.line(frame, hip, knee, (255, 0, 0), 4)
        cv2.line(frame, nose, shoulder, neck_color, 3)

        cv2.putText(
            frame,
            f"Abdomene: {amplitude_proxy:.1f}",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2,
            cv2.LINE_AA
        )

    elif exercise_type == "tractiuni":
        left_shoulder = get_point(11)
        right_shoulder = get_point(12)
        left_elbow = get_point(13)
        right_elbow = get_point(14)
        left_wrist = get_point(15)
        right_wrist = get_point(16)
        left_hip = get_point(23)
        right_hip = get_point(24)
        left_ankle = get_point(27)
        right_ankle = get_point(28)

        left_elbow_angle = fr.calculate_angle(
            (landmarks[11].x, landmarks[11].y),
            (landmarks[13].x, landmarks[13].y),
            (landmarks[15].x, landmarks[15].y)
        )
        right_elbow_angle = fr.calculate_angle(
            (landmarks[12].x, landmarks[12].y),
            (landmarks[14].x, landmarks[14].y),
            (landmarks[16].x, landmarks[16].y)
        )

        arm_left_color = (0, 255, 0) if left_elbow_angle <= 110 else (0, 0, 255)
        arm_right_color = (0, 255, 0) if right_elbow_angle <= 110 else (0, 0, 255)

        shoulder_mid = (
            (landmarks[11].x + landmarks[12].x) / 2.0,
            (landmarks[11].y + landmarks[12].y) / 2.0
        )
        hip_mid = (
            (landmarks[23].x + landmarks[24].x) / 2.0,
            (landmarks[23].y + landmarks[24].y) / 2.0
        )
        ankle_mid = (
            (landmarks[27].x + landmarks[28].x) / 2.0,
            (landmarks[27].y + landmarks[28].y) / 2.0
        )
        body_alignment_angle_local = fr.calculate_angle(shoulder_mid, hip_mid, ankle_mid)
        trunk_color = (0, 255, 0) if 165 <= body_alignment_angle_local <= 195 else (0, 0, 255)

        cv2.line(frame, left_shoulder, left_elbow, arm_left_color, 4)
        cv2.line(frame, left_elbow, left_wrist, arm_left_color, 4)
        cv2.line(frame, right_shoulder, right_elbow, arm_right_color, 4)
        cv2.line(frame, right_elbow, right_wrist, arm_right_color, 4)

        hip_mid_px = ((left_hip[0] + right_hip[0]) // 2, (left_hip[1] + right_hip[1]) // 2)
        shoulder_mid_px = ((left_shoulder[0] + right_shoulder[0]) // 2, (left_shoulder[1] + right_shoulder[1]) // 2)
        ankle_mid_px = ((left_ankle[0] + right_ankle[0]) // 2, (left_ankle[1] + right_ankle[1]) // 2)

        cv2.line(frame, shoulder_mid_px, hip_mid_px, trunk_color, 4)
        cv2.line(frame, hip_mid_px, ankle_mid_px, trunk_color, 4)

        avg_angle = (left_elbow_angle + right_elbow_angle) / 2.0
        cv2.putText(
            frame,
            f"Tractiuni: {avg_angle:.1f}°",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2,
            cv2.LINE_AA
        )

    elif exercise_type == "fandare":
        dp = date_postura or {}
        unghi_trunchi = dp.get('unghi_trunchi', trunk_angle if trunk_angle is not None else 999)
        unghi_genunchi_fata = dp.get('unghi_genunchi_fata', squat_angle if squat_angle is not None else 999)
        genunchi_peste_varf = dp.get('genunchi_peste_varf', knee_offset if knee_offset is not None else 1.0)
        limita_offset = dp.get('limita_offset', max_offset if max_offset is not None else 1.0)
        adancime_spate = dp.get('adancime_spate', -1.0)

        fH, fK, fA, bH, bK, bA, L_SH, R_SH = dp.get('puncte_cheie', (23, 25, 27, 24, 26, 28, 11, 12))

        def Pxy(idx):
            return int(landmarks[idx].x * w), int(landmarks[idx].y * h)

        left_hip, right_hip = Pxy(23), Pxy(24)
        hip_mid = ((left_hip[0] + right_hip[0]) // 2, (left_hip[1] + right_hip[1]) // 2)
        left_sh, right_sh = Pxy(L_SH), Pxy(R_SH)
        shoulder_mid = ((left_sh[0] + right_sh[0]) // 2, (left_sh[1] + right_sh[1]) // 2)

        front_hip, front_knee, front_ank = Pxy(fH), Pxy(fK), Pxy(fA)
        back_hip, back_knee, back_ank = Pxy(bH), Pxy(bK), Pxy(bA)

        verde, rosu, portocaliu, alb = (0, 255, 0), (0, 0, 255), (0, 165, 255), (255, 255, 255)

        tr_ok = (unghi_trunchi <= 10)
        co_ok = (80 <= unghi_genunchi_fata <= 100)
        ga_ok = (abs(genunchi_peste_varf) <= (limita_offset or 1.0))
        bk_ok = (adancime_spate >= -0.02)

        cv2.line(frame, hip_mid, shoulder_mid, verde if tr_ok else rosu, 4)
        cv2.line(frame, front_hip, front_knee, verde if co_ok else rosu, 4)
        cv2.line(frame, front_knee, front_ank, verde if ga_ok else rosu, 4)
        cv2.line(frame, back_knee, back_ank, verde if bk_ok else portocaliu, 4)

        scor = dp.get('scor_total', None)
        if scor is not None:
            cv2.putText(
                frame,
                f"Fandare: {scor}%",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                alb,
                2,
                cv2.LINE_AA
            )

    elif exercise_type == "plank":
        left_shoulder_px = get_point(11)
        right_shoulder_px = get_point(12)
        left_hip_px = get_point(23)
        right_hip_px = get_point(24)
        left_ankle_px = get_point(27)
        right_ankle_px = get_point(28)
        left_elbow_px = get_point(13)
        right_elbow_px = get_point(14)

        sh_mid_px = (
            (left_shoulder_px[0] + right_shoulder_px[0]) // 2,
            (left_shoulder_px[1] + right_shoulder_px[1]) // 2
        )

        hip_mid_px = (
            (left_hip_px[0] + right_hip_px[0]) // 2,
            (left_hip_px[1] + right_hip_px[1]) // 2
        )

        ank_mid_px = (
            (left_ankle_px[0] + right_ankle_px[0]) // 2,
            (left_ankle_px[1] + right_ankle_px[1]) // 2
        )

        elbow_mid_px = (
            (left_elbow_px[0] + right_elbow_px[0]) // 2,
            (left_elbow_px[1] + right_elbow_px[1]) // 2
        )

        sh_mid_norm = (
            (landmarks[11].x + landmarks[12].x) / 2.0,
            (landmarks[11].y + landmarks[12].y) / 2.0
        )

        hip_mid_norm = (
            (landmarks[23].x + landmarks[24].x) / 2.0,
            (landmarks[23].y + landmarks[24].y) / 2.0
        )

        ank_mid_norm = (
            (landmarks[27].x + landmarks[28].x) / 2.0,
            (landmarks[27].y + landmarks[28].y) / 2.0
        )

        body_angle = fr.calculate_angle(
            sh_mid_norm,
            hip_mid_norm,
            ank_mid_norm
        )

        trunk_color = (0, 255, 0) if 155 <= body_angle <= 205 else (0, 0, 255)

        cv2.line(frame, sh_mid_px, hip_mid_px, trunk_color, 4)
        cv2.line(frame, hip_mid_px, ank_mid_px, trunk_color, 4)
        cv2.line(frame, sh_mid_px, elbow_mid_px, (255, 0, 0), 3)

        cv2.putText(
            frame,
            f"Plank: {body_angle:.1f}",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2,
            cv2.LINE_AA
        )
    
    elif exercise_type == "bench_press":
        left_shoulder = get_point(11)
        right_shoulder = get_point(12)
        left_elbow = get_point(13)
        right_elbow = get_point(14)
        left_wrist = get_point(15)
        right_wrist = get_point(16)

        left_elbow_angle = fr.calculate_angle(
            (landmarks[11].x, landmarks[11].y),
            (landmarks[13].x, landmarks[13].y),
            (landmarks[15].x, landmarks[15].y)
        )
        right_elbow_angle = fr.calculate_angle(
            (landmarks[12].x, landmarks[12].y),
            (landmarks[14].x, landmarks[14].y),
            (landmarks[16].x, landmarks[16].y)
        )

        left_color = (0, 255, 0) if 70 <= left_elbow_angle <= 110 else (0, 0, 255)
        right_color = (0, 255, 0) if 70 <= right_elbow_angle <= 110 else (0, 0, 255)

        cv2.line(frame, left_shoulder, left_elbow, left_color, 4)
        cv2.line(frame, left_elbow, left_wrist, left_color, 4)

        cv2.line(frame, right_shoulder, right_elbow, right_color, 4)
        cv2.line(frame, right_elbow, right_wrist, right_color, 4)

        avg_angle = (left_elbow_angle + right_elbow_angle) / 2.0

        cv2.putText(
            frame,
            f"Bench Press: {avg_angle:.1f}°",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2,
            cv2.LINE_AA
        )
    elif exercise_type == "biceps_curl":
        left_shoulder = get_point(11)
        right_shoulder = get_point(12)
        left_elbow = get_point(13)
        right_elbow = get_point(14)
        left_wrist = get_point(15)
        right_wrist = get_point(16)

        left_angle = fr.calculate_angle(
            (landmarks[11].x, landmarks[11].y),
            (landmarks[13].x, landmarks[13].y),
            (landmarks[15].x, landmarks[15].y)
        )
        right_angle = fr.calculate_angle(
            (landmarks[12].x, landmarks[12].y),
            (landmarks[14].x, landmarks[14].y),
            (landmarks[16].x, landmarks[16].y)
        )
        left_color = (0, 255, 0) if left_angle <= 75 else (0, 0, 255)
        right_color = (0, 255, 0) if right_angle <= 75 else (0, 0, 255)
        cv2.line(frame, left_shoulder, left_elbow, left_color, 4)
        cv2.line(frame, left_elbow, left_wrist, left_color, 4)
        cv2.line(frame, right_shoulder, right_elbow, right_color, 4)
        cv2.line(frame, right_elbow, right_wrist, right_color, 4)
        cv2.putText(frame, f"Biceps Curl: {((left_angle + right_angle) / 2):.1f}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,255,255), 2, cv2.LINE_AA)

    elif exercise_type == "mountain_climbers":
        left_shoulder = get_point(11)
        right_shoulder = get_point(12)
        left_elbow = get_point(13)
        right_elbow = get_point(14)
        left_wrist = get_point(15)
        right_wrist = get_point(16)
        left_hip = get_point(23)
        right_hip = get_point(24)
        left_knee = get_point(25)
        right_knee = get_point(26)
        left_ankle = get_point(27)
        right_ankle = get_point(28)

        shoulder_mid = ((left_shoulder[0] + right_shoulder[0]) // 2, (left_shoulder[1] + right_shoulder[1]) // 2)
        hip_mid = ((left_hip[0] + right_hip[0]) // 2, (left_hip[1] + right_hip[1]) // 2)
        ankle_mid = ((left_ankle[0] + right_ankle[0]) // 2, (left_ankle[1] + right_ankle[1]) // 2)

        state = fr.mountain_climber_rep_state(landmarks)
        active_side = state.get("active_side", "none")
        knee_to_chest = min(state["left_knee_to_chest"], state["right_knee_to_chest"])
        alignment_score = fr.evaluate_mountain_climber_body_alignment(state["body_alignment"])
        knee_score = fr.evaluate_mountain_climber_knee_drive(knee_to_chest)
        hip_score = fr.evaluate_mountain_climber_hip_stability(state["hip_deviation"], state["pelvis_tilt"])
        arm_score = fr.evaluate_mountain_climber_arm_support(state["elbow_avg"], state["shoulder_wrist_offset"])
        total_score = int(0.30 * alignment_score + 0.30 * knee_score + 0.25 * hip_score + 0.15 * arm_score)

        arm_color = (0, 255, 0) if arm_score >= 70 else (0, 0, 255)
        trunk_color = (0, 255, 0) if alignment_score >= 70 and hip_score >= 70 else (0, 0, 255)
        knee_color = (0, 255, 0) if knee_score >= 70 else (0, 0, 255)

        cv2.line(frame, left_shoulder, left_elbow, arm_color, 4)
        cv2.line(frame, left_elbow, left_wrist, arm_color, 4)
        cv2.line(frame, right_shoulder, right_elbow, arm_color, 4)
        cv2.line(frame, right_elbow, right_wrist, arm_color, 4)
        cv2.line(frame, shoulder_mid, hip_mid, trunk_color, 4)
        cv2.line(frame, hip_mid, ankle_mid, trunk_color, 4)

        if active_side == "left":
            cv2.line(frame, hip_mid, left_knee, knee_color, 4)
        elif active_side == "right":
            cv2.line(frame, hip_mid, right_knee, knee_color, 4)

        cv2.putText(frame, f"Mountain Climbers: {active_side} {total_score}%", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,255,255), 2, cv2.LINE_AA)

    elif exercise_type == "lateral_raise":
        left_shoulder = get_point(11)
        right_shoulder = get_point(12)
        left_elbow = get_point(13)
        right_elbow = get_point(14)
        left_wrist = get_point(15)
        right_wrist = get_point(16)
        left_level = abs(landmarks[15].y - landmarks[11].y)
        right_level = abs(landmarks[16].y - landmarks[12].y)
        left_color = (0, 255, 0) if left_level <= 0.12 else (0, 0, 255)
        right_color = (0, 255, 0) if right_level <= 0.12 else (0, 0, 255)
        cv2.line(frame, left_shoulder, left_elbow, left_color, 4)
        cv2.line(frame, left_elbow, left_wrist, left_color, 4)
        cv2.line(frame, right_shoulder, right_elbow, right_color, 4)
        cv2.line(frame, right_elbow, right_wrist, right_color, 4)
        cv2.putText(frame, "Lateral Raise", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,255,255), 2, cv2.LINE_AA)
    cv2.putText(
        frame,
        "Verde = corect, Rosu = incorect",
        (10, h - 10),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (255, 255, 255),
        1,
        cv2.LINE_AA
    )

    return frame
