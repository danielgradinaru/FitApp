print("MAIN.PY RULEAZA")

import shutil, os, json, cv2, sqlite3, base64, requests, tempfile, uuid
from dotenv import load_dotenv
from datetime import datetime, timedelta, date
from collections import deque, Counter
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, File, UploadFile, Form, Depends, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from exercise_detection import detect_exercise
import numpy as np
from pydantic import BaseModel
from feedback_rules import (
    pushup_rep_state,
    squat_rep_state,
    deadlift_rep_state,
    lunge_rep_state,
    bench_press_rep_state,
    biceps_curl_rep_state,
    mountain_climber_rep_state,
    lateral_raise_rep_state,
    plank_state,
    calculate_angle,
)

load_dotenv()

# Importam logica existenta
from pose_estimation import PoseDetector
from exercise_evaluation import (
    evaluate_pushup_form,
    evaluate_form,
    evaluate_deadlift_form,
    evalueaza_forma_fandare,
    evaluate_pullup_form,
    evaluate_situp_form,
    evaluate_plank_form,
    evaluate_bench_press_form,
    evaluate_biceps_curl_form,
    evaluate_mountain_climber_form,
    evaluate_lateral_raise_form,
    draw_colored_landmarks
)

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_PUBLISHABLE_KEY = os.getenv("SUPABASE_PUBLISHABLE_KEY", "")

print("SUPABASE_URL:", SUPABASE_URL)
print("SUPABASE_PUBLISHABLE_KEY exists:", bool(SUPABASE_PUBLISHABLE_KEY))

DB_PATH = "fitapp.db"
PROCESSED_DIR = "static/processed"
MAX_UPLOAD_FRAME_SIDE = 480
ANALYSIS_SCREENSHOT_OVERLAY = False
SAVE_PROCESSED_VIDEO = False
DEBUG_ANALYSIS = False
DEBUG_MOUNTAIN = False
MOUNTAIN_MIN_PEAK_DISTANCE = 3

app = FastAPI(title="FitApp API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
os.makedirs("static", exist_ok=True)
if SAVE_PROCESSED_VIDEO:
    os.makedirs(PROCESSED_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

analysis_jobs = {}


def normalize_exercise_name(exercise):
    value = (exercise or "").strip()
    aliases = {
        "lateral raises": "Lateral Raise",
        "lateral raise": "Lateral Raise",
        "biceps curl": "Biceps Curl",
        "mountain climbers": "Mountain Climbers",
        "mountain climber": "Mountain Climbers",
        "bench press": "Bench Press",
    }
    return aliases.get(value.lower(), value)


def _scaled_video_size(width, height, max_side=MAX_UPLOAD_FRAME_SIDE):
    if width <= 0 or height <= 0:
        return int(width), int(height)

    longest_side = max(width, height)
    if longest_side <= max_side:
        scaled_width, scaled_height = int(width), int(height)
    else:
        scale = max_side / float(longest_side)
        scaled_width = int(width * scale)
        scaled_height = int(height * scale)

    # Codecurile video se impaca mai bine cu dimensiuni pare.
    scaled_width = max(2, scaled_width - (scaled_width % 2))
    scaled_height = max(2, scaled_height - (scaled_height % 2))
    return scaled_width, scaled_height


def _resize_frame_for_processing(frame, target_size):
    target_width, target_height = target_size
    if frame.shape[1] == target_width and frame.shape[0] == target_height:
        return frame
    return cv2.resize(frame, target_size, interpolation=cv2.INTER_AREA)


def _plank_position_message(hip_position):
    if hip_position == "low":
        return "Bazinul a coborat sub linia corpului."
    if hip_position == "high":
        return "Bazinul a urcat peste linia corpului."
    return "Pozitia de plank este stabila."


def _plank_snapshot_reason(metrics, score, previous_metrics, previous_score):
    hip_position = metrics.get("hip_position", "neutral")
    if previous_metrics is None:
        return "Cadru initial pentru analiza plank."

    previous_position = previous_metrics.get("hip_position", "neutral")
    if hip_position in ["low", "high"] and hip_position != previous_position:
        return _plank_position_message(hip_position)

    hip_deviation = float(metrics.get("hip_deviation", 0.0) or 0.0)
    previous_deviation = float(previous_metrics.get("hip_deviation", 0.0) or 0.0)
    if abs(hip_deviation - previous_deviation) >= 0.04:
        return "Pozitia bazinului s-a schimbat vizibil."

    if previous_score is not None and score <= previous_score - 12:
        return "Forma s-a degradat fata de cadrul anterior."

    if score < 70 and hip_position in ["low", "high"]:
        return _plank_position_message(hip_position)

    return None

# --- DATABASE SETUP ---
def get_db_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False) # Fix pentru threading
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE,
        password_hash TEXT,
        full_name TEXT,
        xp INTEGER DEFAULT 0,
        level INTEGER DEFAULT 1,
        current_streak INTEGER DEFAULT 0,
        last_workout_date TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS workouts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        exercise TEXT,
        avg_score REAL,
        video_path TEXT, processed_video_path TEXT,
        feedback_json TEXT, reps_json TEXT, created_at TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS user_badges (
        user_id INTEGER,
        badge_id TEXT,
        earned_at TEXT,
        PRIMARY KEY (user_id, badge_id)
    )""")
    conn.commit()
    conn.close()

init_db()

# --- GAMIFICATION LOGIC (MODIFICATĂ SA PRIMEASCĂ CONEXIUNEA) ---
def get_rank_name(level):
    if level < 10: return "Novice"
    if level < 20: return "Bronze Athlete"
    if level < 30: return "Silver Lifter"
    if level < 40: return "Gold Master"
    if level < 50: return "Platinum Legend"
    if level < 60: return "Diamond Cyborg"
    return "God Tier"

def xp_for_next_level(current_level):
    return int(250 * current_level * 1.2)

# FIX: Acum primeste `conn` ca argument, nu deschide altul nou
def check_badges(conn, user_id, current_data):
    new_badges = []
    
    badges_def = {
        "b_first": "Începutul (Primul antrenament)",
        "b_perf": "Perfecționist (Scor > 90%)",
        "b_streak3": "Constanță (Streak 3 zile)",
        "b_streak7": "Dedicație (Streak 7 zile)",
        "b_streak30": "Discipol (Streak 30 zile)",
        "b_rep_master": "Rep Master (20+ repetări)",
        "b_sniper": "Sniper (Toate rep-urile > 80%)",
        "b_night": "Night Owl (Antrenament noaptea)",
        "b_morning": "Early Bird (Antrenament dimineața)",
        "b_lvl10": "Veteran (Level 10)"
    }

    def award(bid):
        exists = conn.execute("SELECT 1 FROM user_badges WHERE user_id=? AND badge_id=?", (user_id, bid)).fetchone()
        if not exists:
            conn.execute("INSERT INTO user_badges (user_id, badge_id, earned_at) VALUES (?, ?, ?)", 
                         (user_id, bid, datetime.now().isoformat()))
            new_badges.append(badges_def[bid])

    # Verificari
    count = conn.execute("SELECT COUNT(*) as c FROM workouts WHERE user_id=?", (user_id,)).fetchone()['c']
    user = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    
    if count >= 1: award("b_first")
    if current_data['score'] >= 90: award("b_perf")
    if user['current_streak'] >= 3: award("b_streak3")
    if user['current_streak'] >= 7: award("b_streak7")
    if len(current_data['reps']) >= 20: award("b_rep_master")
    
    reps = current_data.get('reps', [])
    if reps and all(r.get('score',0) > 80 for r in reps): award("b_sniper")
    
    hr = datetime.now().hour
    if 22 <= hr or hr <= 4: award("b_night")
    if 5 <= hr <= 9: award("b_morning")
    if user['level'] >= 10: award("b_lvl10")

    return new_badges

# --- AUTH ---
bearer_scheme = HTTPBearer(auto_error=False)

def verify_supabase_token_and_get_user(token: str) -> dict:
    if not SUPABASE_URL or not SUPABASE_PUBLISHABLE_KEY:
        raise HTTPException(
            status_code=500,
            detail="SUPABASE_URL sau SUPABASE_PUBLISHABLE_KEY nu sunt configurate pe backend."
        )

    url = f"{SUPABASE_URL}/auth/v1/user"
    headers = {
        "apikey": SUPABASE_PUBLISHABLE_KEY,
        "Authorization": f"Bearer {token}",
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
    except requests.RequestException as exc:
        raise HTTPException(status_code=503, detail=f"Nu pot valida sesiunea Supabase: {exc}")

    if response.status_code != 200:
        raise HTTPException(status_code=401, detail="Token Supabase invalid sau expirat.")

    data = response.json()
    if not data or not data.get("email"):
        raise HTTPException(status_code=401, detail="User invalid in tokenul Supabase.")

    return data

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    if not credentials or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Lipseste Bearer token.")

    token = credentials.credentials
    supabase_user = verify_supabase_token_and_get_user(token)
    email = supabase_user.get("email")
    meta = supabase_user.get("user_metadata") or {}
    full_name = meta.get("full_name") or meta.get("name") or email.split("@")[0]

    conn = get_db_connection()
    try:
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

        if not user:
            # Pull existing XP/level/streak from Supabase so data survives device changes
            xp, level, streak = 0, 1, 0
            try:
                sp_resp = requests.get(
                    f"{SUPABASE_URL}/rest/v1/profiles",
                    headers={"apikey": SUPABASE_PUBLISHABLE_KEY, "Authorization": f"Bearer {token}"},
                    params={"id": f"eq.{supabase_user['id']}", "select": "total_xp,level,streak_days"},
                    timeout=5,
                )
                if sp_resp.status_code == 200:
                    rows = sp_resp.json()
                    if rows:
                        xp = rows[0].get("total_xp", 0) or 0
                        level = rows[0].get("level", 1) or 1
                        streak = rows[0].get("streak_days", 0) or 0
            except Exception:
                pass

            conn.execute(
                "INSERT INTO users (email, password_hash, full_name, xp, level, current_streak, last_workout_date) VALUES (?,?,?,?,?,?,NULL)",
                (email, "", full_name, xp, level, streak)
            )
            conn.commit()
            user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        elif full_name and user["full_name"] != full_name:
            conn.execute("UPDATE users SET full_name=? WHERE id=?", (full_name, user["id"]))
            conn.commit()
            user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

        if not user:
            raise HTTPException(status_code=401, detail="Utilizatorul nu a putut fi incarcat.")

        return {
            "local_user": user,
            "supabase_user": supabase_user,
            "token": token,
        }
    finally:
        conn.close()

@app.post("/token")
def login():
    raise HTTPException(410, "Login-ul se face acum prin Supabase Auth din frontend.")

@app.post("/register")
def register():
    raise HTTPException(410, "Inregistrarea se face acum prin Supabase Auth din frontend.")

@app.get("/users/me")
def me(current=Depends(get_current_user)):
    local_user = current["local_user"]

    conn = get_db_connection()
    badges = [
        b["badge_id"]
        for b in conn.execute(
            "SELECT badge_id FROM user_badges WHERE user_id=?",
            (local_user["id"],)
        )
    ]
    conn.close()

    return {
        "full_name": local_user["full_name"],
        "xp": local_user["xp"],
        "level": local_user["level"],
        "rank": get_rank_name(local_user["level"]),
        "streak": local_user["current_streak"],
        "next_level_xp": xp_for_next_level(local_user["level"]),
        "badges": badges,
        "email": local_user["email"],
    }

# --- SAVE & PROCESS ---
class SaveReq(BaseModel):
    exercise: str
    avg_score: int
    reps: List[Dict[str, Any]]
    raw_path: str = ""
    processed_path: str = ""
    feedback: List[str] = []

@app.post("/analyze/save")
def save(data: SaveReq, current=Depends(get_current_user)):
    conn = get_db_connection()

    local_user = current["local_user"]
    supabase_user = current["supabase_user"]
    user_token = current["token"]

    try:
        # 1. Calcul XP
        xp_reps = 0
        for r in data.reps:
            s = r.get('score', 0)
            if s > 90:
                xp_reps += 10
            elif s > 70:
                xp_reps += 5

        xp_bonus = 0
        if data.avg_score > 80:
            xp_bonus = 50
        elif data.avg_score >= 60:
            xp_bonus = 25

        # 2. Streak
        today = date.today()
        last_str = local_user['last_workout_date']
        streak = local_user['current_streak']

        if last_str:
            last_date = datetime.fromisoformat(last_str).date()
            diff = (today - last_date).days
            if diff == 1:
                streak += 1
            elif diff > 1:
                streak = 1
        else:
            streak = 1

        xp_streak = 0
        if streak >= 3:
            xp_streak = 100 * streak

        total_gain = xp_reps + xp_bonus + xp_streak
        new_xp = local_user['xp'] + total_gain

        # 3. Level Up
        curr_lvl = local_user['level']
        calc_lvl = 1
        xp_pool = new_xp

        while True:
            cost = xp_for_next_level(calc_lvl)
            if xp_pool >= cost:
                xp_pool -= cost
                calc_lvl += 1
            else:
                break

        is_levelup = calc_lvl > curr_lvl

        # 4. Insert Workout in SQLite
        conn.execute(
            """
            INSERT INTO workouts (
                user_id, exercise, avg_score, video_path, processed_video_path,
                feedback_json, reps_json, created_at
            ) VALUES (?,?,?,?,?,?,?,?)
            """,
            (
                local_user['id'],
                data.exercise,
                data.avg_score,
                data.raw_path,
                data.processed_path,
                json.dumps(data.feedback),
                json.dumps(data.reps),
                datetime.now().isoformat(),
            )
        )

        # 5. Update local SQLite user
        conn.execute(
            "UPDATE users SET xp=?, level=?, current_streak=?, last_workout_date=? WHERE id=?",
            (new_xp, calc_lvl, streak, today.isoformat(), local_user['id'])
        )

        # 6. Check badges in SQLite
        new_badges = check_badges(
            conn,
            local_user['id'],
            {"score": data.avg_score, "reps": data.reps, "exercise": data.exercise}
        )

        conn.commit()

        # 7. Update Supabase profiles using user's own JWT
        # presupune tabela public.profiles cu PK=id (uuid din auth.users)
        supabase_profile_url = f"{SUPABASE_URL}/rest/v1/profiles?id=eq.{supabase_user['id']}"
        supabase_headers = {
            "apikey": SUPABASE_PUBLISHABLE_KEY,
            "Authorization": f"Bearer {user_token}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }
        supabase_payload = {
            "total_xp": new_xp,
            "level": calc_lvl,
            "streak_days": streak,
            "full_name": local_user["full_name"],
        }

        supabase_response = requests.patch(
            supabase_profile_url,
            headers=supabase_headers,
            json=supabase_payload,
            timeout=10,
        )

        if supabase_response.status_code >= 400:
            print("SUPABASE PROFILE UPDATE STATUS:", supabase_response.status_code)
            print("SUPABASE PROFILE UPDATE BODY:", supabase_response.text)

        # 8. Update challenge entries for matching active challenges
        try:
            now_iso = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
            reps_count = len(data.reps)
            good_reps = sum(1 for r in data.reps if r.get('score', 0) >= 70)
            consistency_val = round((good_reps / reps_count) * 100) if reps_count > 0 else 0

            ch_resp = requests.get(
                f"{SUPABASE_URL}/rest/v1/challenges",
                headers={
                    "apikey": SUPABASE_PUBLISHABLE_KEY,
                    "Authorization": f"Bearer {user_token}",
                },
                params={
                    "exercise_type": f"eq.{data.exercise}",
                    "is_active": "eq.true",
                    "is_public": "eq.true",
                    "start_at": f"lte.{now_iso}",
                    "end_at": f"gte.{now_iso}",
                    "select": "id,metric_type",
                },
                timeout=10,
            )

            if ch_resp.status_code == 200:
                for ch in ch_resp.json():
                    ch_id = ch['id']
                    metric = ch['metric_type']

                    if metric == 'max_reps':
                        session_value = reps_count
                    elif metric == 'best_score':
                        session_value = data.avg_score
                    elif metric == 'total_reps':
                        session_value = reps_count
                    elif metric == 'consistency':
                        session_value = consistency_val
                    else:
                        continue

                    entry_resp = requests.get(
                        f"{SUPABASE_URL}/rest/v1/challenge_entries",
                        headers={
                            "apikey": SUPABASE_PUBLISHABLE_KEY,
                            "Authorization": f"Bearer {user_token}",
                        },
                        params={
                            "challenge_id": f"eq.{ch_id}",
                            "user_id": f"eq.{supabase_user['id']}",
                            "select": "id,value",
                        },
                        timeout=10,
                    )

                    if entry_resp.status_code == 200:
                        entries = entry_resp.json()
                        if not entries:
                            continue

                        current_val = float(entries[0]['value'])
                        entry_id = entries[0]['id']

                        if metric == 'total_reps':
                            new_val = current_val + session_value
                        else:
                            new_val = max(current_val, session_value)

                        requests.patch(
                            f"{SUPABASE_URL}/rest/v1/challenge_entries",
                            headers={
                                "apikey": SUPABASE_PUBLISHABLE_KEY,
                                "Authorization": f"Bearer {user_token}",
                                "Content-Type": "application/json",
                            },
                            params={"id": f"eq.{entry_id}"},
                            json={"value": new_val, "updated_at": now_iso},
                            timeout=10,
                        )
        except Exception as e:
            print(f"Challenge update error: {e}")

        return {
            "xp_table": {
                "reps": xp_reps,
                "bonus": xp_bonus,
                "streak": xp_streak,
                "total": total_gain
            },
            "level_up": is_levelup,
            "new_level": calc_lvl,
            "badges": new_badges
        }

    except Exception as e:
        conn.rollback()
        raise HTTPException(500, f"Database Error: {e}")
    finally:
        conn.close()

def reset_rep_memory():
    return {
        "start_hold": 0,
        "bottom_hold": 0,
        "finish_hold": 0,
        "start_frame": None,
        "start_lms": None,
        "bottom_frame": None,
        "bottom_lms": None,
        "bottom_quality": None,
        "trajectory": [],
        "trajectory_details": [],

        # Date folosite special pentru Bench Press.
        # Pentru acest exercițiu, cadrul de jos nu este suficient:
        # trebuie analizată traiectoria brațelor pe toată repetarea.
        "bench_wrist_mid": [],
        "bench_left_wrist": [],
        "bench_right_wrist": [],
        "bench_left_elbow": [],
        "bench_right_elbow": [],
        "bench_elbow_avg": [],

        "mountain_last_confirmed_side": "none",
        "mountain_pending_side": "none",
        "mountain_pending_count": 0,
        "mountain_rep_cooldown": 0,
        "mountain_last_rep_frame_idx": -999,
        "mountain_min_frames_between_reps": 6,
        "mountain_required_confirm_frames": 2,
        "mountain_best_frame": None,
        "mountain_best_lms": None,
        "mountain_best_quality": None,
        "mountain_candidate_frame": None,
        "mountain_candidate_lms": None,
        "mountain_candidate_quality": None,
        "mountain_signal": [],
        "mountain_left_signal": [],
        "mountain_right_signal": [],
        "mountain_frames": [],
        "mountain_lms": [],
        "mountain_frame_indices": [],
        "mountain_rep_frames_used": set(),
    }


def _motion_y(final_exercise, lms):
    """Returnează coordonata Y folosită pentru viteza execuției."""
    if final_exercise == "Flotare":
        return float((lms[11].y + lms[12].y) / 2.0)
    if final_exercise == "Tractiuni":
        return float((lms[11].y + lms[12].y) / 2.0)
    if final_exercise == "Abdomene":
        return float(lms[0].y)
    if final_exercise in ["Biceps Curl", "Lateral Raise", "Bench Press"]:
        return float(((lms[15].y + lms[16].y) / 2.0))
    return float((lms[23].y + lms[24].y) / 2.0)


def record_rep_trajectory(final_exercise, lms, rep_memory):
    y = _motion_y(final_exercise, lms)
    traj = rep_memory.setdefault("trajectory", [])
    if not traj or abs(traj[-1] - y) > 1e-6:
        traj.append(y)

    detail = _trajectory_detail(final_exercise, lms)
    if detail:
        rep_memory.setdefault("trajectory_details", []).append(detail)


def _midpoint(a, b):
    return ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)


def _trajectory_detail(final_exercise, lms):
    left_shoulder = (float(lms[11].x), float(lms[11].y))
    right_shoulder = (float(lms[12].x), float(lms[12].y))
    left_elbow = (float(lms[13].x), float(lms[13].y))
    right_elbow = (float(lms[14].x), float(lms[14].y))
    left_wrist = (float(lms[15].x), float(lms[15].y))
    right_wrist = (float(lms[16].x), float(lms[16].y))
    left_hip = (float(lms[23].x), float(lms[23].y))
    right_hip = (float(lms[24].x), float(lms[24].y))
    left_ankle = (float(lms[27].x), float(lms[27].y))
    right_ankle = (float(lms[28].x), float(lms[28].y))
    nose = (float(lms[0].x), float(lms[0].y))

    shoulder_mid = _midpoint(left_shoulder, right_shoulder)
    hip_mid = _midpoint(left_hip, right_hip)
    ankle_mid = _midpoint(left_ankle, right_ankle)
    wrist_mid = _midpoint(left_wrist, right_wrist)

    left_elbow_angle = calculate_angle(left_shoulder, left_elbow, left_wrist)
    right_elbow_angle = calculate_angle(right_shoulder, right_elbow, right_wrist)
    elbow_avg = (left_elbow_angle + right_elbow_angle) / 2.0

    detail = {
        "shoulder_y": shoulder_mid[1],
        "shoulder_x": shoulder_mid[0],
        "hip_y": hip_mid[1],
        "hip_x": hip_mid[0],
        "ankle_y": ankle_mid[1],
        "wrist_y": wrist_mid[1],
        "nose_y": nose[1],
        "elbow_avg": float(elbow_avg),
        "left_elbow_angle": float(left_elbow_angle),
        "right_elbow_angle": float(right_elbow_angle),
        "body_alignment": float(calculate_angle(shoulder_mid, hip_mid, ankle_mid)),
        "shoulder_hip_dx": float(abs(shoulder_mid[0] - hip_mid[0])),
    }

    if final_exercise == "Abdomene":
        left_knee = (float(lms[25].x), float(lms[25].y))
        detail["torso_angle"] = float(calculate_angle(left_shoulder, left_hip, left_knee))
        detail["neck_angle"] = float(calculate_angle(nose, left_shoulder, left_hip))

    return detail


def record_bench_trajectory(lms, rep_memory):
    """
    Salvează traiectoria brațelor pentru Bench Press pe parcursul unei repetări.

    Folosim încheieturile ca proxy pentru traiectoria barei/ganterelor.
    Analiza se face ulterior pe:
    - drift orizontal al traiectoriei;
    - simetria stânga-dreapta;
    - amplitudinea coatelor.
    """
    left_wrist = (float(lms[15].x), float(lms[15].y))
    right_wrist = (float(lms[16].x), float(lms[16].y))
    left_elbow = (float(lms[13].x), float(lms[13].y))
    right_elbow = (float(lms[14].x), float(lms[14].y))

    wrist_mid = (
        (left_wrist[0] + right_wrist[0]) / 2.0,
        (left_wrist[1] + right_wrist[1]) / 2.0,
    )

    left_elbow_angle = calculate_angle(
        (lms[11].x, lms[11].y),
        (lms[13].x, lms[13].y),
        (lms[15].x, lms[15].y),
    )

    right_elbow_angle = calculate_angle(
        (lms[12].x, lms[12].y),
        (lms[14].x, lms[14].y),
        (lms[16].x, lms[16].y),
    )

    elbow_avg = (left_elbow_angle + right_elbow_angle) / 2.0

    rep_memory.setdefault("bench_wrist_mid", []).append(wrist_mid)
    rep_memory.setdefault("bench_left_wrist", []).append(left_wrist)
    rep_memory.setdefault("bench_right_wrist", []).append(right_wrist)
    rep_memory.setdefault("bench_left_elbow", []).append(left_elbow)
    rep_memory.setdefault("bench_right_elbow", []).append(right_elbow)
    rep_memory.setdefault("bench_elbow_avg", []).append(float(elbow_avg))


def evaluate_bench_trajectory(rep_memory):
    """
    Evaluează traiectoria brațelor pentru Bench Press.

    Observație:
    - MediaPipe nu vede bara, deci folosim media încheieturilor ca proxy.
    - Pentru filmări din lateral, drift-ul pe X reflectă faptul că bara fuge înainte/înapoi.
    - Pentru filmări frontale, simetria stânga-dreapta este mai relevantă.
    """
    wrist_mid = np.array(rep_memory.get("bench_wrist_mid", []), dtype=float)
    left_wrist = np.array(rep_memory.get("bench_left_wrist", []), dtype=float)
    right_wrist = np.array(rep_memory.get("bench_right_wrist", []), dtype=float)
    elbow_avg = np.array(rep_memory.get("bench_elbow_avg", []), dtype=float)

    feedback = []

    if len(wrist_mid) < 6 or len(left_wrist) < 6 or len(right_wrist) < 6 or len(elbow_avg) < 6:
        return {
            "bench_path_score": 85,
            "bench_symmetry_trajectory_score": 85,
            "bench_lockout_score": 85,
            "bench_trajectory_score": 85,
            "bench_path_x_drift": 0.0,
            "bench_path_y_rom": 0.0,
            "bench_path_drift_ratio": 0.0,
            "bench_hand_y_asymmetry": 0.0,
            "bench_elbow_rom": 0.0,
            "bench_elbow_min": 0.0,
            "bench_elbow_max": 0.0,
        }, ["Nu au fost suficiente cadre pentru analiza completă a traiectoriei brațelor."]

    x = wrist_mid[:, 0]
    y = wrist_mid[:, 1]

    y_rom = float(np.percentile(y, 90) - np.percentile(y, 10))
    x_drift = float(np.percentile(x, 90) - np.percentile(x, 10))
    drift_ratio = float(x_drift / (y_rom + 1e-6))

    # 1. Traiectoria principală: brațele trebuie să se miște controlat, fără drift mare.
    if y_rom < 0.015:
        path_score = 60
        feedback.append("Amplitudinea mișcării brațelor pare prea mică pentru o repetare completă.")
    else:
        if drift_ratio <= 0.35:
            path_score = 100
            feedback.append("Traiectoria brațelor este stabilă și aproape verticală.")
        elif drift_ratio <= 0.55:
            path_score = 75
            feedback.append("Traiectoria brațelor este acceptabilă, dar există o ușoară deplasare înainte/înapoi.")
        else:
            path_score = 45
            feedback.append("Traiectoria brațelor deviază prea mult; încearcă să cobori și să împingi pe o linie mai controlată.")

    # 2. Simetria stânga-dreapta: o mână nu ar trebui să fie constant mai jos/sus.
    hand_y_diff = np.abs(left_wrist[:, 1] - right_wrist[:, 1])
    hand_y_asym = float(np.percentile(hand_y_diff, 90))

    if hand_y_asym <= 0.035:
        symmetry_score = 100
        feedback.append("Brațele se mișcă simetric pe verticală.")
    elif hand_y_asym <= 0.065:
        symmetry_score = 75
        feedback.append("Există o mică diferență între brațe pe traiectorie.")
    else:
        symmetry_score = 45
        feedback.append("Un braț pare să rămână în urmă; încearcă să împingi egal cu ambele mâini.")

    # 3. ROM coate: repetarea trebuie să aibă coborâre + extensie.
    elbow_rom = float(np.percentile(elbow_avg, 90) - np.percentile(elbow_avg, 10))
    elbow_min = float(np.percentile(elbow_avg, 10))
    elbow_max = float(np.percentile(elbow_avg, 90))

    if elbow_rom >= 35 and elbow_min <= 115 and elbow_max >= 140:
        lockout_score = 100
        feedback.append("Amplitudinea coatelor este bună: coborâre și împingere complete.")
    elif elbow_rom >= 25:
        lockout_score = 75
        feedback.append("Amplitudinea este acceptabilă, dar poți controla mai bine coborârea sau extensia finală.")
    else:
        lockout_score = 45
        feedback.append("Mișcarea pare prea scurtă; coboară și extinde mai complet brațele.")

    trajectory_score = int(
        0.45 * path_score +
        0.35 * symmetry_score +
        0.20 * lockout_score
    )

    return {
        "bench_path_score": int(path_score),
        "bench_symmetry_trajectory_score": int(symmetry_score),
        "bench_lockout_score": int(lockout_score),
        "bench_trajectory_score": int(trajectory_score),
        "bench_path_x_drift": round(x_drift, 4),
        "bench_path_y_rom": round(y_rom, 4),
        "bench_path_drift_ratio": round(drift_ratio, 3),
        "bench_hand_y_asymmetry": round(hand_y_asym, 4),
        "bench_elbow_rom": round(elbow_rom, 2),
        "bench_elbow_min": round(elbow_min, 2),
        "bench_elbow_max": round(elbow_max, 2),
    }, feedback


def evaluate_bench_trajectory_v2(rep_memory):
    """
    Bench Press:
    - cadrul de jos ramane cel mai important pentru postura;
    - traiectoria verifica extensia sus, simetria si drift-ul mainilor.
    """
    wrist_mid = np.array(rep_memory.get("bench_wrist_mid", []), dtype=float)
    left_wrist = np.array(rep_memory.get("bench_left_wrist", []), dtype=float)
    right_wrist = np.array(rep_memory.get("bench_right_wrist", []), dtype=float)
    elbow_avg = np.array(rep_memory.get("bench_elbow_avg", []), dtype=float)

    if len(wrist_mid) < 6 or len(left_wrist) < 6 or len(right_wrist) < 6 or len(elbow_avg) < 6:
        return {
            "bench_path_score": 85,
            "bench_symmetry_trajectory_score": 85,
            "bench_bottom_depth_score": 85,
            "bench_lockout_score": 85,
            "bench_rom_score": 85,
            "bench_trajectory_score": 85,
            "bench_path_x_drift": 0.0,
            "bench_path_y_rom": 0.0,
            "bench_path_drift_ratio": 0.0,
            "bench_hand_y_asymmetry": 0.0,
            "bench_elbow_rom": 0.0,
            "bench_elbow_min": 0.0,
            "bench_elbow_max": 0.0,
        }, ["Nu au fost suficiente cadre pentru analiza completa a traiectoriei bratelor."]

    x = wrist_mid[:, 0]
    y = wrist_mid[:, 1]
    y_rom = float(np.percentile(y, 90) - np.percentile(y, 10))
    x_drift = float(np.percentile(x, 90) - np.percentile(x, 10))
    drift_ratio = float(x_drift / (y_rom + 1e-6))

    feedback = []
    if y_rom < 0.015:
        path_score = 60
        feedback.append("Amplitudinea miscarii bratelor pare prea mica pentru o repetare completa.")
    elif drift_ratio <= 0.35:
        path_score = 100
        feedback.append("Traiectoria bratelor este stabila si aproape verticala.")
    elif drift_ratio <= 0.55:
        path_score = 75
        feedback.append("Traiectoria bratelor este acceptabila, dar exista o usoara deplasare inainte/inapoi.")
    else:
        path_score = 45
        feedback.append("Traiectoria bratelor deviaza prea mult; incearca sa cobori si sa impingi pe o linie mai controlata.")

    hand_y_diff = np.abs(left_wrist[:, 1] - right_wrist[:, 1])
    hand_y_asym = float(np.percentile(hand_y_diff, 90))
    if hand_y_asym <= 0.035:
        symmetry_score = 100
        feedback.append("Bratele se misca simetric pe verticala.")
    elif hand_y_asym <= 0.065:
        symmetry_score = 75
        feedback.append("Exista o mica diferenta intre brate pe traiectorie.")
    else:
        symmetry_score = 45
        feedback.append("Un brat pare sa ramana in urma; incearca sa impingi egal cu ambele maini.")

    elbow_rom = float(np.percentile(elbow_avg, 90) - np.percentile(elbow_avg, 10))
    elbow_min = float(np.percentile(elbow_avg, 10))
    elbow_max = float(np.percentile(elbow_avg, 90))

    if elbow_min <= 110:
        bottom_depth_score = 100
    elif elbow_min <= 125:
        bottom_depth_score = 75
    else:
        bottom_depth_score = 45

    if elbow_max >= 145:
        lockout_score = 100
        feedback.append("Extensia de sus este buna; finalizezi impingerea cu bratele aproape intinse.")
    elif elbow_max >= 130:
        lockout_score = 75
        feedback.append("Extinde putin mai complet bratele in partea de sus.")
    else:
        lockout_score = 45
        feedback.append("Nu finalizezi impingerea sus; cauta o extensie mai completa a bratelor.")

    if elbow_rom >= 35 and bottom_depth_score >= 75 and lockout_score >= 75:
        rom_score = 100
        feedback.append("Repetarea are coborare si impingere complete.")
    elif elbow_rom >= 25:
        rom_score = 75
        feedback.append("Amplitudinea este acceptabila, dar poti controla mai bine coborarea sau extensia finala.")
    else:
        rom_score = 45
        feedback.append("Miscarea pare prea scurta; coboara si extinde mai complet bratele.")

    trajectory_score = int(
        0.40 * path_score +
        0.30 * symmetry_score +
        0.30 * rom_score
    )

    return {
        "bench_path_score": int(path_score),
        "bench_symmetry_trajectory_score": int(symmetry_score),
        "bench_bottom_depth_score": int(bottom_depth_score),
        "bench_lockout_score": int(lockout_score),
        "bench_rom_score": int(rom_score),
        "bench_trajectory_score": int(trajectory_score),
        "bench_path_x_drift": round(x_drift, 4),
        "bench_path_y_rom": round(y_rom, 4),
        "bench_path_drift_ratio": round(drift_ratio, 3),
        "bench_hand_y_asymmetry": round(hand_y_asym, 4),
        "bench_elbow_rom": round(elbow_rom, 2),
        "bench_elbow_min": round(elbow_min, 2),
        "bench_elbow_max": round(elbow_max, 2),
    }, feedback


def apply_bench_trajectory_metrics(metrics, feedback, rep_memory):
    """
    Combină scorul de postură Bench Press cu scorul de traiectorie.

    Pentru Bench Press, traiectoria brațelor contează mult, deci are pondere mare.
    """
    traj_metrics, traj_feedback = evaluate_bench_trajectory_v2(rep_memory)

    posture_score = int(metrics.get("total_score", 0) or 0)
    trajectory_score = int(traj_metrics.get("bench_trajectory_score", 85))

    total_score = int(round(
        0.65 * posture_score +
        0.35 * trajectory_score
    ))

    metrics.update(traj_metrics)
    metrics["bench_posture_score"] = posture_score
    metrics["bench_trajectory_score"] = trajectory_score
    metrics["total_score"] = total_score

    feedback.extend(traj_feedback)

    return metrics


def _bottom_quality(rep_state):
    if "hip_y" in rep_state and "knee_avg" in rep_state:
        hip_y = float(rep_state.get("hip_y", 0.0))
        knee_avg = float(rep_state.get("knee_avg", 180.0))
        trunk_avg = float(rep_state.get("trunk_avg", 0.0))
        return hip_y * 100.0 + (180.0 - knee_avg) * 0.45 + trunk_avg * 0.08

    if "chest_distance" in rep_state and "elbow_avg" in rep_state:
        chest_distance = float(rep_state.get("chest_distance", 1.0))
        elbow_avg = float(rep_state.get("elbow_avg", 180.0))
        return (1.0 - chest_distance) * 100.0 + (180.0 - elbow_avg) * 0.35

    if "front_knee" in rep_state:
        front_knee = float(rep_state.get("front_knee", 180.0))
        back_depth = float(rep_state.get("back_depth", 0.0))
        return (180.0 - front_knee) * 0.7 + back_depth * 100.0

    if "elbow_avg" in rep_state:
        elbow_avg = float(rep_state.get("elbow_avg", 180.0))
        if "wrist_level" in rep_state:
            return (1.0 - float(rep_state.get("wrist_level", 1.0))) * 100.0 + (180.0 - elbow_avg) * 0.05
        if "wrist_above_shoulder" in rep_state:
            return float(rep_state.get("wrist_above_shoulder", 0.0)) * 100.0 + elbow_avg * 0.2
        return (180.0 - elbow_avg) * 0.8

    return 0.0


def _store_bottom_if_better(rep_state, frame, lms, rep_memory):
    q = _bottom_quality(rep_state)
    if rep_memory.get("bottom_quality") is None or q > rep_memory["bottom_quality"]:
        rep_memory["bottom_quality"] = q
        rep_memory["bottom_frame"] = frame.copy()
        rep_memory["bottom_lms"] = lms


def _mountain_frame_quality(rep_state):
    current_side = rep_state.get("active_side", "none")
    if current_side == "left":
        drive = float(rep_state.get("left_drive", 0.0))
    elif current_side == "right":
        drive = float(rep_state.get("right_drive", 0.0))
    else:
        drive = max(
            float(rep_state.get("left_drive", 0.0)),
            float(rep_state.get("right_drive", 0.0)),
        )

    alignment = float(rep_state.get("body_alignment", 180.0))
    alignment_bonus = max(0.0, 1.0 - abs(alignment - 180.0) / 90.0)
    return drive * 100.0 + alignment_bonus * 10.0


def _store_mountain_best_frame(rep_state, frame, lms, rep_memory):
    quality = _mountain_frame_quality(rep_state)
    best = rep_memory.get("mountain_best_quality")
    if best is None or quality > best:
        rep_memory["mountain_best_frame"] = frame.copy()
        rep_memory["mountain_best_lms"] = lms
        rep_memory["mountain_best_quality"] = quality
    return quality


def _clamp01(value):
    return float(max(0.0, min(1.0, value)))


def _landmark_xy(landmarks, idx):
    return np.array([float(landmarks[idx].x), float(landmarks[idx].y)], dtype=float)


def _mountain_counting_signals_from_landmarks(landmarks):
    if landmarks is None or len(landmarks) <= 28:
        return None

    left_shoulder = _landmark_xy(landmarks, 11)
    right_shoulder = _landmark_xy(landmarks, 12)
    left_hip = _landmark_xy(landmarks, 23)
    right_hip = _landmark_xy(landmarks, 24)
    left_knee = _landmark_xy(landmarks, 25)
    right_knee = _landmark_xy(landmarks, 26)
    left_ankle = _landmark_xy(landmarks, 27)
    right_ankle = _landmark_xy(landmarks, 28)

    shoulder_mid = (left_shoulder + right_shoulder) / 2.0
    hip_mid = (left_hip + right_hip) / 2.0
    ankle_mid = (left_ankle + right_ankle) / 2.0

    torso_axis = shoulder_mid - hip_mid
    torso_len = float(np.linalg.norm(torso_axis))
    if torso_len < 0.03:
        torso_axis = shoulder_mid - ankle_mid
        torso_len = float(np.linalg.norm(torso_axis))
    if torso_len < 0.03:
        return None

    torso_unit = torso_axis / torso_len
    body_len = max(0.25, float(np.linalg.norm(shoulder_mid - ankle_mid)))
    chest_anchor = (shoulder_mid + hip_mid) / 2.0

    def side_signal(hip, knee, ankle):
        knee_angle = calculate_angle(tuple(hip), tuple(knee), tuple(ankle))
        # Allow knee angle up to 175 (slightly bent) for more flexible detection
        if knee_angle >= 175:
            return 0.0

        # Mountain climbers count when the knee is both bent and travelling
        # toward the shoulders. This prevents a straight-leg plank/start frame
        # from being treated as a repetition.
        # Improved thresholds for better detection of actual knee drives
        knee_projection = float(np.dot(knee - hip, torso_unit) / (torso_len + 1e-6))
        projection_score = _clamp01((knee_projection - 0.05) / 0.60)
        bend_score = _clamp01((175.0 - knee_angle) / 75.0)

        knee_to_chest = float(np.linalg.norm(knee - chest_anchor) / (body_len + 1e-6))
        distance_score = _clamp01((0.62 - knee_to_chest) / 0.30)

        signal = bend_score * (0.65 * projection_score + 0.35 * distance_score)
        # Reduced minimum thresholds to catch more valid reps
        if projection_score < 0.05 or bend_score < 0.06:
            return 0.0
        return _clamp01(signal)

    return (
        side_signal(left_hip, left_knee, left_ankle),
        side_signal(right_hip, right_knee, right_ankle),
    )


def _mountain_side_drive_signals(rep_state):
    left_drive = rep_state.get("left_drive")
    right_drive = rep_state.get("right_drive")

    if left_drive is not None and right_drive is not None:
        left_signal = float(left_drive)
        right_signal = float(right_drive)
    else:
        left_dist = rep_state.get("left_knee_to_chest")
        right_dist = rep_state.get("right_knee_to_chest")
        if left_dist is None or right_dist is None:
            left_signal = 0.0
            right_signal = 0.0
        else:
            left_signal = 0.60 - float(left_dist)
            right_signal = 0.60 - float(right_dist)

    left_signal = float(max(0.0, min(1.0, left_signal)))
    right_signal = float(max(0.0, min(1.0, right_signal)))
    return left_signal, right_signal


def _mountain_drive_signal(rep_state):
    left_signal, right_signal = _mountain_side_drive_signals(rep_state)
    return max(left_signal, right_signal)


def record_mountain_climber_signal(rep_state, frame, lms, rep_memory, frame_idx=None):
    counting_signals = _mountain_counting_signals_from_landmarks(lms)
    if counting_signals is not None:
        left_signal, right_signal = counting_signals
    else:
        left_signal, right_signal = _mountain_side_drive_signals(rep_state)

    drive_signal = max(left_signal, right_signal)
    rep_memory.setdefault("mountain_signal", []).append(drive_signal)
    rep_memory.setdefault("mountain_left_signal", []).append(left_signal)
    rep_memory.setdefault("mountain_right_signal", []).append(right_signal)
    rep_memory.setdefault("mountain_frames", []).append(frame.copy())
    rep_memory.setdefault("mountain_lms", []).append(lms)
    rep_memory.setdefault("mountain_frame_indices", []).append(frame_idx)
    _store_mountain_best_frame(rep_state, frame, lms, rep_memory)
    return drive_signal


def update_mountain_climber_state(rep_state, frame, lms, rep_memory, frame_idx=0, rep_count=0):
    quality = _store_mountain_best_frame(rep_state, frame, lms, rep_memory)
    current_side = rep_state.get("active_side", "none")
    if current_side not in ["left", "right"]:
        if rep_memory.get("mountain_rep_cooldown", 0) > 0:
            rep_memory["mountain_rep_cooldown"] -= 1
        return None

    if current_side == rep_memory.get("mountain_pending_side", "none"):
        rep_memory["mountain_pending_count"] += 1
    else:
        rep_memory["mountain_pending_side"] = current_side
        rep_memory["mountain_pending_count"] = 1

    if rep_memory["mountain_pending_count"] < rep_memory.get("mountain_required_confirm_frames", 2):
        if rep_memory.get("mountain_rep_cooldown", 0) > 0:
            rep_memory["mountain_rep_cooldown"] -= 1
        return None

    confirmed_side = current_side
    drive = float(rep_state.get("left_drive" if confirmed_side == "left" else "right_drive", 0.0))
    if drive < 0.12:
        return None

    last_frame = int(rep_memory.get("mountain_last_rep_frame_idx", -999))
    min_gap = int(rep_memory.get("mountain_min_frames_between_reps", 6))
    if frame_idx - last_frame < min_gap:
        if rep_memory.get("mountain_rep_cooldown", 0) > 0:
            rep_memory["mountain_rep_cooldown"] -= 1
        return None

    last_confirmed = rep_memory.get("mountain_last_confirmed_side", "none")
    if last_confirmed == "none":
        rep_memory["mountain_last_confirmed_side"] = confirmed_side
        rep_memory["mountain_candidate_frame"] = frame.copy()
        rep_memory["mountain_candidate_lms"] = lms
        rep_memory["mountain_candidate_quality"] = quality
        if DEBUG_MOUNTAIN:
            print({
                "frame_idx": frame_idx,
                "current_side": current_side,
                "pending_side": rep_memory["mountain_pending_side"],
                "pending_count": rep_memory["mountain_pending_count"],
                "last_confirmed_side": rep_memory["mountain_last_confirmed_side"],
                "drive": drive,
                "rep_count": rep_count,
            })
        return None

    if confirmed_side == last_confirmed:
        if rep_memory.get("mountain_candidate_quality") is None or quality > rep_memory["mountain_candidate_quality"]:
            rep_memory["mountain_candidate_frame"] = frame.copy()
            rep_memory["mountain_candidate_lms"] = lms
            rep_memory["mountain_candidate_quality"] = quality
        return None

    if rep_memory.get("mountain_candidate_frame") is not None and rep_memory.get("mountain_candidate_lms") is not None:
        completed = (
            rep_memory["mountain_candidate_frame"],
            rep_memory["mountain_candidate_lms"],
        )
    else:
        completed = (frame.copy(), lms)

    rep_memory["mountain_last_confirmed_side"] = confirmed_side
    rep_memory["mountain_last_rep_frame_idx"] = frame_idx
    rep_memory["mountain_rep_cooldown"] = min_gap
    rep_memory["mountain_candidate_frame"] = frame.copy()
    rep_memory["mountain_candidate_lms"] = lms
    rep_memory["mountain_candidate_quality"] = quality

    if DEBUG_MOUNTAIN:
        print({
            "frame_idx": frame_idx,
            "current_side": current_side,
            "pending_side": rep_memory["mountain_pending_side"],
            "pending_count": rep_memory["mountain_pending_count"],
            "last_confirmed_side": rep_memory["mountain_last_confirmed_side"],
            "drive": drive,
            "rep_count": rep_count,
        })

    return completed


def update_rep_fsm(state, rep_state, frame, lms, rep_memory):
    """
    FSM tolerant pentru video-uri scurte / o singură repetare.
    Păstrează cel mai bun cadru de jos pentru evaluarea posturii.
    """
    if state == "idle":
        if rep_state["start_ok"]:
            rep_memory["start_hold"] += 1
            rep_memory["start_frame"] = frame.copy()
            rep_memory["start_lms"] = lms
            return "start"

        if rep_state["bottom_ok"]:
            rep_memory["bottom_hold"] += 1
            _store_bottom_if_better(rep_state, frame, lms, rep_memory)
            return "bottom"

    elif state == "start":
        if rep_state["bottom_ok"]:
            rep_memory["bottom_hold"] += 1
            _store_bottom_if_better(rep_state, frame, lms, rep_memory)
            return "bottom"
        else:
            rep_memory["bottom_hold"] = 0

    elif state == "bottom":
        if rep_state["bottom_ok"]:
            rep_memory["bottom_hold"] += 1
            _store_bottom_if_better(rep_state, frame, lms, rep_memory)

        if rep_state["finish_ok"]:
            rep_memory["finish_hold"] += 1
        else:
            rep_memory["finish_hold"] = 0

        if rep_memory["finish_hold"] >= 1:
            return "complete"

    return state


def reset_live_rep_memory():
    """
    Memorie pentru repetari in modul live.
    Adauga praguri de debouncing fata de varianta pentru analiza video,
    deoarece fluxul live are FPS mai mic (~12) si zgomot mai mare de landmark-uri.
    """
    m = reset_rep_memory()
    m["min_start_hold"] = 2   # cadre consecutive necesare pentru idle → start
    m["min_bottom_hold"] = 2  # cadre consecutive necesare in bottom inainte de a permite finish
    m["min_finish_hold"] = 3  # cadre consecutive necesare pentru bottom → complete
    m["rep_cooldown"] = 0     # cadre de asteptare dupa o repetare completa
    m["has_been_start"] = False  # previne idle → bottom direct la pornire
    return m


def update_live_rep_fsm(state, rep_state, frame, lms, rep_memory):
    """
    FSM cu debouncing pentru modul live.

    Diferente fata de update_rep_fsm (folosit la analiza video):
    - Fiecare tranzitie necesita mai multe cadre consecutive, nu unul singur.
    - Cooldown dupa fiecare repetare completa previne dublarea.
    - Calea directa idle → bottom este blocata pana cand pozitia de start
      a fost confirmata cel putin o data in sesiune (previne false trigger
      daca utilizatorul porneste deja ghemuit/in pozitie de jos).
    """
    cooldown = rep_memory.get("rep_cooldown", 0)
    if cooldown > 0:
        rep_memory["rep_cooldown"] = cooldown - 1
        return state

    min_start = rep_memory.get("min_start_hold", 2)
    min_bottom = rep_memory.get("min_bottom_hold", 2)
    min_finish = rep_memory.get("min_finish_hold", 3)

    if state == "idle":
        if rep_state["start_ok"]:
            rep_memory["start_hold"] += 1
            rep_memory["start_frame"] = frame.copy()
            rep_memory["start_lms"] = lms
            if rep_memory["start_hold"] >= min_start:
                rep_memory["has_been_start"] = True
                return "start"
        else:
            rep_memory["start_hold"] = 0

        if rep_state["bottom_ok"] and rep_memory.get("has_been_start", False):
            rep_memory["bottom_hold"] += 1
            _store_bottom_if_better(rep_state, frame, lms, rep_memory)
            return "bottom"

    elif state == "start":
        if rep_state["bottom_ok"]:
            rep_memory["bottom_hold"] += 1
            _store_bottom_if_better(rep_state, frame, lms, rep_memory)
            return "bottom"
        else:
            rep_memory["bottom_hold"] = 0

    elif state == "bottom":
        if rep_state["bottom_ok"]:
            rep_memory["bottom_hold"] += 1
            _store_bottom_if_better(rep_state, frame, lms, rep_memory)

        if rep_state["finish_ok"]:
            rep_memory["finish_hold"] += 1
        else:
            rep_memory["finish_hold"] = 0

        if (rep_memory["bottom_hold"] >= min_bottom
                and rep_memory["finish_hold"] >= min_finish):
            rep_memory["rep_cooldown"] = 10
            rep_memory["has_been_start"] = False
            return "complete"

    return state


def _smooth_signal(values):
    """Netezire robustă pentru zgomotul MediaPipe, fără să schimbe forma mișcării."""
    arr = np.array(values, dtype=float)
    if len(arr) < 5:
        return arr

    # median filter simplu, ca să eliminăm jitter-ul landmark-urilor
    padded = np.pad(arr, (1, 1), mode="edge")
    med = np.array([np.median(padded[i:i + 3]) for i in range(len(arr))], dtype=float)

    # moving average scurt
    if len(arr) >= 9:
        kernel = np.ones(5, dtype=float) / 5.0
    else:
        kernel = np.ones(3, dtype=float) / 3.0

    smooth = np.convolve(med, kernel, mode="same")
    smooth[0] = arr[0]
    smooth[-1] = arr[-1]
    return smooth


def _phase_speed_stats(segment, fps=30.0):
    """
    Calculează constanța vitezei într-o singură fază, separat.

    Important:
    - ignoră începutul și finalul fazei, unde accelerarea/decelerarea este normală;
    - ignoră micro-vibrațiile MediaPipe;
    - folosește MAD/median, nu std/mean, deci nu penalizează exagerat outlierii.
    """
    seg = np.array(segment, dtype=float)
    fps = float(fps or 30.0)
    if fps <= 1:
        fps = 30.0

    if len(seg) < 5:
        return {
            "mean_speed": 0.0,
            "cv": 0.0,
            "consistency_score": 92,
            "duration_sec": round(len(seg) / fps, 2),
            "count": int(len(seg)),
        }

    seg = _smooth_signal(seg)
    rom = float(np.max(seg) - np.min(seg))
    duration = float((len(seg) - 1) / fps)

    if rom < 0.008:
        return {
            "mean_speed": 0.0,
            "cv": 0.0,
            "consistency_score": 90,
            "duration_sec": round(duration, 2),
            "count": int(len(seg)),
        }

    # Normalizăm la amplitudinea fazei. Așa pragurile merg pentru toate exercițiile.
    norm = (seg - seg[0]) / (rom + 1e-6)
    vel = np.abs(np.diff(norm))

    # Scoatem marginile fazei: e normal să accelerezi la început și să frânezi la final.
    if len(vel) >= 8:
        trim = max(1, int(len(vel) * 0.15))
        vel_core = vel[trim:-trim] if len(vel) - 2 * trim >= 4 else vel
    else:
        vel_core = vel

    # Eliminăm micro-mișcările / tremuratul landmark-urilor.
    noise_floor = max(0.004, np.percentile(vel_core, 20) * 0.6)
    moving = vel_core[vel_core > noise_floor]

    if len(moving) < 4:
        return {
            "mean_speed": round(float(np.mean(vel)) * fps, 5) if len(vel) else 0.0,
            "cv": 0.0,
            "consistency_score": 90,
            "duration_sec": round(duration, 2),
            "count": int(len(seg)),
        }

    med = float(np.median(moving))
    mad = float(np.median(np.abs(moving - med)))

    # robust_cv: variație relativă robustă. 1.4826 transformă MAD spre echivalent std.
    robust_cv = float((1.4826 * mad) / (med + 1e-6))

    # Foarte blând: execuțiile normale rămân sus; penalizăm doar variații mari.
    consistency_score = int(max(55, min(100, 100 - robust_cv * 35)))

    return {
        "mean_speed": round(float(np.median(moving)) * fps, 5),
        "cv": round(robust_cv, 3),
        "consistency_score": consistency_score,
        "duration_sec": round(duration, 2),
        "count": int(len(seg)),
    }


def evaluate_rep_trajectory_form(final_exercise, rep_memory):
    details = rep_memory.get("trajectory_details", [])
    if len(details) < 5:
        return {}, []

    feedback = []
    metrics = {}

    def values(key):
        return np.array([float(item.get(key, 0.0)) for item in details], dtype=float)

    if final_exercise == "Flotare":
        shoulder_y = values("shoulder_y")
        hip_y = values("hip_y")
        body_alignment = values("body_alignment")
        elbow_avg = values("elbow_avg")

        shoulder_rom = float(np.percentile(shoulder_y, 90) - np.percentile(shoulder_y, 10))
        hip_rom = float(np.percentile(hip_y, 90) - np.percentile(hip_y, 10))
        min_elbow = float(np.percentile(elbow_avg, 10))
        alignment_span = float(np.percentile(body_alignment, 90) - np.percentile(body_alignment, 10))

        score_parts = []
        if min_elbow <= 105 and shoulder_rom >= 0.04:
            score_parts.append(100)
            feedback.append("Amplitudinea flotarii este buna pe parcursul repetarii.")
        elif min_elbow <= 120:
            score_parts.append(75)
            feedback.append("Amplitudinea este acceptabila, dar poti cobori putin mai controlat.")
        else:
            score_parts.append(45)
            feedback.append("Repetarea pare prea scurta; coboara mai mult in faza de jos.")

        if alignment_span <= 18:
            score_parts.append(100)
        elif alignment_span <= 30:
            score_parts.append(75)
            feedback.append("Linia corpului variaza putin in timpul repetarii.")
        else:
            score_parts.append(45)
            feedback.append("Alinierea corpului se schimba mult; evita sa rupi miscarea din solduri.")

        trajectory_score = int(np.mean(score_parts))
        metrics.update({
            "trajectory_form_score": trajectory_score,
            "pushup_shoulder_rom": round(shoulder_rom, 4),
            "pushup_hip_rom": round(hip_rom, 4),
            "pushup_min_elbow_angle": round(min_elbow, 2),
        })

    elif final_exercise == "Abdomene":
        shoulder_y = values("shoulder_y")
        hip_y = values("hip_y")
        torso_angle = values("torso_angle")
        neck_angle = values("neck_angle")

        torso_rom = float(np.percentile(torso_angle, 90) - np.percentile(torso_angle, 10))
        shoulder_rom = float(np.percentile(shoulder_y, 90) - np.percentile(shoulder_y, 10))
        hip_rom = float(np.percentile(hip_y, 90) - np.percentile(hip_y, 10))
        neck_bad_ratio = float(np.mean((neck_angle < 65) | (neck_angle > 150)))

        score_parts = []
        if torso_rom >= 35 or shoulder_rom >= 0.12:
            score_parts.append(100)
            feedback.append("Amplitudinea abdomenului este buna pe intreaga repetare.")
        elif torso_rom >= 22 or shoulder_rom >= 0.08:
            score_parts.append(75)
            feedback.append("Amplitudinea este acceptabila, dar ridica trunchiul putin mai mult.")
        else:
            score_parts.append(45)
            feedback.append("Miscarea este prea scurta; cauta o ridicare mai ampla a trunchiului.")

        if hip_rom <= 0.06:
            score_parts.append(100)
            feedback.append("Soldurile raman stabile in timpul repetarii.")
        elif hip_rom <= 0.10:
            score_parts.append(75)
            feedback.append("Soldurile se misca putin; stabilizeaza bazinul.")
        else:
            score_parts.append(45)
            feedback.append("Soldurile se ridica prea mult; incearca sa controlezi miscarea din abdomen.")

        if neck_bad_ratio <= 0.25:
            score_parts.append(100)
        elif neck_bad_ratio <= 0.50:
            score_parts.append(75)
            feedback.append("Gatul isi pierde uneori pozitia neutra.")
        else:
            score_parts.append(45)
            feedback.append("Evita sa tragi din cap; mentine gatul neutru.")

        trajectory_score = int(np.mean(score_parts))
        metrics.update({
            "trajectory_form_score": trajectory_score,
            "situp_torso_rom": round(torso_rom, 2),
            "situp_shoulder_rom": round(shoulder_rom, 4),
            "situp_hip_rom": round(hip_rom, 4),
            "situp_neck_bad_ratio": round(neck_bad_ratio, 3),
        })

    elif final_exercise == "Tractiuni":
        shoulder_y = values("shoulder_y")
        shoulder_x = values("shoulder_x")
        hip_x = values("hip_x")
        elbow_avg = values("elbow_avg")
        left_elbow = values("left_elbow_angle")
        right_elbow = values("right_elbow_angle")

        shoulder_rom = float(np.percentile(shoulder_y, 90) - np.percentile(shoulder_y, 10))
        top_elbow = float(np.percentile(elbow_avg, 10))
        bottom_elbow = float(np.percentile(elbow_avg, 90))
        elbow_rom = bottom_elbow - top_elbow
        swing_span = float(np.percentile(np.abs(shoulder_x - hip_x), 90) - np.percentile(np.abs(shoulder_x - hip_x), 10))
        asymmetry = float(np.percentile(np.abs(left_elbow - right_elbow), 90))

        score_parts = []
        if top_elbow <= 85 and shoulder_rom >= 0.06:
            score_parts.append(100)
            feedback.append("Pozitia de sus este buna, cu tragere clara spre bara.")
        elif top_elbow <= 105:
            score_parts.append(75)
            feedback.append("Mai urca putin pentru o tractiune completa.")
        else:
            score_parts.append(45)
            feedback.append("Nu urci suficient; cauta o amplitudine mai mare.")

        if bottom_elbow >= 145 and elbow_rom >= 35:
            score_parts.append(100)
            feedback.append("Coborarea are extensie buna jos.")
        elif bottom_elbow >= 130:
            score_parts.append(75)
            feedback.append("Coboara putin mai mult pentru extensie completa.")
        else:
            score_parts.append(45)
            feedback.append("Nu intinzi suficient bratele in partea de jos.")

        if swing_span <= 0.05:
            score_parts.append(100)
        elif swing_span <= 0.10:
            score_parts.append(75)
            feedback.append("Exista un mic balans; mentine trunchiul mai controlat.")
        else:
            score_parts.append(45)
            feedback.append("Balansul este mare; evita sa folosesti impulsul.")

        if asymmetry <= 18:
            score_parts.append(100)
        elif asymmetry <= 30:
            score_parts.append(75)
            feedback.append("Bratele trag usor diferit; incearca sa urci simetric.")
        else:
            score_parts.append(45)
            feedback.append("Tragi inegal cu bratele; corecteaza simetria.")

        trajectory_score = int(np.mean(score_parts))
        metrics.update({
            "trajectory_form_score": trajectory_score,
            "pullup_shoulder_rom": round(shoulder_rom, 4),
            "pullup_top_elbow_angle": round(top_elbow, 2),
            "pullup_bottom_elbow_angle": round(bottom_elbow, 2),
            "pullup_elbow_rom": round(elbow_rom, 2),
            "pullup_swing_span": round(swing_span, 4),
            "pullup_arm_asymmetry": round(asymmetry, 2),
        })

    return metrics, feedback


def apply_control_metrics(final_exercise, metrics, feedback, rep_memory, fps=30.0):
    """
    Adaugă scor separat de control al mișcării.

    Nu compară viteza de urcare cu viteza de coborâre. Verifică doar dacă
    viteza este relativ constantă în interiorul fiecărei faze.

    total_score = 85% postură + 15% control, ca feedback-ul de control să fie util,
    dar să nu strice scorul unei execuții corecte.
    """
    posture_score = int(metrics.get("total_score", metrics.get("scor_total", 0)) or 0)

    traj = np.array(rep_memory.get("trajectory", []), dtype=float)
    fps = float(fps or 30.0)
    if fps <= 1:
        fps = 30.0

    down_stats = {"mean_speed": 0.0, "cv": 0.0, "consistency_score": 92, "duration_sec": 0.0, "count": 0}
    up_stats = {"mean_speed": 0.0, "cv": 0.0, "consistency_score": 92, "duration_sec": 0.0, "count": 0}

    if len(traj) >= 8:
        smooth = _smooth_signal(traj)
        total_rom = float(np.max(smooth) - np.min(smooth))

        if total_rom >= 0.012:
            # Pentru genuflexiune/flotare/deadlift/fandare: jos = y maxim.
            # Pentru tracțiuni/abdomene: sus = y minim.
            if final_exercise in ["Tractiuni", "Abdomene", "Biceps Curl", "Lateral Raise"]:
                split = int(np.argmin(smooth))
                up_segment = smooth[:split + 1]
                down_segment = smooth[split:]
            else:
                split = int(np.argmax(smooth))
                down_segment = smooth[:split + 1]
                up_segment = smooth[split:]

            down_stats = _phase_speed_stats(down_segment, fps=fps)
            up_stats = _phase_speed_stats(up_segment, fps=fps)

            # Dacă o fază are prea puține cadre, nu o penalizăm dur.
            available = []
            if down_stats["count"] >= 5:
                available.append(down_stats["consistency_score"])
            if up_stats["count"] >= 5:
                available.append(up_stats["consistency_score"])

            control_score = int(np.mean(available)) if available else 90

            # Feedback de durată: praguri relaxate.
            # Nu comparăm urcarea cu coborârea; fiecare fază este evaluată separat.
            if 0 < down_stats["duration_sec"] < 0.40:
                control_score -= 6
                feedback.append("Coborârea este prea rapidă; încearcă să controlezi mai bine faza descendentă.")
            elif down_stats["duration_sec"] > 4.0:
                control_score -= 4
                feedback.append("Coborârea este foarte lentă; încearcă să păstrezi o mișcare mai fluentă.")

            if 0 < up_stats["duration_sec"] < 0.25:
                control_score -= 5
                feedback.append("Urcarea este foarte explozivă; finalizează repetarea fără smucitură.")
            elif up_stats["duration_sec"] > 3.5:
                control_score -= 4
                feedback.append("Urcarea este foarte lentă; încearcă să menții un ritm mai fluent.")

            # Feedback pentru constanță: praguri mult mai tolerante.
            # Ținem cont că o execuție bună are natural accelerație + frânare.
            if down_stats["count"] >= 7:
                if down_stats["cv"] > 1.15:
                    control_score -= 8
                    feedback.append("Viteza pe coborâre este neuniformă; încearcă să eviți opririle sau accelerările bruște.")
                elif down_stats["cv"] > 0.85:
                    control_score -= 4
                    feedback.append("Coborârea este ușor neuniformă, dar execuția rămâne acceptabilă.")

            if up_stats["count"] >= 7:
                if up_stats["cv"] > 1.30:
                    control_score -= 8
                    feedback.append("Viteza pe urcare este neuniformă; evită smuciturile pe faza pozitivă.")
                elif up_stats["cv"] > 0.95:
                    control_score -= 4
                    feedback.append("Urcarea este ușor neuniformă, dar execuția rămâne acceptabilă.")
        else:
            control_score = 90
    else:
        control_score = 90
        feedback.append("Nu au fost suficiente cadre pentru o estimare precisă a constanței vitezei.")

    # Scor foarte blând: controlul are rol informativ, nu trebuie să anuleze postura bună.
    trajectory_metrics, trajectory_feedback = evaluate_rep_trajectory_form(final_exercise, rep_memory)
    trajectory_score = int(trajectory_metrics.get("trajectory_form_score", posture_score))
    if trajectory_feedback:
        feedback.extend(trajectory_feedback)

    control_score = int(max(55, min(100, control_score)))
    if trajectory_metrics:
        total_score = int(round(
            0.70 * posture_score +
            0.15 * trajectory_score +
            0.15 * control_score
        ))
    else:
        total_score = int(round(0.80 * posture_score + 0.20 * control_score))

    metrics["posture_score"] = posture_score
    metrics["control_score"] = control_score
    metrics.update(trajectory_metrics)
    metrics["total_score"] = total_score
    metrics["tempo_down_sec"] = down_stats["duration_sec"]
    metrics["tempo_up_sec"] = up_stats["duration_sec"]
    metrics["down_speed"] = down_stats["mean_speed"]
    metrics["up_speed"] = up_stats["mean_speed"]
    metrics["down_consistency_score"] = int(down_stats["consistency_score"])
    metrics["up_consistency_score"] = int(up_stats["consistency_score"])
    metrics["down_speed_cv"] = down_stats["cv"]
    metrics["up_speed_cv"] = up_stats["cv"]
    metrics["smoothness_score"] = int(round((down_stats["consistency_score"] + up_stats["consistency_score"]) / 2.0))

    # Păstrăm câmpul vechi pentru compatibilitate, dar NU îl folosim pentru penalizare.
    metrics["speed_ratio_up_down"] = round(float(up_stats["mean_speed"] / down_stats["mean_speed"]), 3) if down_stats["mean_speed"] > 1e-6 else 1.0

    if "scor_total" in metrics:
        metrics["scor_total"] = total_score

    return metrics

def clean_feedback_text(text):
    if not isinstance(text, str):
        return text
    if any(marker in text for marker in ("Ã", "Ä", "È", "Å")):
        try:
            return text.encode("latin1").decode("utf-8")
        except UnicodeError:
            return text
    return text


def clean_feedback_list(feedback):
    return [clean_feedback_text(item) for item in (feedback or [])]


def maybe_draw_analysis_overlay(image_frame, metrics=None):
    if not ANALYSIS_SCREENSHOT_OVERLAY or not metrics:
        return image_frame

    landmarks = metrics.get("landmarks")
    exercise_type = metrics.get("exercise_type")
    if landmarks is None or not exercise_type:
        return image_frame

    try:
        return draw_colored_landmarks(
            image_frame.copy(),
            landmarks,
            metrics.get("trunk_angle") or metrics.get("body_alignment_angle"),
            metrics.get("squat_angle"),
            metrics.get("knee_offset"),
            metrics.get("max_offset"),
            exercise_type=exercise_type,
            date_postura=metrics if exercise_type == "fandare" else None,
        )
    except Exception as exc:
        if DEBUG_ANALYSIS:
            print("analysis overlay failed:", exc)
        return image_frame


def build_rep_payload(rep_id, score, feedback, image_frame, metrics=None):
    image_frame = maybe_draw_analysis_overlay(image_frame, metrics)
    payload = {
        "id": rep_id,
        "score": int(score),
        "feedback": clean_feedback_list(feedback),
        "image": frame_to_b64(image_frame),
    }
    if metrics:
        payload.update({
            "posture_score": int(metrics.get("posture_score", score)),
            "control_score": int(metrics.get("control_score", 100)),
            "total_score": int(metrics.get("total_score", score)),
            "tempo_down_sec": metrics.get("tempo_down_sec", 0.0),
            "tempo_up_sec": metrics.get("tempo_up_sec", 0.0),
            "down_speed": metrics.get("down_speed", 0.0),
            "up_speed": metrics.get("up_speed", 0.0),
            "speed_ratio_up_down": metrics.get("speed_ratio_up_down", 1.0),
            "smoothness_score": metrics.get("smoothness_score", 100),
        })

        # Păstrăm și metricile suplimentare specifice exercițiilor
        # Exemplu: bench_path_score, bench_trajectory_score, bench_elbow_rom.
        for key, value in metrics.items():
            if key in payload or key in ["landmarks", "puncte", "puncte_cheie"]:
                continue
            if isinstance(value, (int, float, str, bool)) or value is None:
                payload[key] = value

    return payload


def _smooth_mountain_signal(values):
    arr = np.array(values, dtype=float)
    if len(arr) < 5:
        return arr

    padded = np.pad(arr, (1, 1), mode="edge")
    med = np.array([np.median(padded[i:i + 3]) for i in range(len(arr))], dtype=float)
    kernel = np.ones(3, dtype=float) / 3.0
    smooth = np.convolve(med, kernel, mode="same")
    smooth[0] = arr[0]
    smooth[-1] = arr[-1]
    return smooth


def _detect_mountain_peaks(signal, peak_threshold, min_prominence=0.0):
    peaks = []
    if len(signal) < 3:
        return peaks

    arr = np.array(signal, dtype=float)
    for i in range(1, len(signal) - 1):
        is_local_peak = (
            arr[i] >= arr[i - 1]
            and arr[i] >= arr[i + 1]
            and (arr[i] > arr[i - 1] or arr[i] > arr[i + 1])
        )
        if not is_local_peak or arr[i] < peak_threshold:
            continue

        left = max(0, i - 4)
        right = min(len(arr), i + 5)
        left_min = float(np.min(arr[left:i + 1]))
        right_min = float(np.min(arr[i:right]))
        prominence = float(arr[i] - max(left_min, right_min))
        if prominence >= min_prominence:
            peaks.append(i)

    # Plateaus can hide a local maximum. For each above-threshold island, keep
    # the strongest frame as a candidate too.
    in_segment = False
    best_idx = 0
    best_value = 0.0
    for i, value in enumerate(arr):
        if value >= peak_threshold:
            if not in_segment:
                in_segment = True
                best_idx = i
                best_value = float(value)
            elif value > best_value:
                best_idx = i
                best_value = float(value)
        elif in_segment:
            peaks.append(best_idx)
            in_segment = False

    if in_segment:
        peaks.append(best_idx)

    peaks = sorted(set(peaks))
    return peaks


def _filter_peaks_by_distance(peaks, signal, min_distance):
    filtered = []
    for peak_idx in peaks:
        if not filtered:
            filtered.append(peak_idx)
            continue

        last = filtered[-1]
        if peak_idx - last < min_distance:
            if signal[peak_idx] > signal[last]:
                filtered[-1] = peak_idx
        else:
            filtered.append(peak_idx)
    return filtered


def _mountain_peaks_for_side(raw_signal, threshold_factor):
    signal = _smooth_mountain_signal(raw_signal)
    if len(signal) < 3:
        return [], signal, {
            "p20": 0.0,
            "p80": 0.0,
            "amplitude": 0.0,
            "threshold": 0.0,
            "raw_peaks": 0,
        }

    p20 = float(np.percentile(signal, 20))
    p80 = float(np.percentile(signal, 80))
    amplitude = float(p80 - p20)
    threshold = p20 + threshold_factor * amplitude
    min_prominence = max(0.003, amplitude * 0.08)

    if amplitude < 0.008:
        return [], signal, {
            "p20": p20,
            "p80": p80,
            "amplitude": amplitude,
            "threshold": threshold,
            "raw_peaks": 0,
        }

    raw_peaks = _detect_mountain_peaks(signal, threshold, min_prominence)
    peaks = _filter_peaks_by_distance(raw_peaks, signal, MOUNTAIN_MIN_PEAK_DISTANCE)
    return peaks, signal, {
        "p20": p20,
        "p80": p80,
        "amplitude": amplitude,
        "threshold": threshold,
        "raw_peaks": len(raw_peaks),
    }


def _mountain_windowed_peaks_for_side(raw_signal, threshold_factor, window_size=72, overlap=12):
    values = list(raw_signal)
    if len(values) < 3:
        return []
    if len(values) <= window_size:
        peaks, _signal, _meta = _mountain_peaks_for_side(values, threshold_factor)
        return peaks

    all_peaks = set()
    step = max(12, window_size - overlap)
    start = 0
    while start < len(values):
        end = min(len(values), start + window_size)
        chunk = values[start:end]
        if len(chunk) >= 3:
            chunk_peaks, chunk_signal, _meta = _mountain_peaks_for_side(chunk, threshold_factor)
            for peak_idx in chunk_peaks:
                global_idx = start + peak_idx
                # Evitam varfurile lipite de marginea ferestrei, unde vecinii
                # reali pot fi in afara chunk-ului. Prima si ultima fereastra
                # au voie sa foloseasca marginea video-ului.
                near_left_edge = peak_idx <= 1 and start > 0
                near_right_edge = peak_idx >= len(chunk_signal) - 2 and end < len(values)
                if not near_left_edge and not near_right_edge:
                    all_peaks.add(global_idx)
        if end == len(values):
            break
        start += step

    smooth_full = _smooth_mountain_signal(values)
    return _filter_peaks_by_distance(sorted(all_peaks), smooth_full, MOUNTAIN_MIN_PEAK_DISTANCE)


def _merge_mountain_side_peaks(left_peaks, right_peaks, left_signal, right_signal):
    events = []
    for peak_idx in left_peaks:
        events.append((peak_idx, "left", float(left_signal[peak_idx])))
    for peak_idx in right_peaks:
        events.append((peak_idx, "right", float(right_signal[peak_idx])))

    events.sort(key=lambda item: item[0])
    filtered = []
    for event in events:
        if not filtered:
            filtered.append(event)
            continue

        last = filtered[-1]
        if event[0] == last[0] and event[1] != last[1]:
            if event[2] > last[2]:
                filtered[-1] = event
        elif event[1] == last[1] and event[0] - last[0] < MOUNTAIN_MIN_PEAK_DISTANCE:
            if event[2] > last[2]:
                filtered[-1] = event
        else:
            filtered.append(event)

    return filtered


def _append_mountain_fallback(rep_memory, reps_data, rep_id, message):
    signal = rep_memory.get("mountain_signal", [])
    frames = rep_memory.get("mountain_frames", [])
    lms_values = rep_memory.get("mountain_lms", [])

    if signal and frames and lms_values:
        best_idx = int(np.argmax(np.array(signal, dtype=float)))
        frame = frames[best_idx]
        lms = lms_values[best_idx]
    else:
        frame = rep_memory.get("mountain_best_frame")
        lms = rep_memory.get("mountain_best_lms")

    if frame is None or lms is None:
        return rep_id

    _, metrics, feedback = evaluate_mountain_climber_form(frame, lms)
    feedback = list(feedback)
    feedback.append(message)
    score = int(metrics.get("total_score", 0))
    reps_data.append(build_rep_payload(rep_id, score, feedback, frame, metrics))
    return rep_id + 1


def finalize_mountain_climber_reps(rep_memory, reps_data, rep_id):
    raw_signal = rep_memory.get("mountain_signal", [])
    left_raw = rep_memory.get("mountain_left_signal", [])
    right_raw = rep_memory.get("mountain_right_signal", [])
    frames = rep_memory.get("mountain_frames", [])
    lms_values = rep_memory.get("mountain_lms", [])
    start_count = len(reps_data)

    if not raw_signal or not frames or not lms_values:
        return _append_mountain_fallback(
            rep_memory,
            reps_data,
            rep_id,
            "Nu au fost detectate suficiente cadre valide, dar am evaluat cel mai relevant cadru al exercitiului."
        )

    if len(left_raw) != len(raw_signal) or len(right_raw) != len(raw_signal):
        left_raw = raw_signal
        right_raw = [0.0 for _ in raw_signal]

    left_peaks, left_signal, left_meta = _mountain_peaks_for_side(left_raw, 0.15)
    right_peaks, right_signal, right_meta = _mountain_peaks_for_side(right_raw, 0.15)
    left_window_peaks = _mountain_windowed_peaks_for_side(left_raw, 0.15)
    right_window_peaks = _mountain_windowed_peaks_for_side(right_raw, 0.15)
    left_peaks = _filter_peaks_by_distance(
        sorted(set(left_peaks) | set(left_window_peaks)),
        left_signal,
        MOUNTAIN_MIN_PEAK_DISTANCE,
    )
    right_peaks = _filter_peaks_by_distance(
        sorted(set(right_peaks) | set(right_window_peaks)),
        right_signal,
        MOUNTAIN_MIN_PEAK_DISTANCE,
    )
    events = _merge_mountain_side_peaks(left_peaks, right_peaks, left_signal, right_signal)

    relaxed_left_peaks, relaxed_left_signal, relaxed_left_meta = _mountain_peaks_for_side(left_raw, 0.08)
    relaxed_right_peaks, relaxed_right_signal, relaxed_right_meta = _mountain_peaks_for_side(right_raw, 0.08)
    relaxed_left_window_peaks = _mountain_windowed_peaks_for_side(left_raw, 0.08)
    relaxed_right_window_peaks = _mountain_windowed_peaks_for_side(right_raw, 0.08)
    relaxed_left_peaks = _filter_peaks_by_distance(
        sorted(set(relaxed_left_peaks) | set(relaxed_left_window_peaks)),
        relaxed_left_signal,
        MOUNTAIN_MIN_PEAK_DISTANCE,
    )
    relaxed_right_peaks = _filter_peaks_by_distance(
        sorted(set(relaxed_right_peaks) | set(relaxed_right_window_peaks)),
        relaxed_right_signal,
        MOUNTAIN_MIN_PEAK_DISTANCE,
    )
    relaxed_events = _merge_mountain_side_peaks(
        relaxed_left_peaks,
        relaxed_right_peaks,
        relaxed_left_signal,
        relaxed_right_signal,
    )

    # Daca numarul initial este mic fata de lungimea semnalului, pragul a fost
    # probabil prea sus pentru unghiul camerei. Relaxam fara sa eliminam filtrul
    # de distanta, ca sa nu revenim la supra-numarare.
    low_count_limit = max(15, len(raw_signal) / 50)
    if len(relaxed_events) > len(events) and len(events) < low_count_limit:
        left_peaks = relaxed_left_peaks
        right_peaks = relaxed_right_peaks
        left_signal = relaxed_left_signal
        right_signal = relaxed_right_signal
        left_meta = relaxed_left_meta
        right_meta = relaxed_right_meta
        events = relaxed_events

    amplitude = max(float(left_meta["amplitude"]), float(right_meta["amplitude"]))
    if amplitude < 0.008:
        if DEBUG_MOUNTAIN:
            print({
                "mountain_signal_len": len(raw_signal),
                "left_amplitude": left_meta["amplitude"],
                "right_amplitude": right_meta["amplitude"],
                "amplitude": amplitude,
                "left_threshold": left_meta["threshold"],
                "right_threshold": right_meta["threshold"],
                "raw_peaks": 0,
                "filtered_peaks": 0,
                "peak_indices": [],
            })
        return _append_mountain_fallback(
            rep_memory,
            reps_data,
            rep_id,
            "Semnalul miscarii a fost prea mic pentru repetari complete; am evaluat cel mai relevant cadru."
        )

    if DEBUG_MOUNTAIN:
        print({
            "mountain_signal_len": len(raw_signal),
            "left_amplitude": left_meta["amplitude"],
            "right_amplitude": right_meta["amplitude"],
            "amplitude": amplitude,
            "left_threshold": left_meta["threshold"],
            "right_threshold": right_meta["threshold"],
            "left_raw_peaks": left_meta["raw_peaks"],
            "right_raw_peaks": right_meta["raw_peaks"],
            "left_peaks": len(left_peaks),
            "right_peaks": len(right_peaks),
            "filtered_peaks": len(events),
            "peak_indices": [event[0] for event in events[:20]],
        })

    if not events:
        return _append_mountain_fallback(
            rep_memory,
            reps_data,
            rep_id,
            "Nu au fost detectate varfuri clare ale miscarii, dar am evaluat cel mai relevant cadru."
        )

    used = rep_memory.setdefault("mountain_rep_frames_used", set())
    for peak_idx, side, _value in events:
        if peak_idx in used or peak_idx >= len(frames) or peak_idx >= len(lms_values):
            continue
        used.add(peak_idx)

        frame = frames[peak_idx]
        lms = lms_values[peak_idx]
        _, metrics, feedback = evaluate_mountain_climber_form(frame, lms)
        metrics["peak_side"] = side
        metrics["peak_index"] = int(peak_idx)
        score = int(metrics.get("total_score", 0))
        reps_data.append(build_rep_payload(rep_id, score, feedback, frame, metrics))
        rep_id += 1

    if len(reps_data) == start_count:
        return _append_mountain_fallback(
            rep_memory,
            reps_data,
            rep_id,
            "Nu au fost detectate varfuri clare ale miscarii, dar am evaluat cel mai relevant cadru."
        )

    return rep_id


def complete_mountain_climber_live_peak(rep_memory):
    signal = np.array(rep_memory.get("mountain_signal", []), dtype=float)
    left_raw = rep_memory.get("mountain_left_signal", [])
    right_raw = rep_memory.get("mountain_right_signal", [])
    frames = rep_memory.get("mountain_frames", [])
    lms_values = rep_memory.get("mountain_lms", [])
    if len(signal) < 5 or len(frames) != len(signal) or len(lms_values) != len(signal):
        return None

    if len(left_raw) != len(signal) or len(right_raw) != len(signal):
        return None

    lookback = 90
    offset = max(0, len(signal) - lookback)
    left_slice = left_raw[offset:]
    right_slice = right_raw[offset:]

    left_peaks, left_signal, _left_meta = _mountain_peaks_for_side(left_slice, 0.15)
    right_peaks, right_signal, _right_meta = _mountain_peaks_for_side(right_slice, 0.15)
    left_peaks = [offset + peak_idx for peak_idx in left_peaks]
    right_peaks = [offset + peak_idx for peak_idx in right_peaks]
    events = _merge_mountain_side_peaks(
        left_peaks,
        right_peaks,
        _smooth_mountain_signal(left_raw),
        _smooth_mountain_signal(right_raw),
    )

    if not events:
        return None

    last_peak = int(rep_memory.get("mountain_last_rep_frame_idx", -999))
    used = rep_memory.setdefault("mountain_rep_frames_used", set())
    for peak_idx, _side, _value in events:
        # In live mode confirmam doar peak-uri care au deja cel putin un cadru
        # dupa ele; altfel am numara miscarea inainte sa stim ca a coborat.
        if peak_idx > len(signal) - 2:
            continue
        if peak_idx - last_peak < MOUNTAIN_MIN_PEAK_DISTANCE or peak_idx in used:
            continue

        used.add(peak_idx)
        rep_memory["mountain_last_rep_frame_idx"] = peak_idx
        return frames[peak_idx], lms_values[peak_idx]

    return None


def finalize_partial_rep(final_exercise, rep_memory, reps_data, rep_id, fps=30.0):
    chosen_frame = rep_memory.get("bottom_frame")
    chosen_lms = rep_memory.get("bottom_lms")
    if final_exercise == "Mountain Climbers":
        best_frame = rep_memory.get("mountain_best_frame")
        best_lms = rep_memory.get("mountain_best_lms")
        if best_frame is not None and best_lms is not None:
            chosen_frame = best_frame
            chosen_lms = best_lms

    if chosen_frame is None or chosen_lms is None:
        return rep_id

    if final_exercise == "Flotare":
        _, m, fb = evaluate_pushup_form(chosen_frame, chosen_lms)
    elif final_exercise == "Genuflexiune":
        _, m, fb = evaluate_form(chosen_frame, chosen_lms)
    elif final_exercise == "Deadlift":
        _, m, fb = evaluate_deadlift_form(chosen_frame, chosen_lms)
    elif final_exercise == "Fandare":
        _, m, fb = evalueaza_forma_fandare(chosen_frame, chosen_lms)
    elif final_exercise == "Bench Press":
        _, m, fb = evaluate_bench_press_form(chosen_frame, chosen_lms)
        m = apply_bench_trajectory_metrics(m, fb, rep_memory)
    elif final_exercise == "Biceps Curl":
        _, m, fb = evaluate_biceps_curl_form(chosen_frame, chosen_lms)
    elif final_exercise == "Mountain Climbers":
        _, m, fb = evaluate_mountain_climber_form(chosen_frame, chosen_lms)
    elif final_exercise == "Lateral Raise":
        _, m, fb = evaluate_lateral_raise_form(chosen_frame, chosen_lms)
    else:
        return rep_id

    if final_exercise not in ["Bench Press", "Mountain Climbers"]:
        m = apply_control_metrics(final_exercise, m, fb, rep_memory, fps=fps)
    sc = int(m.get("total_score", 0))

    if sc > 0:
        reps_data.append(build_rep_payload(rep_id, sc, fb, chosen_frame, m))
        rep_id += 1

    return rep_id

# --- CORE LOGIC ---
@app.post("/analyze/process")
async def process(exercise: str = Form("Auto"), file: UploadFile = File(...)):
    raw_path = ""
    suffix = os.path.splitext(file.filename or "")[1] or ".mp4"
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            raw_path = tmp.name
            shutil.copyfileobj(file.file, tmp)

        return run_video_analysis(raw_path, exercise)
    finally:
        if raw_path and os.path.exists(raw_path):
            try:
                os.remove(raw_path)
            except OSError:
                pass


@app.post("/analyze/start")
async def start_analysis(
    background_tasks: BackgroundTasks,
    exercise: str = Form("Auto"),
    file: UploadFile = File(...)
):
    job_id = str(uuid.uuid4())
    suffix = os.path.splitext(file.filename or "")[1] or ".mp4"

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        raw_path = tmp.name
        shutil.copyfileobj(file.file, tmp)

    analysis_jobs[job_id] = {
        "status": "queued",
        "progress": 0,
        "result": None,
        "error": None,
    }

    background_tasks.add_task(_run_analysis_job, job_id, raw_path, exercise)

    return {"job_id": job_id, "status": "queued"}


@app.get("/analyze/status/{job_id}")
def analysis_status(job_id: str):
    job = analysis_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job-ul nu exista.")
    response = {
        "status": job["status"],
        "progress": job["progress"],
    }
    if job["status"] == "done":
        response["result"] = job["result"]
    if job["status"] == "error":
        response["error"] = job["error"]
    return response


def _run_analysis_job(job_id: str, raw_path: str, exercise: str):
    job = analysis_jobs[job_id]

    def set_progress(percent):
        job["progress"] = int(max(0, min(100, percent)))

    try:
        job["status"] = "processing"
        set_progress(1)
        result = run_video_analysis(raw_path, exercise, progress_callback=set_progress)
        job["result"] = result
        job["status"] = "done"
        set_progress(100)
    except Exception as exc:
        job["status"] = "error"
        job["error"] = str(exc)
        set_progress(100)
    finally:
        if raw_path and os.path.exists(raw_path):
            try:
                os.remove(raw_path)
            except OSError:
                pass


def run_video_analysis(raw_path: str, exercise: str, progress_callback=None):
    def report(percent):
        if progress_callback:
            progress_callback(percent)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    proc = f"proc_{ts}.webm"
    proc_path = os.path.join(PROCESSED_DIR, proc) if SAVE_PROCESSED_VIDEO else ""

    detected_exercise = None
    final_exercise = exercise
    report(5)

    if (exercise or "").strip().lower() in ["auto", ""]:
        detected_exercise = detect_exercise(raw_path)
        final_exercise = normalize_exercise_name(detected_exercise)
        report(20)
    else:
        final_exercise = normalize_exercise_name(exercise)
        report(20)

    valid = {
        "Flotare",
        "Genuflexiune",
        "Deadlift",
        "Fandare",
        "Tractiuni",
        "Abdomene",
        "Bench Press",
        "Biceps Curl",
        "Mountain Climbers",
        "Lateral Raise",
        "Plank",
    }
    if final_exercise not in valid:
        final_exercise = "Necunoscut"

    if final_exercise == "Necunoscut":
        report(100)
        return {
            "avg_score": 0,
            "feedback": ["Exercițiul nu a putut fi detectat automat. Selectează manual exercițiul."],
            "reps": [],
            "raw_path": "",
            "processed_path": "",
            "processed_video_url": "",
            "final_exercise": final_exercise,
            "detected_exercise": detected_exercise,
        }

    cap = cv2.VideoCapture(raw_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    if fps <= 1:
        fps = 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)

    source_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    source_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    process_size = _scaled_video_size(source_width, source_height)

    out = None
    if SAVE_PROCESSED_VIDEO:
        out = cv2.VideoWriter(
            proc_path,
            cv2.VideoWriter_fourcc(*'vp80'),
            30.0,
            process_size
        )

    det = PoseDetector()
    state, reps_data = "idle", []
    rep_memory = reset_rep_memory()
    rep_id = 1
    motion_window = max(8, min(30, int(fps * 0.25)))
    buf = deque(maxlen=motion_window)
    min_v, f_in, l_in = None, None, None

    plank_scores = []
    plank_feedback_all = []
    plank_best_frame = None
    plank_best_metrics = None
    plank_best_feedback = None
    plank_best_score = -1
    plank_worst_frame = None
    plank_worst_metrics = None
    plank_worst_feedback = None
    plank_worst_score = 101
    plank_worst_frame_index = 0
    plank_valid_frames = 0
    plank_keyframes = []
    plank_last_snapshot_metrics = None
    plank_last_snapshot_score = None
    plank_last_snapshot_frame = -10_000
    processed_frame_idx = 0
    while True:
        ret, frm = cap.read()
        if not ret:
            break
        processed_frame_idx += 1
        frm = _resize_frame_for_processing(frm, process_size)

        res = det.detect_pose(frm)
        lms = det.get_landmarks(res)
        drw = frm.copy()

        if lms:
            done, sc, fb, img, rep_metrics = False, 0, [], None, None

            if final_exercise == "Plank":
                _, m, fb = evaluate_plank_form(frm.copy(), lms)
                sc = int(m.get("total_score", 0))

                plank_scores.append(sc)
                plank_feedback_all.extend(fb)
                plank_valid_frames += 1

                if sc > plank_best_score:
                    plank_best_score = sc
                    plank_best_frame = frm.copy()
                    plank_best_metrics = m
                    plank_best_feedback = fb

                if sc < plank_worst_score:
                    plank_worst_score = sc
                    plank_worst_frame = frm.copy()
                    plank_worst_metrics = m
                    plank_worst_feedback = fb
                    plank_worst_frame_index = processed_frame_idx

                snapshot_reason = _plank_snapshot_reason(
                    m,
                    sc,
                    plank_last_snapshot_metrics,
                    plank_last_snapshot_score
                )
                snapshot_cooldown = max(1, int(fps * 0.75))
                can_add_snapshot = (
                    snapshot_reason is not None and
                    len(plank_keyframes) < 8 and
                    (
                        not plank_keyframes or
                        processed_frame_idx - plank_last_snapshot_frame >= snapshot_cooldown
                    )
                )

                if can_add_snapshot:
                    snapshot_metrics = dict(m)
                    snapshot_metrics["analysis_type"] = "plank_frame"
                    snapshot_metrics["label"] = "Cadru analizat"
                    snapshot_metrics["reason"] = snapshot_reason
                    snapshot_metrics["frame_index"] = processed_frame_idx
                    snapshot_metrics["time_sec"] = round(processed_frame_idx / fps, 2)
                    snapshot_metrics["score_at_frame"] = sc

                    snapshot_feedback = [snapshot_reason]
                    for item in fb:
                        if item not in snapshot_feedback:
                            snapshot_feedback.append(item)

                    plank_keyframes.append({
                        "score": sc,
                        "feedback": snapshot_feedback[:6],
                        "frame": frm.copy(),
                        "metrics": snapshot_metrics,
                    })
                    plank_last_snapshot_metrics = m
                    plank_last_snapshot_score = sc
                    plank_last_snapshot_frame = processed_frame_idx

                drw = draw_colored_landmarks(
                    frm.copy(),
                    lms,
                    exercise_type="plank"
                )
            elif final_exercise == "Flotare":
                rep_state = pushup_rep_state(lms)
                if state in ["start", "bottom"] or rep_state["start_ok"] or rep_state["bottom_ok"]:
                    record_rep_trajectory(final_exercise, lms, rep_memory)
                new_state = update_rep_fsm(state, rep_state, frm, lms, rep_memory)

                if new_state == "complete":
                    chosen_frame = rep_memory["bottom_frame"]
                    chosen_lms = rep_memory["bottom_lms"]

                    if chosen_frame is not None and chosen_lms is not None:
                        _, m, fb = evaluate_pushup_form(chosen_frame, chosen_lms)
                        rep_metrics = apply_control_metrics(final_exercise, m, fb, rep_memory, fps=fps)
                        sc = rep_metrics.get("total_score", 0)
                        img = chosen_frame
                        done = True

                    state = "idle"
                    rep_memory = reset_rep_memory()
                else:
                    state = new_state

                if rep_state["bottom_ok"]:
                    drw = draw_colored_landmarks(
                        frm.copy(),
                        lms,
                        rep_state.get("body_alignment", 0),
                        0,
                        0,
                        0,
                        "flotare"
                    )

            elif final_exercise == "Genuflexiune":
                rep_state = squat_rep_state(lms)
                if state in ["start", "bottom"] or rep_state["start_ok"] or rep_state["bottom_ok"]:
                    record_rep_trajectory(final_exercise, lms, rep_memory)
                new_state = update_rep_fsm(state, rep_state, frm, lms, rep_memory)

                if new_state == "complete":
                    chosen_frame = rep_memory["bottom_frame"]
                    chosen_lms = rep_memory["bottom_lms"]

                    if chosen_frame is not None and chosen_lms is not None:
                        _, m, fb = evaluate_form(chosen_frame, chosen_lms)
                        rep_metrics = apply_control_metrics(final_exercise, m, fb, rep_memory, fps=fps)
                        sc = rep_metrics.get("total_score", 0)
                        img = chosen_frame
                        done = True

                    state = "idle"
                    rep_memory = reset_rep_memory()
                else:
                    state = new_state

                if rep_state["bottom_ok"]:
                    _, m_tmp, _ = evaluate_form(frm.copy(), lms)
                    drw = draw_colored_landmarks(
                        frm.copy(),
                        lms,
                        m_tmp.get("trunk_angle"),
                        m_tmp.get("squat_angle"),
                        m_tmp.get("knee_offset"),
                        m_tmp.get("max_offset"),
                        "genoflexiune"
                    )

            elif final_exercise == "Deadlift":
                rep_state = deadlift_rep_state(lms)
                if state in ["start", "bottom"] or rep_state["start_ok"] or rep_state["bottom_ok"]:
                    record_rep_trajectory(final_exercise, lms, rep_memory)
                new_state = update_rep_fsm(state, rep_state, frm, lms, rep_memory)

                if new_state == "complete":
                    chosen_frame = rep_memory["bottom_frame"]
                    chosen_lms = rep_memory["bottom_lms"]

                    if chosen_frame is not None and chosen_lms is not None:
                        _, m, fb = evaluate_deadlift_form(chosen_frame, chosen_lms)
                        rep_metrics = apply_control_metrics(final_exercise, m, fb, rep_memory, fps=fps)
                        sc = rep_metrics.get("total_score", 0)
                        img = chosen_frame
                        done = True

                    state = "idle"
                    rep_memory = reset_rep_memory()
                else:
                    state = new_state

                if rep_state["bottom_ok"]:
                    _, m_tmp, _ = evaluate_deadlift_form(frm.copy(), lms)
                    drw = draw_colored_landmarks(
                        frm.copy(),
                        lms,
                        m_tmp.get("trunk_angle"),
                        0,
                        m_tmp.get("knee_offset"),
                        m_tmp.get("max_offset"),
                        "deadlift"
                    )

            elif final_exercise == "Fandare":
                rep_state = lunge_rep_state(lms)
                if state in ["start", "bottom"] or rep_state["start_ok"] or rep_state["bottom_ok"]:
                    record_rep_trajectory(final_exercise, lms, rep_memory)
                new_state = update_rep_fsm(state, rep_state, frm, lms, rep_memory)

                if new_state == "complete":
                    chosen_frame = rep_memory["bottom_frame"]
                    chosen_lms = rep_memory["bottom_lms"]

                    if chosen_frame is not None and chosen_lms is not None:
                        _, m, fb = evalueaza_forma_fandare(chosen_frame, chosen_lms)
                        rep_metrics = apply_control_metrics(final_exercise, m, fb, rep_memory, fps=fps)
                        sc = rep_metrics.get("total_score", 0)
                        img = chosen_frame
                        done = True

                    state = "idle"
                    rep_memory = reset_rep_memory()
                else:
                    state = new_state

                if rep_state["bottom_ok"]:
                    _, m_tmp, _ = evalueaza_forma_fandare(frm.copy(), lms)
                    drw = draw_colored_landmarks(
                        frm.copy(),
                        lms,
                        exercise_type="fandare",
                        date_postura=m_tmp
                    )

            elif final_exercise == "Bench Press":
                rep_state = bench_press_rep_state(lms)

                if state in ["start", "bottom"] or rep_state["start_ok"] or rep_state["bottom_ok"]:
                    record_rep_trajectory(final_exercise, lms, rep_memory)
                    record_bench_trajectory(lms, rep_memory)

                new_state = update_rep_fsm(state, rep_state, frm, lms, rep_memory)

                if new_state == "complete":
                    chosen_frame = rep_memory["bottom_frame"]
                    chosen_lms = rep_memory["bottom_lms"]

                    if chosen_frame is not None and chosen_lms is not None:
                        _, m, fb = evaluate_bench_press_form(chosen_frame, chosen_lms)
                        rep_metrics = apply_bench_trajectory_metrics(m, fb, rep_memory)

                        sc = rep_metrics.get("total_score", 0)
                        img = chosen_frame
                        done = True

                    state = "idle"
                    rep_memory = reset_rep_memory()
                else:
                    state = new_state

                if rep_state["bottom_ok"]:
                    drw = draw_colored_landmarks(
                        frm.copy(),
                        lms,
                        exercise_type="bench_press"
                    )
            elif final_exercise == "Biceps Curl":
                rep_state = biceps_curl_rep_state(lms)
                if state in ["start", "bottom"] or rep_state["start_ok"] or rep_state["bottom_ok"]:
                    record_rep_trajectory(final_exercise, lms, rep_memory)
                new_state = update_rep_fsm(state, rep_state, frm, lms, rep_memory)

                if new_state == "complete":
                    chosen_frame = rep_memory["bottom_frame"]
                    chosen_lms = rep_memory["bottom_lms"]
                    if chosen_frame is not None and chosen_lms is not None:
                        _, m, fb = evaluate_biceps_curl_form(chosen_frame, chosen_lms)
                        rep_metrics = apply_control_metrics(final_exercise, m, fb, rep_memory, fps=fps)
                        sc = rep_metrics.get("total_score", 0)
                        img = chosen_frame
                        done = True
                    state = "idle"
                    rep_memory = reset_rep_memory()
                else:
                    state = new_state

                if rep_state["bottom_ok"]:
                    drw = draw_colored_landmarks(frm.copy(), lms, exercise_type="biceps_curl")

            elif final_exercise == "Mountain Climbers":
                rep_state = mountain_climber_rep_state(lms)
                record_mountain_climber_signal(rep_state, frm, lms, rep_memory, frame_idx=processed_frame_idx)
                drw = draw_colored_landmarks(frm.copy(), lms, exercise_type="mountain_climbers")

            elif final_exercise == "Lateral Raise":
                rep_state = lateral_raise_rep_state(lms)
                if state in ["start", "bottom"] or rep_state["start_ok"] or rep_state["bottom_ok"]:
                    record_rep_trajectory(final_exercise, lms, rep_memory)
                new_state = update_rep_fsm(state, rep_state, frm, lms, rep_memory)

                if new_state == "complete":
                    chosen_frame = rep_memory["bottom_frame"]
                    chosen_lms = rep_memory["bottom_lms"]
                    if chosen_frame is not None and chosen_lms is not None:
                        _, m, fb = evaluate_lateral_raise_form(chosen_frame, chosen_lms)
                        rep_metrics = apply_control_metrics(final_exercise, m, fb, rep_memory, fps=fps)
                        sc = rep_metrics.get("total_score", 0)
                        img = chosen_frame
                        done = True
                    state = "idle"
                    rep_memory = reset_rep_memory()
                else:
                    state = new_state

                if rep_state["bottom_ok"]:
                    drw = draw_colored_landmarks(frm.copy(), lms, exercise_type="lateral_raise")
            elif final_exercise == "Abdomene":
                y = lms[0].y
                buf.append(y)
                tr = (buf[-1] - buf[0]) if len(buf) == buf.maxlen else 0

                if state == "idle" and tr < -0.025:
                    state, min_v, f_in, l_in = "down", y, frm.copy(), lms
                    rep_memory = reset_rep_memory()
                    record_rep_trajectory(final_exercise, lms, rep_memory)
                elif state == "down":
                    record_rep_trajectory(final_exercise, lms, rep_memory)
                    if min_v is None or y < min_v:
                        min_v, f_in, l_in = y, frm.copy(), lms
                    if tr > 0.025:
                        _, m, fb = evaluate_situp_form(f_in, l_in)
                        rep_metrics = apply_control_metrics(final_exercise, m, fb, rep_memory, fps=fps)
                        sc = rep_metrics.get("total_score", 0)
                        img = f_in
                        done = True
                        state = "idle"
                        min_v = None

            elif final_exercise == "Tractiuni":
                y = (lms[11].y + lms[12].y) / 2.0
                buf.append(y)
                tr = (buf[-1] - buf[0]) if len(buf) == buf.maxlen else 0

                if state == "idle" and tr < -0.025:
                    state, min_v, f_in, l_in = "down", y, frm.copy(), lms
                    rep_memory = reset_rep_memory()
                    record_rep_trajectory(final_exercise, lms, rep_memory)
                elif state == "down":
                    record_rep_trajectory(final_exercise, lms, rep_memory)
                    if min_v is None or y < min_v:
                        min_v, f_in, l_in = y, frm.copy(), lms
                    if tr > 0.025:
                        _, m, fb = evaluate_pullup_form(f_in, l_in)
                        rep_metrics = apply_control_metrics(final_exercise, m, fb, rep_memory, fps=fps)
                        sc = rep_metrics.get("total_score", 0)
                        img = f_in
                        done = True
                        state = "idle"
                        min_v = None

            if done:
                reps_data.append(build_rep_payload(rep_id, sc, fb, img, rep_metrics))
                rep_id += 1
        if out is not None:
            out.write(drw)
        if total_frames > 0:
            report(20 + (processed_frame_idx / total_frames) * 75)

    if final_exercise == "Mountain Climbers":
        rep_id = finalize_mountain_climber_reps(rep_memory, reps_data, rep_id)

    if final_exercise == "Plank" and plank_valid_frames > 0 and plank_best_frame is not None:
        avg_plank_score = int(sum(plank_scores) / len(plank_scores))
        has_worst_snapshot = any(
            item["metrics"].get("frame_index") == plank_worst_frame_index
            for item in plank_keyframes
        )

        if plank_worst_frame is not None and not has_worst_snapshot:
            worst_metrics = dict(plank_worst_metrics or {})
            worst_reason = _plank_position_message(worst_metrics.get("hip_position", "neutral"))
            if plank_worst_score >= 85:
                worst_reason = "Cel mai slab cadru gasit ramane acceptabil."

            worst_metrics["analysis_type"] = "plank_frame"
            worst_metrics["label"] = "Cadru analizat"
            worst_metrics["reason"] = worst_reason
            worst_metrics["frame_index"] = plank_worst_frame_index
            worst_metrics["time_sec"] = round(plank_worst_frame_index / fps, 2)
            worst_metrics["score_at_frame"] = plank_worst_score

            worst_feedback = [worst_reason]
            for item in plank_worst_feedback or []:
                if item not in worst_feedback:
                    worst_feedback.append(item)

            plank_keyframes.append({
                "score": plank_worst_score,
                "feedback": worst_feedback[:6],
                "frame": plank_worst_frame,
                "metrics": worst_metrics,
            })

        plank_keyframes.sort(key=lambda item: item["metrics"].get("frame_index", 0))

        feedback_counts = Counter(plank_feedback_all)
        session_feedback = [item for item, _ in feedback_counts.most_common(5)]

        for snapshot in plank_keyframes:
            metrics = dict(snapshot["metrics"])
            metrics["session_total_score"] = avg_plank_score
            metrics["static_hold_frames"] = plank_valid_frames
            metrics["best_frame_score"] = plank_best_score
            metrics["worst_frame_score"] = plank_worst_score
            metrics["min_score"] = min(plank_scores)
            metrics["max_score"] = max(plank_scores)
            metrics["avg_score_over_frames"] = avg_plank_score

            feedback = list(snapshot["feedback"])
            for item in session_feedback:
                if item not in feedback:
                    feedback.append(item)

            reps_data.append(
                build_rep_payload(
                    rep_id,
                    snapshot["score"],
                    feedback[:6],
                    snapshot["frame"],
                    metrics
                )
            )
            rep_id += 1
    # fallback pentru videoclipuri cu o singură repetare sau final tăiat
    if final_exercise not in ["Mountain Climbers", "Plank"] and state in ["bottom", "start"]:
        rep_id = finalize_partial_rep(final_exercise, rep_memory, reps_data, rep_id, fps=fps)

    cap.release()
    if out is not None:
        out.release()
    report(98)

    if final_exercise == "Plank" and plank_scores:
        avg = int(sum(plank_scores) / len(plank_scores))
    else:
        avg = int(sum(r['score'] for r in reps_data)/len(reps_data)) if reps_data else 0
    all_feedback = [
        clean_feedback_text(item)
        for sublist in [r["feedback"] for r in reps_data]
        for item in sublist
    ]
    fb_all = [item for item, _ in Counter(all_feedback).most_common(5)]

    result = {
        "avg_score": avg,
        "feedback": fb_all,
        "reps": reps_data,
        "raw_path": "",
        "processed_path": "",
        "processed_video_url": "",
        "final_exercise": final_exercise,
        "detected_exercise": detected_exercise
    }
    if DEBUG_ANALYSIS:
        print({
            "detected_exercise": detected_exercise,
            "final_exercise": final_exercise,
            "reps_count": len(reps_data),
            "avg_score": avg,
        })
    report(100)
    return result

def frame_to_b64(frame):
    _, b = cv2.imencode('.jpg', frame); return "data:image/jpeg;base64," + base64.b64encode(b).decode('utf-8')

@app.websocket("/ws/live/{ex}")
async def ws_live(websocket: WebSocket, ex: str):
    await websocket.accept()
    ex = normalize_exercise_name(ex)

    det = PoseDetector()

    state = "idle"
    buf = deque(maxlen=8)
    min_v, f_in, l_in = None, None, None
    rep_id = 1
    rep_memory = reset_live_rep_memory()

    # Pentru Plank: trimitem o evaluare periodică, nu repetări.
    plank_frame_count = 0
    plank_last_sent = 0
    mountain_frame_idx = 0

    valid_live = {
        "Flotare",
        "Genuflexiune",
        "Deadlift",
        "Fandare",
        "Abdomene",
        "Tractiuni",
        "Bench Press",
        "Biceps Curl",
        "Mountain Climbers",
        "Lateral Raise",
        "Plank",
    }

    if ex not in valid_live:
        ex = "Genuflexiune"

    try:
        while True:
            d = await websocket.receive_text()

            frm = cv2.imdecode(
                np.frombuffer(base64.b64decode(d.split(",")[1]), np.uint8),
                cv2.IMREAD_COLOR
            )
            mountain_frame_idx += 1

            res = det.detect_pose(frm)
            lms = det.get_landmarks(res)

            disp = frm.copy()

            if lms:
                done, sc, fb, img, rep_metrics = False, 0, [], None, None

                # =========================
                # PLANK
                # =========================
                if ex == "Plank":
                    _, m, fb = evaluate_plank_form(frm.copy(), lms)
                    sc = int(m.get("total_score", 0))

                    disp = draw_colored_landmarks(
                        frm.copy(),
                        lms,
                        exercise_type="plank"
                    )

                    cv2.putText(
                        disp,
                        f"Scor Plank: {sc}%",
                        (10, 60),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.8,
                        (255, 255, 255),
                        2,
                        cv2.LINE_AA
                    )

                    plank_frame_count += 1

                    # Trimitem o evaluare la aproximativ fiecare 30 cadre,
                    # ca să existe ceva salvabil în repsList.
                    if plank_frame_count - plank_last_sent >= 30:
                        plank_last_sent = plank_frame_count

                        rep_payload = build_rep_payload(
                            rep_id,
                            sc,
                            fb,
                            disp,
                            {
                                **m,
                                "static_hold_frames": plank_frame_count,
                                "total_score": sc,
                            }
                        )

                        await websocket.send_json({
                            "type": "REP_COMPLETE",
                            "rep_data": rep_payload
                        })

                        rep_id += 1

                # =========================
                # FLOTARE
                # =========================
                elif ex == "Flotare":
                    rep_state = pushup_rep_state(lms)

                    if state in ["start", "bottom"] or rep_state["start_ok"] or rep_state["bottom_ok"]:
                        record_rep_trajectory(ex, lms, rep_memory)

                    new_state = update_live_rep_fsm(state, rep_state, frm, lms, rep_memory)

                    if new_state == "complete":
                        chosen_frame = rep_memory.get("bottom_frame")
                        chosen_lms = rep_memory.get("bottom_lms")

                        if chosen_frame is not None and chosen_lms is not None:
                            _, m, fb = evaluate_pushup_form(chosen_frame, chosen_lms)
                            rep_metrics = apply_control_metrics(ex, m, fb, rep_memory)
                            sc = rep_metrics.get("total_score", 0)
                            img = chosen_frame
                            done = True

                        state = "idle"
                        rep_memory = reset_live_rep_memory()
                    else:
                        state = new_state

                    disp = draw_colored_landmarks(
                        frm.copy(),
                        lms,
                        rep_state.get("body_alignment", 0),
                        0,
                        0,
                        0,
                        "flotare"
                    )

                # =========================
                # GENOFLEXIUNE
                # =========================
                elif ex == "Genuflexiune":
                    rep_state = squat_rep_state(lms)

                    if state in ["start", "bottom"] or rep_state["start_ok"] or rep_state["bottom_ok"]:
                        record_rep_trajectory(ex, lms, rep_memory)

                    new_state = update_live_rep_fsm(state, rep_state, frm, lms, rep_memory)

                    if new_state == "complete":
                        chosen_frame = rep_memory.get("bottom_frame")
                        chosen_lms = rep_memory.get("bottom_lms")

                        if chosen_frame is not None and chosen_lms is not None:
                            _, m, fb = evaluate_form(chosen_frame, chosen_lms)
                            rep_metrics = apply_control_metrics(ex, m, fb, rep_memory)
                            sc = rep_metrics.get("total_score", 0)
                            img = chosen_frame
                            done = True

                        state = "idle"
                        rep_memory = reset_live_rep_memory()
                    else:
                        state = new_state

                    _, m_tmp, _ = evaluate_form(frm.copy(), lms)
                    disp = draw_colored_landmarks(
                        frm.copy(),
                        lms,
                        m_tmp.get("trunk_angle"),
                        m_tmp.get("squat_angle"),
                        m_tmp.get("knee_offset"),
                        m_tmp.get("max_offset"),
                        "genoflexiune"
                    )

                # =========================
                # DEADLIFT
                # =========================
                elif ex == "Deadlift":
                    rep_state = deadlift_rep_state(lms)

                    if state in ["start", "bottom"] or rep_state["start_ok"] or rep_state["bottom_ok"]:
                        record_rep_trajectory(ex, lms, rep_memory)

                    new_state = update_live_rep_fsm(state, rep_state, frm, lms, rep_memory)

                    if new_state == "complete":
                        chosen_frame = rep_memory.get("bottom_frame")
                        chosen_lms = rep_memory.get("bottom_lms")

                        if chosen_frame is not None and chosen_lms is not None:
                            _, m, fb = evaluate_deadlift_form(chosen_frame, chosen_lms)
                            rep_metrics = apply_control_metrics(ex, m, fb, rep_memory)
                            sc = rep_metrics.get("total_score", 0)
                            img = chosen_frame
                            done = True

                        state = "idle"
                        rep_memory = reset_live_rep_memory()
                    else:
                        state = new_state

                    _, m_tmp, _ = evaluate_deadlift_form(frm.copy(), lms)
                    disp = draw_colored_landmarks(
                        frm.copy(),
                        lms,
                        m_tmp.get("trunk_angle"),
                        m_tmp.get("squat_angle", 0),
                        m_tmp.get("knee_offset"),
                        m_tmp.get("max_offset"),
                        "deadlift"
                    )

                # =========================
                # FANDARE
                # =========================
                elif ex == "Fandare":
                    rep_state = lunge_rep_state(lms)

                    if state in ["start", "bottom"] or rep_state["start_ok"] or rep_state["bottom_ok"]:
                        record_rep_trajectory(ex, lms, rep_memory)

                    new_state = update_live_rep_fsm(state, rep_state, frm, lms, rep_memory)

                    if new_state == "complete":
                        chosen_frame = rep_memory.get("bottom_frame")
                        chosen_lms = rep_memory.get("bottom_lms")

                        if chosen_frame is not None and chosen_lms is not None:
                            _, m, fb = evalueaza_forma_fandare(chosen_frame, chosen_lms)
                            rep_metrics = apply_control_metrics(ex, m, fb, rep_memory)
                            sc = rep_metrics.get("total_score", 0)
                            img = chosen_frame
                            done = True

                        state = "idle"
                        rep_memory = reset_live_rep_memory()
                    else:
                        state = new_state

                    _, m_tmp, _ = evalueaza_forma_fandare(frm.copy(), lms)
                    disp = draw_colored_landmarks(
                        frm.copy(),
                        lms,
                        exercise_type="fandare",
                        date_postura=m_tmp
                    )

                # =========================
                # BENCH PRESS
                # =========================
                elif ex == "Bench Press":
                    rep_state = bench_press_rep_state(lms)

                    if state in ["start", "bottom"] or rep_state["start_ok"] or rep_state["bottom_ok"]:
                        record_rep_trajectory(ex, lms, rep_memory)
                        record_bench_trajectory(lms, rep_memory)

                    new_state = update_live_rep_fsm(state, rep_state, frm, lms, rep_memory)

                    if new_state == "complete":
                        chosen_frame = rep_memory.get("bottom_frame")
                        chosen_lms = rep_memory.get("bottom_lms")

                        if chosen_frame is not None and chosen_lms is not None:
                            _, m, fb = evaluate_bench_press_form(chosen_frame, chosen_lms)
                            rep_metrics = apply_bench_trajectory_metrics(m, fb, rep_memory)
                            sc = rep_metrics.get("total_score", 0)
                            img = chosen_frame
                            done = True

                        state = "idle"
                        rep_memory = reset_live_rep_memory()
                    else:
                        state = new_state

                    disp = draw_colored_landmarks(
                        frm.copy(),
                        lms,
                        exercise_type="bench_press"
                    )

                elif ex == "Biceps Curl":
                    rep_state = biceps_curl_rep_state(lms)
                    if state in ["start", "bottom"] or rep_state["start_ok"] or rep_state["bottom_ok"]:
                        record_rep_trajectory(ex, lms, rep_memory)
                    new_state = update_live_rep_fsm(state, rep_state, frm, lms, rep_memory)

                    if new_state == "complete":
                        chosen_frame = rep_memory.get("bottom_frame")
                        chosen_lms = rep_memory.get("bottom_lms")
                        if chosen_frame is not None and chosen_lms is not None:
                            _, m, fb = evaluate_biceps_curl_form(chosen_frame, chosen_lms)
                            rep_metrics = apply_control_metrics(ex, m, fb, rep_memory)
                            sc = rep_metrics.get("total_score", 0)
                            img = chosen_frame
                            done = True
                        state = "idle"
                        rep_memory = reset_live_rep_memory()
                    else:
                        state = new_state

                    disp = draw_colored_landmarks(frm.copy(), lms, exercise_type="biceps_curl")

                elif ex == "Mountain Climbers":
                    rep_state = mountain_climber_rep_state(lms)
                    record_mountain_climber_signal(rep_state, frm, lms, rep_memory, frame_idx=mountain_frame_idx)
                    completed = complete_mountain_climber_live_peak(rep_memory)

                    if completed is not None:
                        chosen_frame, chosen_lms = completed
                        _, m, fb = evaluate_mountain_climber_form(chosen_frame, chosen_lms)
                        rep_metrics = m
                        sc = rep_metrics.get("total_score", 0)
                        img = chosen_frame
                        done = True

                    disp = draw_colored_landmarks(frm.copy(), lms, exercise_type="mountain_climbers")

                elif ex == "Lateral Raise":
                    rep_state = lateral_raise_rep_state(lms)
                    if state in ["start", "bottom"] or rep_state["start_ok"] or rep_state["bottom_ok"]:
                        record_rep_trajectory(ex, lms, rep_memory)
                    new_state = update_live_rep_fsm(state, rep_state, frm, lms, rep_memory)

                    if new_state == "complete":
                        chosen_frame = rep_memory.get("bottom_frame")
                        chosen_lms = rep_memory.get("bottom_lms")
                        if chosen_frame is not None and chosen_lms is not None:
                            _, m, fb = evaluate_lateral_raise_form(chosen_frame, chosen_lms)
                            rep_metrics = apply_control_metrics(ex, m, fb, rep_memory)
                            sc = rep_metrics.get("total_score", 0)
                            img = chosen_frame
                            done = True
                        state = "idle"
                        rep_memory = reset_live_rep_memory()
                    else:
                        state = new_state

                    disp = draw_colored_landmarks(frm.copy(), lms, exercise_type="lateral_raise")

                # =========================
                # ABDOMENE
                # =========================
                elif ex == "Abdomene":
                    y = lms[0].y
                    buf.append(y)
                    tr = (buf[-1] - buf[0]) if len(buf) == buf.maxlen else 0

                    if state == "idle" and tr < -0.025:
                        state = "up"
                        min_v = y
                        f_in, l_in = frm.copy(), lms
                        rep_memory = reset_live_rep_memory()
                        record_rep_trajectory(ex, lms, rep_memory)

                    elif state == "up":
                        record_rep_trajectory(ex, lms, rep_memory)

                        if min_v is None or y < min_v:
                            min_v, f_in, l_in = y, frm.copy(), lms

                        if tr > 0.025:
                            _, m, fb = evaluate_situp_form(f_in, l_in)
                            rep_metrics = apply_control_metrics(ex, m, fb, rep_memory)
                            sc = rep_metrics.get("total_score", 0)
                            img = f_in
                            done = True
                            state = "idle"
                            min_v = None

                    disp = draw_colored_landmarks(
                        frm.copy(),
                        lms,
                        exercise_type="abdomene"
                    )

                # =========================
                # TRACTIUNI
                # =========================
                elif ex == "Tractiuni":
                    y = (lms[11].y + lms[12].y) / 2.0
                    buf.append(y)
                    tr = (buf[-1] - buf[0]) if len(buf) == buf.maxlen else 0

                    if state == "idle" and tr < -0.025:
                        state = "up"
                        min_v = y
                        f_in, l_in = frm.copy(), lms
                        rep_memory = reset_live_rep_memory()
                        record_rep_trajectory(ex, lms, rep_memory)

                    elif state == "up":
                        record_rep_trajectory(ex, lms, rep_memory)

                        if min_v is None or y < min_v:
                            min_v, f_in, l_in = y, frm.copy(), lms

                        if tr > 0.025:
                            _, m, fb = evaluate_pullup_form(f_in, l_in)
                            rep_metrics = apply_control_metrics(ex, m, fb, rep_memory)
                            sc = rep_metrics.get("total_score", 0)
                            img = f_in
                            done = True
                            state = "idle"
                            min_v = None

                    disp = draw_colored_landmarks(
                        frm.copy(),
                        lms,
                        exercise_type="tractiuni"
                    )

                if done:
                    rep_payload = build_rep_payload(rep_id, sc, fb, img, rep_metrics)

                    await websocket.send_json({
                        "type": "REP_COMPLETE",
                        "rep_data": rep_payload
                    })

                    rep_id += 1

            else:
                if res.pose_landmarks:
                    det.mp_drawing.draw_landmarks(
                        disp,
                        res.pose_landmarks,
                        det.mp_pose.POSE_CONNECTIONS
                    )

            await websocket.send_json({
                "type": "FRAME_UPDATE",
                "image": frame_to_b64(disp).split(",")[1]
            })

    except WebSocketDisconnect:
        return
    except Exception as e:
        try:
            await websocket.send_json({"type": "ERROR", "message": str(e)})
        except Exception:
            return
@app.get("/history")
def hist(current=Depends(get_current_user)):
    local_user = current["local_user"]

    conn = get_db_connection()
    try:
        res = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM workouts WHERE user_id=? ORDER BY id DESC",
                (local_user["id"],)
            )
        ]
        for r in res:
            r["reps"] = json.loads(r["reps_json"]) if r["reps_json"] else []
            r["feedback"] = json.loads(r["feedback_json"]) if r["feedback_json"] else []
        return res
    except Exception:
        return []
    finally:
        conn.close()

@app.get("/stats")
def st(current=Depends(get_current_user)):
    local_user = current["local_user"]

    conn = get_db_connection()
    res = [
        dict(r)
        for r in conn.execute(
            "SELECT * FROM workouts WHERE user_id=? ORDER BY created_at ASC",
            (local_user["id"],)
        )
    ]
    conn.close()
    return res

@app.delete("/history/{id}")
def delete_w(id: int, current=Depends(get_current_user)):
    local_user = current["local_user"]

    conn = get_db_connection()
    conn.execute("DELETE FROM workouts WHERE id=? AND user_id=?", (id, local_user["id"]))
    conn.commit()
    conn.close()
    return {"status": "deleted"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
