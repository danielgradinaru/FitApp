import cv2
import numpy as np

from pose_estimation import PoseDetector
from feedback_rules import (
    calculate_body_alignment,
    calculate_trunk_angle,
    calculate_squat_angle,
    check_knee_position,
    calculate_angle,
)


MIN_DETECTION_SAMPLES = 60
MAX_DETECTION_FRAME_SKIP = 2


def _p(arr, q):
    arr = np.array(arr, dtype=float)
    if len(arr) == 0:
        return 0.0
    return float(np.percentile(arr, q))


def _span(arr, q_low=10, q_high=90):
    arr = np.array(arr, dtype=float)
    if len(arr) == 0:
        return 0.0
    return float(np.percentile(arr, q_high) - np.percentile(arr, q_low))


def _safe_dist(a, b):
    return float(np.hypot(a[0] - b[0], a[1] - b[1]))


def _mid(a, b):
    return ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)


def _visible(lm, indexes, threshold=0.55):
    ok = 0
    for idx in indexes:
        if getattr(lm[idx], "visibility", 1.0) >= threshold:
            ok += 1
    return ok >= int(len(indexes) * 0.75)


def _detection_trim_frames(total_frames, fps):
    """
    Returneaza cate cadre ignoram la inceput si la final pentru detectarea automata.

    Scop: in multe videoclipuri utilizatorul intra in cadru, se aseaza pe saltea,
    porneste/opreste camera etc. Acele cadre nu reprezinta exercitiul si pot
    schimba statisticile globale, de exemplu flotare -> deadlift.

    Trimming-ul este conservator:
    - pentru clipuri lungi ignoram aproximativ primele 12% si ultimele 8%,
      dar cu limite maxime in secunde;
    - pentru clipuri scurte ignoram mult mai putin;
    - pastram mereu suficient continut pentru analiza.
    """
    if total_frames <= 0:
        return 0, 0

    fps = float(fps or 30.0)
    if fps <= 1.0:
        fps = 30.0

    duration = total_frames / fps

    if duration >= 10.0:
        start_trim = int(min(total_frames * 0.12, fps * 4.0))
        end_trim = int(min(total_frames * 0.08, fps * 2.5))
    elif duration >= 6.0:
        start_trim = int(min(total_frames * 0.08, fps * 1.0))
        end_trim = int(min(total_frames * 0.05, fps * 0.75))
    else:
        start_trim = 0
        end_trim = 0

    # Nu permitem ca trimming-ul sa elimine prea mult din clip.
    max_total_trim = int(total_frames * 0.35)
    if start_trim + end_trim > max_total_trim:
        scale = max_total_trim / float(start_trim + end_trim)
        start_trim = int(start_trim * scale)
        end_trim = int(end_trim * scale)

    return max(0, start_trim), max(0, end_trim)


def detect_exercise(
    video_path: str,
    sample_every_n_frames=None,
    max_samples: int = 180,
    max_frame_width: int = 640,
    trim_intro_outro: bool = True,
    crop_top_ratio: float = 0.0,
) -> str:
    detector = PoseDetector()
    cap = cv2.VideoCapture(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    source_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    source_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    source_is_portrait = source_height > source_width * 1.15
    if fps <= 1.0:
        fps = 30.0

    trim_start_frames, trim_end_frames = (0, 0)
    if trim_intro_outro:
        trim_start_frames, trim_end_frames = _detection_trim_frames(total_frames, fps)

    if sample_every_n_frames is None:
        if total_frames <= 120:
            sample_every_n_frames = 1
        else:
            sample_every_n_frames = min(
                MAX_DETECTION_FRAME_SKIP,
                max(1, total_frames // MIN_DETECTION_SAMPLES)
            )
    else:
        sample_every_n_frames = max(1, int(sample_every_n_frames))

    body_align = []
    vertical_body_align = []
    trunk = []

    elbow_avg = []
    knee_L = []
    knee_R = []
    knee_asym = []
    knee_forward = []

    hip_y = []
    hip_x = []
    shoulder_mid_y = []
    nose_y = []

    wrist_mid_y = []
    wrist_mid_x = []
    elbow_mid_y = []

    knee_dx = []
    knee_y_diff = []
    left_knee_y_values = []
    right_knee_y_values = []
    left_ankle_y_values = []
    right_ankle_y_values = []
    left_knee_x_values = []
    right_knee_x_values = []
    ankle_distance = []
    shoulder_hip_dy = []
    wrist_above_shoulder_ratio = []

    elbow_y_relative_to_shoulder = []
    wrist_y_relative_to_shoulder = []
    shoulder_hip_dx = []
    torso_flatness = []
    body_static_score_values = []
    plank_hip_deviation_values = []

    wrist_shoulder_rel_y = []
    elbow_above_shoulder = []

    wrist_above_elbow_ratio = []
    hip_shoulder_rel_y = []

    wrist_hip_rel_y = []
    wrist_chest_rel_y = []

    wrist_to_shoulder_dist = []
    wrist_to_hip_dist = []

    shoulder_width_values = []
    body_height_frame_values = []

    samples = 0
    frame_idx = 0

    important_idx = [0, 11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28]

    shoulder_mid = (0.5, 0.5)
    ankle_mid = (0.5, 1.0)

    while True:
        ok, frame = cap.read()
        if not ok:
            break

        frame_idx += 1

        # Ignoram cadrele de setup/iesire din clip.
        # Exemplu: utilizatorul se aseaza in pozitie de flotare, iar detectorul
        # vede cateva cadre verticale/aplecate si le poate interpreta ca deadlift.
        if trim_start_frames and frame_idx <= trim_start_frames:
            continue

        if (
            trim_end_frames
            and total_frames > 0
            and frame_idx >= total_frames - trim_end_frames
        ):
            continue

        if frame_idx % sample_every_n_frames != 0:
            continue

        height, width = frame.shape[:2]
        if max_frame_width and width > max_frame_width:
            scale = max_frame_width / float(width)
            resized_size = (
                max(2, int(width * scale)),
                max(2, int(height * scale)),
            )
            frame = cv2.resize(frame, resized_size, interpolation=cv2.INTER_AREA)

        if crop_top_ratio > 0:
            crop_start = int(frame.shape[0] * crop_top_ratio)
            if crop_start > 0 and frame.shape[0] - crop_start >= 2:
                frame = frame[crop_start:, :]

        results = detector.detect_pose(frame)
        lm = detector.get_landmarks(results)

        if not lm:
            continue

        if not _visible(lm, important_idx):
            continue

        L_sh = (lm[11].x, lm[11].y)
        R_sh = (lm[12].x, lm[12].y)
        L_el = (lm[13].x, lm[13].y)
        R_el = (lm[14].x, lm[14].y)
        L_wr = (lm[15].x, lm[15].y)
        R_wr = (lm[16].x, lm[16].y)

        L_hip = (lm[23].x, lm[23].y)
        R_hip = (lm[24].x, lm[24].y)
        L_knee = (lm[25].x, lm[25].y)
        R_knee = (lm[26].x, lm[26].y)
        L_ank = (lm[27].x, lm[27].y)
        R_ank = (lm[28].x, lm[28].y)

        nose = (lm[0].x, lm[0].y)

        shoulder_mid = _mid(L_sh, R_sh)
        hip_mid = _mid(L_hip, R_hip)
        ankle_mid = _mid(L_ank, R_ank)
        elbow_mid = _mid(L_el, R_el)
        wrist_mid = _mid(L_wr, R_wr)

        shoulder_width_values.append(_safe_dist(L_sh, R_sh))

        wrist_mid_y.append(wrist_mid[1])
        wrist_mid_x.append(wrist_mid[0])
        elbow_mid_y.append(elbow_mid[1])

        elbow_y_relative_to_shoulder.append(elbow_mid[1] - shoulder_mid[1])
        wrist_y_relative_to_shoulder.append(wrist_mid[1] - shoulder_mid[1])
        shoulder_hip_dx.append(abs(shoulder_mid[0] - hip_mid[0]))

        torso_flatness.append(abs(shoulder_mid[1] - hip_mid[1]))

        expected_hip_y = (shoulder_mid[1] + ankle_mid[1]) / 2.0
        plank_hip_deviation_values.append(abs(hip_mid[1] - expected_hip_y))

        leg_len_proxy = max(
            1e-6,
            (_safe_dist(L_hip, L_ank) + _safe_dist(R_hip, R_ank)) / 2.0,
        )

        body_height_frame_proxy = max(
            1e-6,
            _safe_dist(shoulder_mid, ankle_mid),
        )
        body_height_frame_values.append(body_height_frame_proxy)

        body_align_left = calculate_body_alignment(L_sh, L_hip, L_ank)
        body_align_right = calculate_body_alignment(R_sh, R_hip, R_ank)
        body_align.append((body_align_left + body_align_right) / 2.0)

        vertical_body_align.append(calculate_angle(shoulder_mid, hip_mid, ankle_mid))

        trunk_left = calculate_trunk_angle(L_hip, L_sh)
        trunk_right = calculate_trunk_angle(R_hip, R_sh)
        trunk.append((trunk_left + trunk_right) / 2.0)

        left_elbow_angle = calculate_angle(L_sh, L_el, L_wr)
        right_elbow_angle = calculate_angle(R_sh, R_el, R_wr)
        elbow_avg.append((left_elbow_angle + right_elbow_angle) / 2.0)

        wrist_up = 0
        if L_wr[1] < L_sh[1]:
            wrist_up += 1
        if R_wr[1] < R_sh[1]:
            wrist_up += 1
        wrist_above_shoulder_ratio.append(wrist_up / 2.0)

        kL = calculate_squat_angle(L_hip, L_knee, L_ank)
        kR = calculate_squat_angle(R_hip, R_knee, R_ank)

        knee_L.append(kL)
        knee_R.append(kR)
        knee_asym.append(abs(kL - kR))

        knee_dx.append(abs(L_knee[0] - R_knee[0]))
        knee_y_diff.append(abs(L_knee[1] - R_knee[1]))
        left_knee_y_values.append(L_knee[1])
        right_knee_y_values.append(R_knee[1])
        left_ankle_y_values.append(L_ank[1])
        right_ankle_y_values.append(R_ank[1])
        left_knee_x_values.append(L_knee[0])
        right_knee_x_values.append(R_knee[0])

        kf_vals = []

        try:
            kfL, _, _ = check_knee_position(L_hip, L_knee, L_ank)
            kf_vals.append(abs(float(kfL)) / leg_len_proxy)
        except Exception:
            pass

        try:
            kfR, _, _ = check_knee_position(R_hip, R_knee, R_ank)
            kf_vals.append(abs(float(kfR)) / leg_len_proxy)
        except Exception:
            pass

        knee_forward.append(float(np.mean(kf_vals)) if kf_vals else 0.0)

        hip_y.append(hip_mid[1])
        hip_x.append(hip_mid[0])
        shoulder_mid_y.append(shoulder_mid[1])
        nose_y.append(nose[1])

        body_static_score_values.append(
            abs(hip_mid[1] - shoulder_mid[1]) +
            abs(hip_mid[0] - shoulder_mid[0])
        )

        shoulder_hip_dy.append(abs(shoulder_mid[1] - hip_mid[1]))
        ankle_distance.append(_safe_dist(L_ank, R_ank) / body_height_frame_proxy)

        wrist_shoulder_rel_y.append(wrist_mid[1] - shoulder_mid[1])

        elbow_above_shoulder.append(
            1.0 if elbow_mid[1] < shoulder_mid[1] else 0.0
        )

        wr_el_count = 0
        if L_wr[1] <= L_el[1] + 0.06:
            wr_el_count += 1
        if R_wr[1] <= R_el[1] + 0.06:
            wr_el_count += 1
        wrist_above_elbow_ratio.append(wr_el_count / 2.0)

        hip_shoulder_rel_y.append(hip_mid[1] - shoulder_mid[1])

        # y crește în jos:
        # wrist_y - hip_y > 0 => palmele sunt sub nivelul șoldului.
        wrist_hip_rel_y.append(wrist_mid[1] - hip_mid[1])

        # Distanțe utile pentru Flotare vs Deadlift.
        wrist_to_shoulder_dist.append(_safe_dist(wrist_mid, shoulder_mid))
        wrist_to_hip_dist.append(_safe_dist(wrist_mid, hip_mid))

        # Proxy nivel piept: între umeri și șold, mai aproape de umeri.
        chest_y = shoulder_mid[1] + 0.25 * (hip_mid[1] - shoulder_mid[1])
        wrist_chest_rel_y.append(abs(wrist_mid[1] - chest_y))

        samples += 1

        if samples >= max_samples:
            break

    cap.release()

    if len(body_align) < 10:
        # Pentru clipuri foarte scurte sau filmate greu, incercam o singura data
        # fara trimming ca fallback, in loc sa returnam direct Necunoscut.
        if trim_intro_outro and (trim_start_frames > 0 or trim_end_frames > 0):
            return detect_exercise(
                video_path,
                sample_every_n_frames=sample_every_n_frames,
                max_samples=max_samples,
                max_frame_width=max_frame_width,
                trim_intro_outro=False,
                crop_top_ratio=crop_top_ratio,
            )
        if crop_top_ratio <= 0 and source_is_portrait:
            return detect_exercise(
                video_path,
                sample_every_n_frames=sample_every_n_frames,
                max_samples=max_samples,
                max_frame_width=max_frame_width,
                trim_intro_outro=trim_intro_outro,
                crop_top_ratio=0.22,
            )
        return "Necunoscut"

    shoulder_width_med = _p(shoulder_width_values, 50)
    torso_proxy = _p(shoulder_hip_dy, 50)
    body_height_frame_med = _p(body_height_frame_values, 50)

    body_height_proxy = max(
        0.25,
        body_height_frame_med,
        shoulder_width_med * 3.0,
        torso_proxy * 2.5,
    )

    align_med = _p(body_align, 50)

    trunk_med = _p(trunk, 50)
    trunk_p75 = _p(trunk, 75)
    trunk_span = _span(trunk)
    elbow_span = _span(elbow_avg)
    elbow_p10 = _p(elbow_avg, 10)
    elbow_p90 = _p(elbow_avg, 90)

    knee_rom = _span(knee_L + knee_R)

    left_knee_p10 = _p(knee_L, 10)
    left_knee_p90 = _p(knee_L, 90)
    right_knee_p10 = _p(knee_R, 10)
    right_knee_p90 = _p(knee_R, 90)

    front_knee_min = min(left_knee_p10, right_knee_p10)
    back_knee_max = max(left_knee_p90, right_knee_p90)

    knee_asym_p90 = _p(knee_asym, 90)
    knee_med = _p(knee_L + knee_R, 50)
    knee_min = _p(knee_L + knee_R, 10)
    left_knee_y_span = _span(left_knee_y_values)
    right_knee_y_span = _span(right_knee_y_values)
    left_ankle_y_span = _span(left_ankle_y_values)
    right_ankle_y_span = _span(right_ankle_y_values)
    knee_motion_span = max(left_knee_y_span, right_knee_y_span)
    ankle_motion_span = max(left_ankle_y_span, right_ankle_y_span)
    left_right_knee_motion_diff = abs(left_knee_y_span - right_knee_y_span)

    hip_drop = _span(hip_y)
    shoulder_y_span = _span(shoulder_mid_y)
    nose_span = _span(nose_y)
    nose_y_span = nose_span
    elbow_y_span = _span(elbow_mid_y)
    wrist_y_span = _span(wrist_mid_y)

    shoulder_hip_dy_med = _p(shoulder_hip_dy, 50)
    shoulder_hip_dy_p10 = _p(shoulder_hip_dy, 10)
    torso_flatness_p75 = _p(torso_flatness, 75)
    wrist_up_med = _p(wrist_above_shoulder_ratio, 50)
    ankle_distance_med = _p(ankle_distance, 50)

    knee_dx_p90 = _p(knee_dx, 90)
    knee_y_p90 = _p(knee_y_diff, 90)

    norm_hip_drop = hip_drop / body_height_proxy
    norm_shoulder_span = shoulder_y_span / body_height_proxy
    norm_nose_span = nose_span / body_height_proxy
    norm_elbow_span = elbow_y_span / body_height_proxy
    norm_wrist_span = wrist_y_span / body_height_proxy

    wrist_shoulder_rel_med = _p(wrist_shoulder_rel_y, 50)
    wrist_shoulder_rel_p10 = _p(wrist_shoulder_rel_y, 10)
    wrist_shoulder_rel_p90 = _p(wrist_shoulder_rel_y, 90)
    elbow_shoulder_rel_med = _p(elbow_y_relative_to_shoulder, 50)
    elbow_shoulder_rel_p10 = _p(elbow_y_relative_to_shoulder, 10)
    elbow_shoulder_rel_p90 = _p(elbow_y_relative_to_shoulder, 90)
    elbow_above_ratio = _p(elbow_above_shoulder, 50)

    wrist_above_elbow_med = _p(wrist_above_elbow_ratio, 50)
    hip_shoulder_rel_med = _p(hip_shoulder_rel_y, 50)
    hip_shoulder_rel_span = _span(hip_shoulder_rel_y)
    norm_hip_shoulder_rel_med = hip_shoulder_rel_med / body_height_proxy

    wrist_hip_rel_med = _p(wrist_hip_rel_y, 50)
    wrist_hip_rel_p75 = _p(wrist_hip_rel_y, 75)

    wrist_chest_rel_min = _p(wrist_chest_rel_y, 10)
    wrist_chest_rel_med = _p(wrist_chest_rel_y, 50)

    norm_wrist_hip_rel_med = wrist_hip_rel_med / body_height_proxy
    norm_wrist_hip_rel_p75 = wrist_hip_rel_p75 / body_height_proxy

    norm_wrist_chest_rel_min = wrist_chest_rel_min / body_height_proxy
    norm_wrist_chest_rel_med = wrist_chest_rel_med / body_height_proxy

    wrist_to_shoulder_med = _p(wrist_to_shoulder_dist, 50)
    wrist_to_shoulder_p75 = _p(wrist_to_shoulder_dist, 75)
    wrist_to_hip_med = _p(wrist_to_hip_dist, 50)

    norm_wrist_to_shoulder = wrist_to_shoulder_med / body_height_proxy
    norm_wrist_to_shoulder_p75 = wrist_to_shoulder_p75 / body_height_proxy
    norm_wrist_to_hip = wrist_to_hip_med / body_height_proxy

    wrist_closer_to_shoulders_than_hips = (
        wrist_to_shoulder_med < wrist_to_hip_med
    )

    wrist_vs_shoulder_ratio = (
        norm_wrist_span / norm_shoulder_span
        if norm_shoulder_span > 1e-4
        else 1.0
    )

    is_horizontal = shoulder_hip_dy_med < (0.35 * body_height_proxy)
    body_horizontal_like = (
        is_horizontal or
        shoulder_hip_dy_med <= 0.22 or
        torso_flatness_p75 <= 0.24
    )
    body_vertical_like = (
        not body_horizontal_like and
        shoulder_hip_dy_med >= 0.22
    )

    arms_dynamic = elbow_span >= 15
    legs_dynamic = knee_rom >= 20
    hips_dynamic = norm_hip_drop >= 0.05
    shoulders_dynamic = norm_shoulder_span >= 0.05

    # Bench Press:
    # - body is horizontal/semi-horizontal
    # - shoulders and hips are close in vertical coordinate
    # - wrists move while torso remains horizontal
    # Pull-up:
    # - wrists are almost fixed on the bar
    # - shoulders/head move vertically
    # - shoulder_y_span and nose_y_span are high
    # - wrist_y_span is not much higher than shoulder_y_span

    scores = {
        "Tractiuni": 0.0,
        "Genuflexiune": 0.0,
        "Fandare": 0.0,
        "Deadlift": 0.0,
        "Flotare": 0.0,
        "Bench Press": 0.0,
        "Biceps Curl": 0.0,
        "Mountain Climbers": 0.0,
        "Lateral Raises": 0.0,
        "Plank": 0.0,
        "Abdomene": 0.0,
    }

    # ── 1. Orientare corp ─────────────────────────────────────────────
    if is_horizontal:
        for ex in ("Flotare", "Bench Press", "Plank", "Abdomene"):
            scores[ex] += 3.0

        for ex in ("Tractiuni", "Genuflexiune", "Fandare", "Deadlift"):
            scores[ex] -= 5.0
    else:
        for ex in ("Tractiuni", "Genuflexiune", "Fandare", "Deadlift", "Biceps Curl", "Lateral Raises"):
            scores[ex] += 3.0

        scores["Flotare"] -= 5.0
        scores["Plank"] -= 5.0
        scores["Bench Press"] -= 1.0

    # ── 2. Tracțiuni ──────────────────────────────────────────────────
    pullup_bar_anchor_pattern = (
        wrist_up_med >= 0.75 and
        wrist_shoulder_rel_med < -0.05 and
        shoulders_dynamic and
        norm_shoulder_span >= 0.045 and
        wrist_vs_shoulder_ratio < 0.70
    )

    pullup_body_moves_pattern = (
        shoulders_dynamic and
        norm_shoulder_span >= 0.045
    )

    if pullup_bar_anchor_pattern:
        scores["Tractiuni"] += 10.0
    else:
        scores["Tractiuni"] -= 3.0

    if pullup_body_moves_pattern:
        scores["Tractiuni"] += 3.0

    if elbow_span >= 20 and wrist_up_med >= 0.60:
        scores["Tractiuni"] += 2.0

    if elbow_above_ratio >= 0.30 and wrist_up_med >= 0.70:
        scores["Tractiuni"] += 2.0

    if knee_rom >= 30:
        scores["Tractiuni"] -= 3.0

    if is_horizontal:
        scores["Tractiuni"] -= 7.0

    if norm_wrist_span >= 0.020 and norm_shoulder_span < 0.045:
        scores["Tractiuni"] -= 6.0

    pullup_fixed_bar_motion = (
        shoulder_y_span >= 0.07 and
        nose_y_span >= 0.06 and
        wrist_y_span <= shoulder_y_span * 1.25 and
        wrist_up_med >= 0.50
    )

    if pullup_fixed_bar_motion:
        scores["Tractiuni"] += 14.0

    pullup_like = (
        not is_horizontal and
        wrist_up_med >= 0.55 and
        elbow_span >= 15 and
        knee_rom < 45 and
        (
            pullup_bar_anchor_pattern or
            norm_shoulder_span >= 0.025 or
            norm_nose_span >= 0.025 or
            elbow_above_ratio >= 0.20
        )
    )

    # ── 3. ROM cot generic ────────────────────────────────────────────
    if elbow_span >= 40:
        for ex in ("Tractiuni", "Flotare", "Bench Press", "Biceps Curl", "Lateral Raises"):
            scores[ex] += 3.0
    elif elbow_span >= 20:
        for ex in ("Tractiuni", "Flotare", "Bench Press", "Biceps Curl", "Lateral Raises"):
            scores[ex] += 1.5

    # ── 4. ROM genunchi ───────────────────────────────────────────────
    if knee_rom >= 40:
        scores["Genuflexiune"] += 4.0
        scores["Deadlift"] += 0.5
        scores["Tractiuni"] -= 2.0
        scores["Bench Press"] -= 4.0
    elif knee_rom >= 20:
        scores["Genuflexiune"] += 2.0
        scores["Deadlift"] += 1.0
    else:
        scores["Tractiuni"] += 1.0
        scores["Plank"] += 1.0
        scores["Bench Press"] += 1.0

    # Pattern clar de Bench Press pe partea superioară.
    bench_like_upper_pattern = (
        wrist_up_med >= 0.70 and
        norm_wrist_chest_rel_min <= 0.14 and
        norm_wrist_hip_rel_p75 < 0.12
    )

    if bench_like_upper_pattern:
        scores["Genuflexiune"] -= 10.0
        scores["Deadlift"] -= 6.0
        scores["Fandare"] = min(scores["Fandare"], -999.0)

    if norm_wrist_span >= 0.018 and knee_rom < 25:
        scores["Genuflexiune"] -= 5.0

    upper_body_standing = (not is_horizontal) and knee_rom < 25 and not hips_dynamic
    upper_body_upright = (not is_horizontal) and knee_rom < 35

    if upper_body_standing and elbow_span >= 35 and wrist_up_med < 0.45:
        scores["Biceps Curl"] += 12.0
        scores["Lateral Raises"] -= 2.0

    biceps_curl_candidate = (
        upper_body_standing and
        elbow_span >= 35 and
        elbow_p10 <= 105 and
        elbow_p90 >= 125 and
        elbow_shoulder_rel_med > 0.04 and
        elbow_above_ratio < 0.25 and
        wrist_shoulder_rel_med > -0.10 and
        norm_wrist_span >= 0.020 and
        norm_shoulder_span < 0.080
    )

    biceps_curl_restore_pattern = (
        not is_horizontal and
        knee_rom < 35 and
        elbow_span >= 30 and
        elbow_p10 <= 115 and
        elbow_p90 >= 125 and
        elbow_shoulder_rel_p10 > -0.04 and
        elbow_above_ratio < 0.25 and
        norm_elbow_span < 0.055 and
        wrist_up_med < 0.65
    )

    if biceps_curl_candidate or biceps_curl_restore_pattern:
        scores["Biceps Curl"] += 18.0
        scores["Lateral Raises"] -= 3.0

    if upper_body_standing and elbow_span < 45 and norm_wrist_span >= 0.035 and wrist_up_med < 0.65:
        scores["Lateral Raises"] += 8.0

    if upper_body_standing and elbow_span >= 20 and abs(_p(wrist_shoulder_rel_y, 50)) <= 0.18:
        scores["Lateral Raises"] += 5.0

    lateral_raise_elbows_to_shoulder = (
        elbow_shoulder_rel_p10 <= 0.20 and
        elbow_shoulder_rel_p90 >= 0.12 and
        norm_elbow_span >= 0.018
    )

    lateral_raise_elbows_near_shoulders = (
        upper_body_upright and
        elbow_shoulder_rel_p10 <= 0.22 and
        norm_elbow_span >= 0.012 and
        norm_wrist_span >= 0.025 and
        elbow_p10 >= 90 and
        wrist_up_med < 0.75
    )

    lateral_raise_candidate = (
        upper_body_standing and
        norm_wrist_span >= 0.035 and
        elbow_p10 >= 105 and
        elbow_p90 >= 130 and
        lateral_raise_elbows_to_shoulder and
        wrist_shoulder_rel_p10 <= 0.14 and
        wrist_shoulder_rel_p90 >= 0.16 and
        norm_wrist_to_shoulder_p75 >= 0.24 and
        wrist_up_med < 0.65
    )

    lateral_raise_elbow_pattern = (
        upper_body_upright and
        (lateral_raise_elbows_to_shoulder or lateral_raise_elbows_near_shoulders) and
        elbow_p10 >= 100 and
        norm_wrist_span >= 0.030 and
        wrist_up_med < 0.70
    )

    if lateral_raise_candidate:
        scores["Lateral Raises"] += 18.0

    if lateral_raise_elbow_pattern:
        scores["Lateral Raises"] += 8.0

    if lateral_raise_elbows_near_shoulders:
        scores["Lateral Raises"] += 12.0

    if knee_rom >= 30 or is_horizontal:
        scores["Biceps Curl"] -= 6.0
        scores["Lateral Raises"] -= 6.0

    # ── 5. Mișcare șold ───────────────────────────────────────────────
    if hips_dynamic:
        if is_horizontal:
            scores["Flotare"] += 2.0
        else:
            scores["Genuflexiune"] += 2.0
            scores["Deadlift"] += 1.5

    # ── 6. Mișcare umeri ──────────────────────────────────────────────
    if shoulders_dynamic:
        if is_horizontal:
            scores["Flotare"] += 2.0
            scores["Abdomene"] += 1.0
        else:
            scores["Tractiuni"] += 1.0
            scores["Abdomene"] += 1.0

    # ── 7. Deadlift ───────────────────────────────────────────────────
    deadlift_hinge = (
        trunk_span >= 15 or
        hip_shoulder_rel_span >= 0.045
    )

    deadlift_hips_active = (
        norm_hip_drop >= 0.025 or
        hip_shoulder_rel_span >= 0.040
    )

    deadlift_knees_moderate = (
        10 <= knee_rom <= 60
    )

    deadlift_hands_below_hip = (
        norm_wrist_hip_rel_med >= 0.020 or
        norm_wrist_hip_rel_p75 >= 0.040
    )

    deadlift_hands_low = (
        wrist_up_med < 0.50 and
        wrist_shoulder_rel_med > -0.05 and
        deadlift_hands_below_hip
    )

    deadlift_not_lunge_shape = (
        knee_asym_p90 < 35 or
        (knee_dx_p90 < 0.085 and knee_y_p90 < 0.045)
    )

    deadlift_candidate = (
        deadlift_hinge and
        deadlift_hips_active and
        deadlift_knees_moderate and
        deadlift_hands_low
    )

    if deadlift_candidate:
        scores["Deadlift"] += 12.0

    if deadlift_hinge:
        scores["Deadlift"] += 3.0

    if deadlift_hips_active:
        scores["Deadlift"] += 2.0

    if deadlift_knees_moderate:
        scores["Deadlift"] += 2.0

    if deadlift_hands_below_hip:
        scores["Deadlift"] += 3.0

    if deadlift_not_lunge_shape:
        scores["Deadlift"] += 2.0

    if not deadlift_hands_below_hip:
        scores["Deadlift"] -= 6.0

    if knee_rom >= 70:
        scores["Deadlift"] -= 3.0

    if wrist_up_med >= 0.60:
        scores["Deadlift"] -= 5.0

    if knee_asym_p90 >= 35 and ankle_distance_med >= 0.22 and (
        knee_dx_p90 >= 0.085 or knee_y_p90 >= 0.045
    ):
        scores["Deadlift"] -= 4.0

    plank_hip_dev_for_pushup = _p(plank_hip_deviation_values, 50) / body_height_proxy

    pushup_body_aligned = (
        140 <= align_med <= 220 and
        plank_hip_dev_for_pushup < 0.22 and
        trunk_span < 25
    )

    # Parametru specific pentru flotare:
    # palmele sunt sprijinite pe sol, deci se mișcă puțin vertical.
    pushup_hands_anchored = (
        wrist_up_med < 0.45 and
        (
            norm_wrist_span <= 0.075 or
            wrist_y_span <= shoulder_y_span * 0.75
        )
    )

    pushup_strong_pattern = (
        is_horizontal and
        elbow_span >= 10 and
        knee_rom < 45 and
        pushup_body_aligned and
        pushup_hands_anchored and
        not bench_like_upper_pattern
    )

    pushup_like = (
        is_horizontal and
        elbow_span >= 8 and
        knee_rom < 55 and
        pushup_body_aligned and
        wrist_up_med < 0.55 and
        norm_wrist_to_shoulder <= max(0.55, norm_wrist_to_hip * 1.20)
    )

    pushup_floor_motion_pattern = (
        is_horizontal
        and elbow_span >= 30
        and knee_rom < 60
        and align_med >= 145
        and plank_hip_dev_for_pushup < 0.14
        and wrist_up_med < 0.20
        and wrist_shoulder_rel_med > 0.12
        and norm_wrist_span <= 0.16
        and norm_shoulder_span >= 0.12
    )

    deadlift_strong_hinge_pattern = (
        deadlift_hands_below_hip and
        wrist_up_med < 0.55 and
        (
            trunk_span >= 18 or
            hip_shoulder_rel_span >= 0.050 or
            deadlift_hips_active
        )
    )

    # Flotare:
    # corp orizontal + brațe active + corp aliniat + palme aproape fixe pe sol.
    pushup_candidate = pushup_strong_pattern or pushup_like or pushup_floor_motion_pattern

    # Deadlift:
    # palmele sub șold + hinge/șold activ,
    # dar NU dacă există pattern puternic de flotare.
    deadlift_upper_pattern = (
        deadlift_strong_hinge_pattern and
        not pushup_candidate and
        not is_horizontal
    )

    if deadlift_upper_pattern:
        scores["Deadlift"] += 8.0
        scores["Flotare"] -= 12.0
        scores["Bench Press"] -= 6.0

    if is_horizontal:
        scores["Deadlift"] -= 30.0

    # Abdomene: trunk_span mare contează doar dacă NU există pattern de deadlift.
    if trunk_span >= 30 and is_horizontal and not deadlift_upper_pattern:
        scores["Abdomene"] += 3.0
    elif trunk_span >= 15 and is_horizontal and not deadlift_upper_pattern:
        scores["Abdomene"] += 1.5

    # ── 8. Fandare ────────────────────────────────────────────────────
    lunge_leg_pattern = (
        front_knee_min <= 140 and
        back_knee_max >= 135 and
        knee_asym_p90 >= 18
    )

    lunge_stance = (
        ankle_distance_med >= 0.16
    )

    lunge_knee_shape = (
        knee_dx_p90 >= 0.055 or
        knee_y_p90 >= 0.025
    )

    lunge_depth = (
        knee_rom >= 18 and
        norm_hip_drop >= 0.020
    )

    lunge_not_horizontal = (
        not is_horizontal
    )

    deadlift_like_for_lunge_block = (
        deadlift_hinge and
        deadlift_hips_active and
        deadlift_hands_low and
        knee_asym_p90 < 35
    )

    bench_like_for_lunge_block = (
        arms_dynamic and
        norm_wrist_span >= 0.018 and
        norm_shoulder_span < 0.060 and
        norm_hip_drop < 0.080 and
        knee_rom < 40
    )

    lunge_candidate = (
        lunge_not_horizontal and
        not deadlift_like_for_lunge_block and
        not bench_like_for_lunge_block and
        not bench_like_upper_pattern and
        not deadlift_upper_pattern and
        (
            (lunge_leg_pattern and lunge_stance and lunge_depth) or
            (lunge_leg_pattern and lunge_knee_shape and lunge_depth) or
            (lunge_stance and lunge_knee_shape and knee_asym_p90 >= 20)
        )
    )

    if bench_like_upper_pattern or deadlift_upper_pattern:
        scores["Fandare"] = -999.0
    else:
        scores["Fandare"] = 0.0

    if lunge_candidate:
        scores["Fandare"] += 12.0
        scores["Genuflexiune"] -= 6.0
        scores["Deadlift"] -= 3.0

        if knee_asym_p90 >= 30:
            scores["Fandare"] += 3.0

        if ankle_distance_med >= 0.22:
            scores["Fandare"] += 2.0

        if front_knee_min <= 125:
            scores["Fandare"] += 2.0

        if back_knee_max >= 145:
            scores["Fandare"] += 2.0
    else:
        if bench_like_upper_pattern or deadlift_upper_pattern:
            scores["Fandare"] = -999.0
        else:
            scores["Fandare"] = min(scores["Fandare"], 0.0)

    if knee_asym_p90 < 16:
        scores["Genuflexiune"] += 2.0

    # ── 9. Stance ─────────────────────────────────────────────────────
    if ankle_distance_med >= 0.25:
        scores["Genuflexiune"] += 1.0

    # ── 10. Plank ─────────────────────────────────────────────────────
    if not arms_dynamic and not legs_dynamic and not hips_dynamic:
        scores["Plank"] += 4.0

    if align_med >= 155 and is_horizontal:
        scores["Plank"] += 4.0

    plank_hip_dev = _p(plank_hip_deviation_values, 50) / body_height_proxy
    plank_hip_dev_p90 = _p(plank_hip_deviation_values, 90) / body_height_proxy

    plank_candidate = (
        is_horizontal and
        not arms_dynamic and
        not legs_dynamic and
        not hips_dynamic and
        align_med >= 150 and
        plank_hip_dev < 0.12
    )
    plank_like = plank_candidate

    if plank_hip_dev < 0.08 and is_horizontal:
        scores["Plank"] += 2.0

    # ── 11. Bench Press ───────────────────────────────────────────────
    bench_body_horizontal = (
        is_horizontal or
        shoulder_hip_dy_med < (0.45 * body_height_proxy)
    )

    bench_upper_body_static = (
        norm_shoulder_span < 0.070 and
        _span(nose_y) / body_height_proxy < 0.080
    )

    bench_lower_body_static = (
        norm_hip_drop < 0.080 and
        knee_rom < 45
    )

    bench_arms_pressing = (
        elbow_span >= 8 or
        wrist_y_span >= 0.006 or
        norm_wrist_span >= 0.015
    )

    bench_hands_to_chest = (
        norm_wrist_chest_rel_min <= 0.120
    )

    bench_hands_not_below_hip = (
        norm_wrist_hip_rel_p75 < 0.080
    )

    bench_not_pullup_pattern = not pullup_bar_anchor_pattern

    bench_not_leg_exercise = (
        knee_rom < 45 and
        norm_hip_drop < 0.090
    )

    bench_candidate = (
        bench_arms_pressing and
        bench_hands_to_chest and
        bench_hands_not_below_hip and
        bench_not_pullup_pattern and
        bench_not_leg_exercise and
        (
            bench_body_horizontal or
            wrist_up_med >= 0.70
        )
    )

    if bench_candidate:
        scores["Bench Press"] += 14.0

    if bench_like_upper_pattern:
        scores["Bench Press"] += 8.0

    if bench_body_horizontal:
        scores["Bench Press"] += 4.0

    if bench_upper_body_static:
        scores["Bench Press"] += 3.0

    if bench_lower_body_static:
        scores["Bench Press"] += 3.0

    if bench_arms_pressing:
        scores["Bench Press"] += 4.0

    if bench_hands_to_chest:
        scores["Bench Press"] += 5.0

    if bench_hands_not_below_hip:
        scores["Bench Press"] += 3.0

    if bench_not_pullup_pattern:
        scores["Bench Press"] += 2.0

    if bench_not_leg_exercise:
        scores["Bench Press"] += 2.0

    if pullup_bar_anchor_pattern:
        scores["Bench Press"] -= 10.0

    if deadlift_hands_below_hip:
        scores["Bench Press"] -= 8.0

    if not bench_hands_to_chest:
        scores["Bench Press"] -= 4.0

    if not bench_hands_not_below_hip:
        scores["Bench Press"] -= 6.0

    if knee_rom >= 55:
        scores["Bench Press"] -= 5.0

    if norm_hip_drop >= 0.110:
        scores["Bench Press"] -= 4.0

    if not bench_arms_pressing:
        scores["Bench Press"] -= 4.0

    if deadlift_candidate:
        scores["Bench Press"] -= 8.0

    if lunge_candidate:
        scores["Bench Press"] -= 6.0

    # Bench Press vs Flotare.
    if is_horizontal and bench_arms_pressing:
        if deadlift_upper_pattern:
            scores["Flotare"] -= 10.0
        elif hips_dynamic or shoulders_dynamic:
            scores["Flotare"] += 3.0
            scores["Bench Press"] -= 2.0
        else:
            scores["Bench Press"] += 3.0
            scores["Flotare"] -= 1.0

    # ── 12. Abdomene ──────────────────────────────────────────────────
    # Mountain Climbers: plank-like support, stable hands/shoulders,
    # low elbow ROM, and pronounced alternating knee/ankle motion.
    mountain_climber_like = (
        body_horizontal_like
        and not body_vertical_like
        and elbow_span <= 28
        and knee_rom >= 35
        and knee_motion_span >= 0.05
        and ankle_motion_span >= 0.04
        and hip_drop <= 0.16
        and (
            wrist_y_span <= 0.08
            or (
                elbow_span <= 10
                and knee_motion_span >= 0.12
                and ankle_motion_span >= 0.08
                and wrist_y_span <= 0.28
            )
        )
        and not plank_like
        and not pushup_like
    )

    mountain_climber_score = 0.0
    if body_horizontal_like:
        mountain_climber_score += 5.0
    if knee_motion_span >= 0.05:
        mountain_climber_score += 4.0
    if ankle_motion_span >= 0.04:
        mountain_climber_score += 4.0
    if knee_rom >= 35:
        mountain_climber_score += 3.0
    if elbow_span <= 28:
        mountain_climber_score += 3.0
    if hip_drop <= 0.16:
        mountain_climber_score += 2.0
    if wrist_y_span <= 0.08:
        mountain_climber_score += 2.0
    if body_vertical_like:
        mountain_climber_score -= 10.0
    if elbow_span >= 35:
        mountain_climber_score -= 8.0
    if knee_motion_span < 0.035:
        mountain_climber_score -= 8.0
    if hip_drop >= 0.22:
        mountain_climber_score -= 8.0
    if wrist_y_span >= 0.12:
        mountain_climber_score -= 6.0
    if mountain_climber_like:
        scores["Mountain Climbers"] = mountain_climber_score
    else:
        scores["Mountain Climbers"] = min(mountain_climber_score, 8.0)

    ab_shoulder_toward_hip = _span(
        [sh - h for sh, h in zip(shoulder_mid_y, hip_y)]
    )

    if ab_shoulder_toward_hip >= 0.08 and not deadlift_upper_pattern:
        scores["Abdomene"] += 3.0

    # Protecții finale.
    if pushup_candidate:
        scores["Flotare"] += 35.0
        scores["Deadlift"] -= 40.0
        scores["Genuflexiune"] -= 8.0
        scores["Fandare"] = min(scores["Fandare"], -999.0)
        scores["Abdomene"] -= 8.0

    if deadlift_upper_pattern:
        scores["Deadlift"] += 22.0
        scores["Flotare"] -= 18.0
        scores["Abdomene"] -= 12.0
        scores["Fandare"] = min(scores["Fandare"], -999.0)

    if lunge_candidate:
        scores["Genuflexiune"] -= 8.0

    situp_like = (
        trunk_span >= 30
        and knee_med <= 115
        and knee_min <= 85
        and (
            norm_shoulder_span >= 0.12
            or norm_nose_span >= 0.12
        )
        and not plank_like
    )

    front_view_standing_static = (
        knee_med >= 145
        and knee_rom <= 18
        and norm_hip_drop <= 0.04
        and norm_shoulder_span <= 0.08
        and norm_nose_span <= 0.06
        and align_med >= 150
    )

    front_view_lateral_raise = (
        front_view_standing_static
        and elbow_span >= 25
        and norm_wrist_span >= 0.25
        and norm_elbow_span >= 0.08
        and wrist_shoulder_rel_p10 <= 0.03
        and wrist_shoulder_rel_p90 >= 0.16
        and elbow_shoulder_rel_p90 >= 0.10
        and wrist_up_med < 0.50
    )

    front_view_biceps_curl = (
        front_view_standing_static
        and elbow_span >= 30
        and norm_wrist_span >= 0.08
        and norm_wrist_span <= 0.25
        and norm_elbow_span <= 0.07
        and wrist_shoulder_rel_p10 >= 0.04
        and wrist_shoulder_rel_p90 <= 0.25
        and elbow_shoulder_rel_med >= 0.05
        and wrist_up_med < 0.50
    )

    forearm_plank_like = (
        is_horizontal
        and align_med >= 145
        and trunk_span <= 12
        and elbow_span <= 50
        and knee_rom <= 50
        and plank_hip_dev < 0.10
        and norm_hip_drop <= 0.16
        and norm_shoulder_span <= 0.18
        and norm_nose_span <= 0.25
        and wrist_up_med < 0.30
        and wrist_shoulder_rel_med >= 0.18
        and not situp_like
        and not mountain_climber_like
    )

    # ==========================================================
    # DECIZIE FINALĂ ROBUSTĂ
    # ==========================================================
    # Observație importantă:
    # - Biceps Curl trebuie verificat înainte de Bench Press.
    # - Bench Press trebuie acceptat doar când corpul este clar orizontal.
    # - Deadlift nu trebuie să câștige la egalitate sau aproape egalitate cu Genuflexiune.

    # 1. Exerciții distinctive care trebuie alese inainte de reguli generice.
    if situp_like:
        return "Abdomene"

    if front_view_biceps_curl:
        return "Biceps Curl"

    if front_view_lateral_raise:
        return "Lateral Raise"

    if forearm_plank_like and source_is_portrait and crop_top_ratio <= 0:
        cropped_exercise = detect_exercise(
            video_path,
            sample_every_n_frames=sample_every_n_frames,
            max_samples=max_samples,
            max_frame_width=max_frame_width,
            trim_intro_outro=trim_intro_outro,
            crop_top_ratio=0.22,
        )
        if cropped_exercise != "Necunoscut":
            return cropped_exercise

    if (plank_like and knee_motion_span < 0.035) or forearm_plank_like:
        return "Plank"

    if (pushup_like or pushup_candidate) and source_is_portrait and crop_top_ratio <= 0:
        cropped_exercise = detect_exercise(
            video_path,
            sample_every_n_frames=sample_every_n_frames,
            max_samples=max_samples,
            max_frame_width=max_frame_width,
            trim_intro_outro=trim_intro_outro,
            crop_top_ratio=0.22,
        )
        if cropped_exercise in ("Bench Press", "Tractiuni"):
            return cropped_exercise

    if pushup_like and elbow_span >= 28:
        return "Flotare"

    if mountain_climber_like and mountain_climber_score >= 13:
        return "Mountain Climbers"

    if pushup_candidate:
        return "Flotare"

    # 2. Tracțiuni înainte de exercițiile de brațe/bench.
    # Dacă mâinile sunt sus ca pe bară și corpul se mișcă vertical, nu vrem să alegem bench/curl.
    if pullup_bar_anchor_pattern or pullup_fixed_bar_motion:
        return "Tractiuni"

    # 3. Biceps Curl înainte de Bench Press.
    # Curl = postură verticală, genunchi relativ statici, coate jos, mișcare mare la cot.
    biceps_strong_override = (
        (biceps_curl_candidate or biceps_curl_restore_pattern)
        and not is_horizontal
        and not body_horizontal_like
        and not pullup_like
        and not pullup_bar_anchor_pattern
        and knee_rom < 35
        and elbow_span >= 30
        and elbow_above_ratio < 0.30
        and wrist_up_med < 0.70
    )

    if biceps_strong_override:
        return "Biceps Curl"

    # Penalizare suplimentară: dacă arată ca biceps curl și persoana nu este culcată,
    # Bench Press nu trebuie să câștige prin faptul că mâinile ajung aproape de piept.
    if (biceps_curl_candidate or biceps_curl_restore_pattern) and not is_horizontal:
        scores["Bench Press"] -= 20.0

    # 4. Lateral Raise înainte de Bench Press, dar numai pentru postură verticală.
    if (
        lateral_raise_candidate or
        lateral_raise_elbow_pattern or
        lateral_raise_elbows_near_shoulders
    ) and not is_horizontal and not pullup_bar_anchor_pattern:
        return "Lateral Raise"

    # 5. Bench Press doar când corpul este clar orizontal.
    # Aceasta este modificarea care blochează cazul Biceps Curl -> Bench Press.
    bench_strong_override = (
        bench_candidate
        and not pullup_like
        and is_horizontal
        and elbow_span >= 8
        and wrist_y_span >= 0.006
        and not plank_like
        and not biceps_strong_override
    )

    if bench_strong_override:
        return "Bench Press"

    portrait_crop_bench_override = (
        crop_top_ratio > 0
        and bench_like_upper_pattern
        and is_horizontal
        and elbow_span >= 20
        and wrist_up_med >= 0.60
        and bench_hands_not_below_hip
        and norm_wrist_to_shoulder <= 0.35
    )

    if portrait_crop_bench_override:
        return "Bench Press"

    if lunge_candidate:
        return "Fandare"

    # ==========================================================
    # GENOFLEXIUNE VS DEADLIFT
    # ==========================================================
    # Fix v3:
    # În patch-ul anterior, squat_strong_override era prea agresiv și returna
    # Genuflexiune înainte ca un deadlift clar să fie verificat.
    # Acum separăm explicit:
    # - Deadlift = hinge din șold/trunchi + mâini jos, sub/în jurul șoldului.
    # - Genuflexiune = mișcare dominantă din genunchi + șold care coboară,
    #   dar fără pattern clar de deadlift.

    clear_deadlift_pattern = (
        not is_horizontal
        and not body_horizontal_like
        and not plank_like
        and not pushup_candidate
        and deadlift_hands_below_hip
        and wrist_up_med <= 0.50
        and knee_rom <= 70
        and knee_min >= 75
        and knee_asym_p90 <= 32
        and (
            deadlift_candidate
            or deadlift_upper_pattern
            or deadlift_strong_hinge_pattern
            or trunk_span >= 12
            or hip_shoulder_rel_span >= 0.045
        )
    )

    deadlift_hard_override = (
        clear_deadlift_pattern
        and knee_rom <= 65
        and knee_min >= 85
        and (
            deadlift_candidate
            or deadlift_upper_pattern
            or deadlift_strong_hinge_pattern
            or trunk_p75 >= 14
            or trunk_span >= 15
        )
    )

    if deadlift_hard_override:
        return "Deadlift"

    # Squat puternic doar când flexia genunchilor este dominantă.
    # IMPORTANT: dacă există pattern clar de deadlift, nu lăsăm squat-ul să câștige
    # doar pentru că genunchii se îndoaie moderat.
    squat_strong_override = (
        knee_rom >= 40
        and knee_min <= 110
        and norm_hip_drop >= 0.030
        and not is_horizontal
        and not body_horizontal_like
        and not plank_like
        and not clear_deadlift_pattern
    )

    if squat_strong_override:
        return "Genuflexiune"

    is_deadlift_strong = (
        clear_deadlift_pattern
        and trunk_p75 >= 12
        and trunk_span >= 5
        and 95 <= knee_med <= 170
        and knee_min >= 80
        and knee_rom <= 70
        and knee_asym_p90 <= 28
        and ankle_distance_med <= 0.40
        and wrist_up_med <= 0.50
        and not body_horizontal_like
        and not plank_like
        and not pushup_like
    )

    deadlift_score = 0.0
    if trunk_p75 >= 12:
        deadlift_score += 4.0
    if trunk_span >= 5:
        deadlift_score += 3.0
    if 95 <= knee_med <= 170:
        deadlift_score += 3.0
    if knee_asym_p90 <= 28:
        deadlift_score += 2.0
    if ankle_distance_med <= 0.40:
        deadlift_score += 2.0
    if wrist_up_med <= 0.50:
        deadlift_score += 2.0
    if hip_drop >= 0.020:
        deadlift_score += 1.0
    if deadlift_hands_below_hip:
        deadlift_score += 4.0
    if clear_deadlift_pattern:
        deadlift_score += 8.0

    # Penalizări clare pentru cazurile care seamănă mai mult cu squat/flotare.
    if body_horizontal_like:
        deadlift_score -= 8.0
    if wrist_up_med >= 0.65:
        deadlift_score -= 5.0
    if knee_min < 75:
        deadlift_score -= 5.0
    if knee_rom > 75:
        deadlift_score -= 5.0
    if knee_asym_p90 >= 35:
        deadlift_score -= 4.0
    if not deadlift_hands_below_hip:
        deadlift_score -= 7.0
    if squat_strong_override:
        deadlift_score -= 8.0

    scores["Deadlift"] += deadlift_score

    if is_deadlift_strong:
        return "Deadlift"

    squat_score = scores["Genuflexiune"]

    # Dacă pattern-ul de deadlift este clar, deadlift nu trebuie să piardă doar
    # fiindcă scorul generic de squat a primit puncte pentru knee_rom/hip_drop.
    if clear_deadlift_pattern and deadlift_score >= squat_score - 2.0:
        return "Deadlift"

    # Dacă pattern-ul NU este clar deadlift, rămânem conservatori:
    # squat câștigă la scor apropiat, iar deadlift trebuie să fie evident mai bun.
    if max(deadlift_score, squat_score) >= 4.5:
        if squat_score >= deadlift_score - 0.5:
            return "Genuflexiune"
        if deadlift_score >= squat_score + 2.0:
            return "Deadlift"
  
    # print("\n================ DETECTION DEBUG ================")
    # print("scores:", scores)
    # print("is_horizontal:", is_horizontal)
    # print("knee_rom:", knee_rom)
    # print("knee_asym_p90:", knee_asym_p90)
    # print("front_knee_min:", front_knee_min)
    # print("back_knee_max:", back_knee_max)
    # print("norm_hip_drop:", norm_hip_drop)
    # print("norm_shoulder_span:", norm_shoulder_span)
    # print("norm_wrist_span:", norm_wrist_span)
    # print("wrist_up_med:", wrist_up_med)
    # print("wrist_shoulder_rel_med:", wrist_shoulder_rel_med)
    # print("norm_wrist_hip_rel_p75:", norm_wrist_hip_rel_p75)
    # print("norm_wrist_chest_rel_min:", norm_wrist_chest_rel_min)
    # print("wrist_closer_to_shoulders_than_hips:", wrist_closer_to_shoulders_than_hips)
    # print("norm_wrist_to_shoulder:", norm_wrist_to_shoulder)
    # print("norm_wrist_to_hip:", norm_wrist_to_hip)
    # print("deadlift_hands_below_hip:", deadlift_hands_below_hip)
    # print("deadlift_upper_pattern:", deadlift_upper_pattern)
    # print("deadlift_candidate:", deadlift_candidate)
    # print("pushup_candidate:", pushup_candidate)
    # print("pushup_body_aligned:", pushup_body_aligned)
    # print("pushup_hands_anchored:", pushup_hands_anchored)
    # print("pushup_strong_pattern:", pushup_strong_pattern)
    # print("deadlift_strong_hinge_pattern:", deadlift_strong_hinge_pattern)
    # print("bench_like_upper_pattern:", bench_like_upper_pattern)
    # print("bench_hands_to_chest:", bench_hands_to_chest)
    # print("bench_hands_not_below_hip:", bench_hands_not_below_hip)
    # print("bench_candidate:", bench_candidate)
    # print("lunge_candidate:", lunge_candidate)
    # print("=================================================\n")


    priority = [
        "Plank",
        "Flotare",
        "Mountain Climbers",
        "Tractiuni",
        "Biceps Curl",
        "Lateral Raises",
        "Bench Press",
        "Abdomene",
        "Fandare",
        "Genuflexiune",
        "Deadlift",
    ]
    best_exercise = max(priority, key=lambda k: scores.get(k, -999.0))
    best_score = scores[best_exercise]

    sorted_scores = sorted([scores.get(k, -999.0) for k in priority], reverse=True)
    margin = sorted_scores[0] - sorted_scores[1] if len(sorted_scores) > 1 else 0.0

    if best_score < 4.5 or margin < 1.5:
        if crop_top_ratio <= 0 and source_is_portrait:
            return detect_exercise(
                video_path,
                sample_every_n_frames=sample_every_n_frames,
                max_samples=max_samples,
                max_frame_width=max_frame_width,
                trim_intro_outro=trim_intro_outro,
                crop_top_ratio=0.22,
            )
        return "Necunoscut"

    if best_exercise == "Lateral Raises":
        return "Lateral Raise"

    return best_exercise
