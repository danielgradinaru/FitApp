# feedback_rules.py
import math
from math import atan, degrees, hypot


def calculate_angle(a, b, c):
    a = [a[0], a[1]]
    b = [b[0], b[1]]
    c = [c[0], c[1]]

    ab = [a[0] - b[0], a[1] - b[1]]
    cb = [c[0] - b[0], c[1] - b[1]]

    dot_product = (ab[0] * cb[0] + ab[1] * cb[1])
    magnitude_ab = math.sqrt(ab[0] ** 2 + ab[1] ** 2)
    magnitude_cb = math.sqrt(cb[0] ** 2 + cb[1] ** 2)

    if magnitude_ab * magnitude_cb == 0:
        return 0

    value = dot_product / (magnitude_ab * magnitude_cb)
    value = max(-1.0, min(1.0, value))

    angle = math.acos(value)
    return math.degrees(angle)


# =========================================
# DEADLIFT
# =========================================

def calculate_trunk_angle(left_hip, left_shoulder):
    """
    Calculeaza unghiul trunchiului fata de verticala.
    """
    delta_x = left_shoulder[0] - left_hip[0]
    delta_y = left_shoulder[1] - left_hip[1]

    if delta_y == 0:
        return 90
    return math.degrees(math.atan(abs(delta_x / delta_y)))


def check_knee_position(left_hip, left_knee, left_ankle):
    """
    Verifica pozitia genunchiului fata de varful piciorului si paralelismul sold-genunchi.
    """
    knee_forward_distance = left_knee[0] - left_ankle[0]
    leg_length = math.sqrt((left_ankle[0] - left_hip[0])**2 + (left_ankle[1] - left_hip[1])**2)

    max_forward_offset = leg_length * 0.08

    delta_x = left_knee[0] - left_hip[0]
    delta_y = left_knee[1] - left_hip[1]

    if delta_x == 0:
        angle_to_horizontal = 90
    else:
        angle_to_horizontal = math.degrees(math.atan2(delta_y, delta_x))

    return knee_forward_distance, max_forward_offset, angle_to_horizontal


def calculate_squat_angle(left_hip, left_knee, left_ankle):
    """
    Calculeaza unghiul dintre sold, genunchi si glezna.
    """
    return calculate_angle(left_hip, left_knee, left_ankle)


def evaluate_deadlift_trunk(trunk_angle):
    if 0 <= trunk_angle <= 10:
        return 100
    elif 10 < trunk_angle <= 15:
        return 70
    else:
        return 20


def evaluate_deadlift_knee_offset(knee_offset):
    if abs(knee_offset) <= 0.07:
        return 100
    elif abs(knee_offset) <= 0.09:
        return 70
    else:
        return 20


def evaluate_deadlift_squat_angle(squat_angle):
    # La deadlift, genunchiul este flexat moderat, nu ca la genuflexiune.
    if 105 <= squat_angle <= 155:
        return 100
    elif 90 <= squat_angle < 105 or 155 < squat_angle <= 170:
        return 70
    else:
        return 20


def evaluate_deadlift_spine_neutrality(hip, mid_back, shoulder):
    angle = calculate_angle(hip, mid_back, shoulder)
    if 170 <= angle <= 190:
        return 100, "Spatele este neutru (drept)."
    elif 160 <= angle < 170 or 190 < angle <= 200:
        return 70, "Spatele este usor curbat."
    else:
        return 20, "Spatele este stramb, indreapta spatele!"


def generate_deadlift_feedback(trunk_angle, knee_offset, squat_angle):
    feedback = []

    if 0 <= trunk_angle <= 10:
        feedback.append("Trunchiul este drept, foarte bine!")
    elif 10 < trunk_angle <= 15:
        feedback.append("Spatele este usor aplecat, atentie!")
    else:
        feedback.append("Spatele este prea curbat, indreapta trunchiul!")

    if abs(knee_offset) <= 0.05:
        feedback.append("Pozitia genunchilor este corecta.")
    elif abs(knee_offset) <= 0.07:
        feedback.append("Pozitia genunchilor este acceptabila, dar ai grija.")
    else:
        feedback.append("Genunchii avanseaza prea mult fata de varfuri!")

    if 105 <= squat_angle <= 155:
        feedback.append("Flexia genunchilor este potrivită pentru deadlift.")
    elif 90 <= squat_angle < 105:
        feedback.append("Îndoi genunchii cam mult; încearcă să duci mișcarea mai mult din șold.")
    elif 155 < squat_angle <= 170:
        feedback.append("Genunchii sunt aproape întinși; asigură-te că nu transformi mișcarea într-un stiff-leg deadlift.")
    else:
        feedback.append("Unghiul genunchilor nu este potrivit pentru deadlift; ajustează poziția.")

    return feedback

# =========================================
# FLOTARE
# =========================================

def calculate_body_alignment(left_shoulder, left_hip, left_ankle):
    return calculate_angle(left_shoulder, left_hip, left_ankle)


def calculate_elbow_angle(left_shoulder, left_elbow, left_wrist):
    return calculate_angle(left_shoulder, left_elbow, left_wrist)


def evaluate_pushup_alignment(body_alignment_angle):
    if 169 <= body_alignment_angle <= 190:
        return 100
    elif 155 <= body_alignment_angle < 169 or 190 < body_alignment_angle <= 205:
        return 70
    else:
        return 20


def evaluate_pushup_depth(chest_distance_to_ground):
    if chest_distance_to_ground <= 0.14:
        return 100
    elif chest_distance_to_ground <= 0.19:
        return 70
    else:
        return 20


def evaluate_pushup_elbow_angle(elbow_angle):
    if 30 <= elbow_angle <= 60:
        return 100
    elif 20 <= elbow_angle < 30 or 60 < elbow_angle <= 70:
        return 70
    else:
        return 20


def evaluate_pushup_hip_stability(hip_movement_variation):
    if hip_movement_variation <= 0.05:
        return 100
    elif hip_movement_variation <= 0.08:
        return 70
    else:
        return 20


def generate_pushup_feedback(body_alignment_angle, chest_distance_to_ground, elbow_angle, hip_movement_variation):
    feedback = []

    if 169 <= body_alignment_angle <= 190:
        feedback.append("Alinierea corpului este corecta.")
    elif 155 <= body_alignment_angle < 169:
        feedback.append("Corp aproape drept, ridica bazinul!")
    elif 190 < body_alignment_angle <= 205:
        feedback.append("Corp aproape drept, coboara bazinul!")
    else:
        feedback.append("Corp stramb, ajusteaza postura (spatele trebuie drept)!")

    if chest_distance_to_ground <= 0.14:
        feedback.append("Adancimea flotarii este corecta.")
    elif chest_distance_to_ground <= 0.19:
        feedback.append("Coboara putin mai mult pentru flotare completa.")
    else:
        feedback.append("Coboara mult mai jos, flotarea este prea superficiala!")

    if 30 <= elbow_angle <= 60:
        feedback.append("Pozitia coatelor este corecta.")
    elif 20 <= elbow_angle < 30 or 60 < elbow_angle <= 70:
        feedback.append("Coatele sunt acceptabile, dar atentie la deschidere!")
    else:
        feedback.append("Coatele sunt prost pozitionate, riscuri pentru umeri!")

    if hip_movement_variation <= 0.05:
        feedback.append("Stabilitatea soldului este foarte buna.")
    elif hip_movement_variation <= 0.08:
        feedback.append("Soldurile sunt acceptabile, dar pot fi mai stabile.")
    else:
        feedback.append("Soldurile oscileaza prea mult, controleaza trunchiul!")

    return feedback


def generate_plank_feedback(body_alignment, hip_deviation, pelvis_tilt, shoulder_elbow_offset, hip_position="neutral"):
    feedback = []

    if 165 <= body_alignment <= 195:
        feedback.append("Corpul este bine aliniat in pozitia de plank.")
    elif hip_position == "high":
        feedback.append("Bazinul este prea sus; coboara usor soldurile pana corpul revine pe linie.")
    elif hip_position == "low":
        feedback.append("Bazinul este prea jos; incordeaza abdomenul si fesierii ca sa ridici soldurile.")
    else:
        feedback.append("Alinierea corpului poate fi mai stabila; mentine umerii, bazinul si gleznele pe aceeasi linie.")

    if hip_deviation <= 0.06:
        feedback.append("Pozitia soldurilor este stabila.")
    elif hip_deviation <= 0.10:
        feedback.append("Soldurile sunt usor deplasate; mentine abdomenul mai activ.")
    elif hip_position == "high":
        feedback.append("Bazinul urca peste linia corpului.")
    elif hip_position == "low":
        feedback.append("Bazinul coboara sub linia corpului.")
    else:
        feedback.append("Soldurile sunt prea sus sau prea jos fata de linia corpului.")

    if pelvis_tilt <= 0.045:
        feedback.append("Bazinul este drept.")
    elif pelvis_tilt <= 0.075:
        feedback.append("Exista o usoara inclinare a bazinului.")
    else:
        feedback.append("Bazinul este inclinat; distribuie greutatea egal pe ambele parti.")

    if shoulder_elbow_offset <= 0.08:
        feedback.append("Coatele sunt bine pozitionate sub umeri.")
    elif shoulder_elbow_offset <= 0.13:
        feedback.append("Coatele sunt usor deplasate; incearca sa le aliniezi mai bine sub umeri.")
    else:
        feedback.append("Coatele sunt prea departe de linia umerilor; ajusteaza pozitia bratelor.")

    return feedback


# =========================================
# GENOFLEXIUNE
# =========================================

def feedback_trunk_inclination(trunk_angle):
    if 10 <= trunk_angle <= 15:
        return "Inclinatia trunchiului este corecta."
    elif 15 < trunk_angle <= 20:
        return "Trunchiul este usor inclinat, este acceptabil."
    elif trunk_angle > 20:
        return "Atentie: trunchiul este prea inclinat in fata!"
    else:
        return "Atentie: trunchiul este prea vertical, apleaca-te usor in fata!"


def check_squat_depth(parallel_angle):
    if parallel_angle < -15:
        return "Ai coborat prea mult. Ridica-te usor."
    elif parallel_angle > 15:
        return "Nu ai coborat suficient. Coboara mai jos."
    else:
        return "Adancimea genoflexiunii este corecta."


def check_butt_wink(left_hip, left_knee, left_ankle):
    angle = calculate_angle(left_hip, left_knee, left_ankle)
    if angle < 60:
        return "Atentie: curbura lombara excesiva (butt wink)!"
    else:
        return "Nu exista curbura lombara semnificativa."


def check_pelvic_tilt(left_hip, right_hip):
    delta_x = right_hip[0] - left_hip[0]
    delta_y = right_hip[1] - left_hip[1]

    if delta_x == 0:
        angle_to_x = 90
    else:
        angle_to_x = math.degrees(math.atan(abs(delta_y / delta_x)))

    if angle_to_x <= 10:
        return "Bazinul este drept."
    else:
        return "Atentie: bazinul este inclinat!"


def evaluate_trunk(trunk_angle):
    # trunk_angle = grade fata de verticala (0 = vertical, 45 = inclinat mult)
    # Genuflexiunile adanci cer normal 25-40 grade; intervalul acceptabil e larg.
    if 5 <= trunk_angle <= 40:
        return 100
    elif trunk_angle <= 50:
        return 75
    elif trunk_angle < 5:
        return 85
    else:
        return 30


def evaluate_squat_depth(squat_angle):
    # squat_angle = unghiul hip-knee-ankle (0-180 grade).
    # Paralel = ~90-100 grade; sub paralel = mai mic.
    if squat_angle <= 100:
        return 100
    elif squat_angle <= 120:
        return 70
    else:
        return 20


def evaluate_knee_position(knee_offset, max_offset):
    if abs(knee_offset) <= 0.07:
        return 100
    elif abs(knee_offset) <= 0.09:
        return 70
    else:
        return 20


def evaluate_butt_wink(left_hip, left_knee, left_ankle):
    angle = calculate_angle(left_hip, left_knee, left_ankle)
    if angle >= 55:
        return 100
    elif angle >= 40:
        return 80
    else:
        return 20


def evaluate_pelvic_tilt(left_hip, right_hip):
    # Folosim diferenta verticala (Y) a soldurilor, care functioneaza
    # atat din unghi frontal cat si lateral, spre deosebire de abordarea
    # bazata pe unghi unghiular care depinde de perspectiva camerei.
    hip_y_diff = abs(right_hip[1] - left_hip[1])
    if hip_y_diff <= 0.03:
        return 100
    elif hip_y_diff <= 0.06:
        return 80
    else:
        return 40


def generate_feedback(trunk_angle, squat_angle, knee_offset, max_offset, left_hip, left_knee, left_ankle, right_hip):
    feedback = []

    if trunk_angle > 50:
        feedback.append("Atentie: trunchiul este prea inclinat in fata!")
    elif trunk_angle > 40:
        feedback.append("Trunchiul este usor prea inclinat, incearca sa te ridici putin.")
    elif trunk_angle >= 5:
        feedback.append("Inclinatia trunchiului este corecta.")
    else:
        feedback.append("Trunchiul este aproape vertical.")

    if squat_angle <= 100:
        feedback.append("Adancimea genuflexiunii este corecta.")
    elif squat_angle <= 120:
        feedback.append("Adancimea este acceptabila, poti cobori usor mai mult.")
    else:
        feedback.append("Nu ai coborat suficient. Coboara mai jos.")

    if abs(knee_offset) <= 0.07:
        feedback.append("Pozitia genunchiului fata de varfuri este corecta.")
    elif abs(knee_offset) <= 0.09:
        feedback.append("Pozitia genunchiului este acceptabila, dar ai grija.")
    else:
        feedback.append("Genunchiul avanseaza prea mult fata de varfuri.")

    angle = calculate_angle(left_hip, left_knee, left_ankle)
    if angle >= 55:
        feedback.append("Curba lombara este normala.")
    elif angle >= 40:
        feedback.append("Curbura lombara este acceptabila, dar atentie.")
    else:
        feedback.append("Atentie: curbura lombara excesiva (butt wink)!")

    hip_y_diff = abs(right_hip[1] - left_hip[1])
    if hip_y_diff <= 0.03:
        feedback.append("Bazinul este bine aliniat.")
    elif hip_y_diff <= 0.06:
        feedback.append("Bazinul este usor inclinat.")
    else:
        feedback.append("Atentie: bazinul este inclinat!")

    return feedback


def knee_offset_relative(hip, knee, ankle):
    tibia_len = math.sqrt((ankle[0]-knee[0])**2 + (ankle[1]-knee[1])**2) or 1e-6
    return (knee[0] - ankle[0]) / tibia_len


def symmetry_score(left_value, right_value, tol=0.05):
    delta = abs(left_value - right_value)
    if delta <= tol:
        return 100
    elif delta <= 2 * tol:
        return 70
    else:
        return 20


# =========================================
# ABDOMENE
# =========================================

def evaluate_situp_amplitude(amplitude):
    if amplitude >= 35:
        return 100
    elif amplitude >= 25:
        return 70
    else:
        return 20


def evaluate_situp_neck(neck_angle):
    if 145 <= neck_angle <= 190:
        return 100
    elif 130 <= neck_angle < 145 or 190 < neck_angle <= 205:
        return 70
    else:
        return 20


def evaluate_situp_hip_stability(hip_variation):
    if hip_variation <= 0.04:
        return 100
    elif hip_variation <= 0.07:
        return 70
    else:
        return 20


def evaluate_situp_symmetry(shoulder_delta):
    if shoulder_delta <= 0.03:
        return 100
    elif shoulder_delta <= 0.06:
        return 70
    else:
        return 20


def generate_situp_feedback(amplitude, neck_angle, hip_variation, shoulder_delta):
    feedback = []

    if amplitude >= 35:
        feedback.append("Amplitudinea abdomenului este foarte buna.")
    elif amplitude >= 25:
        feedback.append("Amplitudinea este acceptabila, mai ridica usor trunchiul.")
    else:
        feedback.append("Miscarea este prea scurta, ridica mai mult trunchiul.")

    if 145 <= neck_angle <= 190:
        feedback.append("Pozitia gatului este corecta.")
    elif 130 <= neck_angle < 145:
        feedback.append("Gatul este usor prea flexat, nu trage din cap.")
    elif 190 < neck_angle <= 205:
        feedback.append("Capul este prea lasat pe spate, mentine gatul neutru.")
    else:
        feedback.append("Pozitia gatului nu este corecta, privirea trebuie sa ramana neutra.")

    if hip_variation <= 0.04:
        feedback.append("Soldurile sunt stabile pe parcursul miscarii.")
    elif hip_variation <= 0.07:
        feedback.append("Exista o mica miscare in solduri, incearca sa stabilizezi mai bine bazinul.")
    else:
        feedback.append("Soldurile se misca prea mult, controleaza mai bine trunchiul.")

    if shoulder_delta <= 0.03:
        feedback.append("Executia este simetrica stanga-dreapta.")
    elif shoulder_delta <= 0.06:
        feedback.append("Exista o mica asimetrie in ridicare.")
    else:
        feedback.append("Ridicarea este asimetrica, evita rasucirea trunchiului.")

    return feedback


# =========================================
# TRACTIUNI
# =========================================

def evaluate_pullup_top_position(avg_elbow_angle_top):
    if avg_elbow_angle_top <= 90:
        return 100
    elif avg_elbow_angle_top <= 110:
        return 70
    else:
        return 20


def evaluate_pullup_bottom_position(avg_elbow_angle_bottom):
    if avg_elbow_angle_bottom >= 160:
        return 100
    elif avg_elbow_angle_bottom >= 145:
        return 70
    else:
        return 20


def evaluate_pullup_body_alignment(body_alignment_angle):
    if 165 <= body_alignment_angle <= 195:
        return 100
    elif 150 <= body_alignment_angle < 165 or 195 < body_alignment_angle <= 210:
        return 70
    else:
        return 20


def evaluate_pullup_symmetry(left_elbow_angle, right_elbow_angle):
    diff = abs(left_elbow_angle - right_elbow_angle)
    if diff <= 10:
        return 100
    elif diff <= 20:
        return 70
    else:
        return 20


def evaluate_pullup_swing(swing_amount):
    if swing_amount <= 0.03:
        return 100
    elif swing_amount <= 0.06:
        return 70
    else:
        return 20


def generate_pullup_feedback(
    avg_elbow_angle_top,
    avg_elbow_angle_bottom,
    body_alignment_angle,
    left_elbow_angle,
    right_elbow_angle,
    swing_amount
):
    feedback = []

    if avg_elbow_angle_top <= 90:
        feedback.append("Pozitia de sus este foarte buna.")
    elif avg_elbow_angle_top <= 110:
        feedback.append("Mai urca putin pentru o tractiune completa.")
    else:
        feedback.append("Nu urci suficient, incearca o amplitudine mai mare.")

    if avg_elbow_angle_bottom >= 160:
        feedback.append("Extensia de jos este completa.")
    elif avg_elbow_angle_bottom >= 145:
        feedback.append("Coboara putin mai mult pentru extensie completa.")
    else:
        feedback.append("Nu cobori suficient, intinde mai bine bratele jos.")

    if 165 <= body_alignment_angle <= 195:
        feedback.append("Trunchiul este bine controlat.")
    elif 150 <= body_alignment_angle < 165 or 195 < body_alignment_angle <= 210:
        feedback.append("Corpul este relativ stabil, dar poti controla mai bine miscarea.")
    else:
        feedback.append("Balans prea mare al trunchiului, evita impulsul.")

    diff = abs(left_elbow_angle - right_elbow_angle)
    if diff <= 10:
        feedback.append("Bratele trag simetric.")
    elif diff <= 20:
        feedback.append("Exista o usoara asimetrie intre brate.")
    else:
        feedback.append("Tragi inegal cu bratele, corecteaza simetria.")

    if swing_amount <= 0.03:
        feedback.append("Balansul corpului este minim.")
    elif swing_amount <= 0.06:
        feedback.append("Exista un mic balans, incearca mai mult control.")
    else:
        feedback.append("Balans prea mare, evita kipping-ul.")

    return feedback


# =========================================
# FANDARE
# =========================================

def identifica_picioare_fandare(puncte):
    """
    Identifică care picior este în față, comparând unghiurile genunchilor.
    Returnează tuple cu indecșii:
    (sold_fata, genunchi_fata, glezna_fata, sold_spate, genunchi_spate, glezna_spate, umar_st, umar_dr).
    """
    L_HIP, L_KNEE, L_ANK = 23, 25, 27
    R_HIP, R_KNEE, R_ANK = 24, 26, 28
    L_SH, R_SH = 11, 12

    def unghi_picior(idx_hip, idx_knee, idx_ank):
        return calculate_angle(
            (puncte[idx_hip].x, puncte[idx_hip].y),
            (puncte[idx_knee].x, puncte[idx_knee].y),
            (puncte[idx_ank].x, puncte[idx_ank].y)
        )

    unghi_st = unghi_picior(L_HIP, L_KNEE, L_ANK)
    unghi_dr = unghi_picior(R_HIP, R_KNEE, R_ANK)

    stang_in_fata = unghi_st < unghi_dr

    if stang_in_fata:
        return (L_HIP, L_KNEE, L_ANK, R_HIP, R_KNEE, R_ANK, L_SH, R_SH)
    else:
        return (R_HIP, R_KNEE, R_ANK, L_HIP, L_KNEE, L_ANK, L_SH, R_SH)


def analizeaza_postura_fandare(puncte):
    fH, fK, fA, bH, bK, bA, L_SH, R_SH = identifica_picioare_fandare(puncte)

    def P(i):
        return (puncte[i].x, puncte[i].y)

    sold_fata, genunchi_fata, glezna_fata = P(fH), P(fK), P(fA)
    sold_spate, genunchi_spate, glezna_spate = P(bH), P(bK), P(bA)
    umar_st, umar_dr = P(L_SH), P(R_SH)

    dx = genunchi_fata[0] - glezna_fata[0]
    dy = genunchi_fata[1] - glezna_fata[1]
    unghi_gamba = 0.0 if dy == 0 else degrees(atan(abs(dx / dy)))

    genunchi_peste_varf = genunchi_fata[0] - glezna_fata[0]
    lungime_gamba = hypot(dx, dy)
    limita_offset = max(1e-6, lungime_gamba * 0.12)

    sold_st, sold_dr = P(23), P(24)
    dx_p = sold_dr[0] - sold_st[0]
    dy_p = sold_dr[1] - sold_st[1]
    inclinare_bazin = 90 if dx_p == 0 else degrees(atan(abs(dy_p / dx_p)))

    mijloc_umar = ((umar_st[0] + umar_dr[0]) / 2, (umar_st[1] + umar_dr[1]) / 2)
    mijloc_sold = ((sold_st[0] + sold_dr[0]) / 2, (sold_st[1] + sold_dr[1]) / 2)
    dx_t = mijloc_umar[0] - mijloc_sold[0]
    dy_t = mijloc_umar[1] - mijloc_sold[1]
    unghi_trunchi = 90 if dy_t == 0 else degrees(atan(abs(dx_t / dy_t)))

    unghi_genunchi_fata = calculate_angle(sold_fata, genunchi_fata, glezna_fata)
    adancime_spate = genunchi_spate[1] - glezna_spate[1]

    return {
        'unghi_gamba': unghi_gamba,
        'genunchi_peste_varf': genunchi_peste_varf,
        'limita_offset': limita_offset,
        'inclinare_bazin': inclinare_bazin,
        'unghi_trunchi': unghi_trunchi,
        'unghi_genunchi_fata': unghi_genunchi_fata,
        'adancime_spate': adancime_spate,
        'puncte_cheie': (fH, fK, fA, bH, bK, bA, L_SH, R_SH)
    }


def evalueaza_fandare(date_postura):
    feedback = []
    total = 0
    sectiuni = 0

    gamba = date_postura['unghi_gamba']
    if gamba <= 6:
        s = 100
        feedback.append("Gamba din fata este aproape verticala - excelent!")
    elif gamba <= 10:
        s = 80
        feedback.append("Gamba din fata e usor inclinata - inca e bine.")
    else:
        s = 40
        feedback.append("Gamba este prea inclinata - incearca sa iti ajustezi pozitia.")
    total += s
    sectiuni += 1

    varf = abs(date_postura['genunchi_peste_varf'])
    if varf <= date_postura['limita_offset']:
        s = 100
        feedback.append("Genunchiul ramane aliniat cu varful piciorului - perfect.")
    elif varf <= date_postura['limita_offset'] * 1.4:
        s = 70
        feedback.append("Genunchiul trece putin peste varf - ai grija la echilibru.")
    else:
        s = 40
        feedback.append("Genunchiul trece prea mult peste varf - muta usor trunchiul inapoi.")
    total += s
    sectiuni += 1

    trunchi = date_postura['unghi_trunchi']
    if trunchi <= 10:
        s = 100
        feedback.append("Trunchiul tau este drept - foarte bine!")
    elif trunchi <= 15:
        s = 80
        feedback.append("Trunchiul e usor aplecat - acceptabil.")
    else:
        s = 40
        feedback.append("Esti prea aplecat(a) - trage umerii usor inapoi.")
    total += s
    sectiuni += 1

    genunchi = date_postura['unghi_genunchi_fata']
    if 80 <= genunchi <= 100:
        s = 100
        feedback.append("Unghiul genunchiului este aproape perfect (~90°).")
    elif 70 <= genunchi <= 110:
        s = 80
        feedback.append("Unghiul genunchiului este decent - mai poti regla putin.")
    else:
        s = 40
        feedback.append("Unghiul genunchiului nu e corect - ajusteaza pasul.")
    total += s
    sectiuni += 1

    bazin = date_postura['inclinare_bazin']
    if 50 <= bazin < 70:
        s = 100
        feedback.append("Bazinul tau este bine aliniat.")
    elif 40 <= bazin < 50:
        s = 80
        feedback.append("Bazin usor inclinat - verifica echilibrul.")
    else:
        s = 40
        feedback.append("Bazinul este inclinat - incordeaza fesierul din spate.")
    total += s
    sectiuni += 1

    adancime = date_postura['adancime_spate']
    if adancime >= -0.02:
        s = 100
        feedback.append("Coborare perfecta - adancimea e ideala.")
    elif adancime >= -0.06:
        s = 80
        feedback.append("Adancimea este buna, dar poti cobori un pic mai mult.")
    else:
        s = 40
        feedback.append("Coboara mai controlat, genunchiul din spate e prea sus.")
    total += s
    sectiuni += 1

    scor_final = int(total / sectiuni) if sectiuni else 0
    return scor_final, feedback
# =========================================
# VALIDARE REPETITII - START / BOTTOM / FINISH
# =========================================

def avg_point(a, b):
    return ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)

def pushup_rep_state(landmarks):
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

    sh_mid = avg_point(left_shoulder, right_shoulder)
    hip_mid = avg_point(left_hip, right_hip)
    ank_mid = avg_point(left_ankle, right_ankle)

    body_alignment = calculate_angle(sh_mid, hip_mid, ank_mid)
    left_elbow_angle = calculate_angle(left_shoulder, left_elbow, left_wrist)
    right_elbow_angle = calculate_angle(right_shoulder, right_elbow, right_wrist)
    elbow_avg = (left_elbow_angle + right_elbow_angle) / 2.0

    ground_y = max(left_wrist[1], right_wrist[1], left_ankle[1], right_ankle[1])
    chest_y = (left_shoulder[1] + right_shoulder[1]) / 2.0
    chest_distance = max(0.0, ground_y - chest_y)

    start_ok = (155 <= body_alignment <= 205) and (elbow_avg >= 130)
    bottom_ok = (elbow_avg <= 115) and (chest_distance <= 0.22)
    finish_ok = (155 <= body_alignment <= 205) and (elbow_avg >= 130)

    return {
        "start_ok": start_ok,
        "bottom_ok": bottom_ok,
        "finish_ok": finish_ok,
        "body_alignment": body_alignment,
        "elbow_avg": elbow_avg,
        "chest_distance": chest_distance
    }

def squat_rep_state(landmarks):
    left_shoulder = (landmarks[11].x, landmarks[11].y)
    right_shoulder = (landmarks[12].x, landmarks[12].y)
    left_hip = (landmarks[23].x, landmarks[23].y)
    right_hip = (landmarks[24].x, landmarks[24].y)
    left_knee = (landmarks[25].x, landmarks[25].y)
    right_knee = (landmarks[26].x, landmarks[26].y)
    left_ankle = (landmarks[27].x, landmarks[27].y)
    right_ankle = (landmarks[28].x, landmarks[28].y)

    sh_mid = avg_point(left_shoulder, right_shoulder)
    hip_mid = avg_point(left_hip, right_hip)

    kL = calculate_squat_angle(left_hip, left_knee, left_ankle)
    kR = calculate_squat_angle(right_hip, right_knee, right_ankle)
    knee_avg = (kL + kR) / 2.0

    trunk_left = calculate_trunk_angle(left_hip, left_shoulder)
    trunk_right = calculate_trunk_angle(right_hip, right_shoulder)
    trunk_avg = (trunk_left + trunk_right) / 2.0

    start_ok = knee_avg >= 140
    bottom_ok = knee_avg <= 125
    finish_ok = knee_avg >= 140

    return {
        "start_ok": start_ok,
        "bottom_ok": bottom_ok,
        "finish_ok": finish_ok,
        "knee_avg": knee_avg,
        "trunk_avg": trunk_avg,
        "hip_y": hip_mid[1],
        "shoulder_y": sh_mid[1]
    }

def deadlift_rep_state(landmarks):
    left_shoulder = (landmarks[11].x, landmarks[11].y)
    right_shoulder = (landmarks[12].x, landmarks[12].y)
    left_hip = (landmarks[23].x, landmarks[23].y)
    right_hip = (landmarks[24].x, landmarks[24].y)
    left_knee = (landmarks[25].x, landmarks[25].y)
    right_knee = (landmarks[26].x, landmarks[26].y)
    left_ankle = (landmarks[27].x, landmarks[27].y)
    right_ankle = (landmarks[28].x, landmarks[28].y)

    hip_mid = avg_point(left_hip, right_hip)

    kL = calculate_squat_angle(left_hip, left_knee, left_ankle)
    kR = calculate_squat_angle(right_hip, right_knee, right_ankle)
    knee_avg = (kL + kR) / 2.0

    trunk_left = calculate_trunk_angle(left_hip, left_shoulder)
    trunk_right = calculate_trunk_angle(right_hip, right_shoulder)
    trunk_avg = (trunk_left + trunk_right) / 2.0

    # Deadlift corect:
    # sus = genunchii aproape întinși + trunchi aproape vertical
    # jos = trunchi aplecat, dar genunchii nu sunt foarte flexați ca la genuflexiune
    start_ok = (
        knee_avg >= 135 and
        trunk_avg <= 18
    )

    bottom_ok = (
        95 <= knee_avg <= 165 and
        trunk_avg >= 18
    )

    finish_ok = (
        knee_avg >= 135 and
        trunk_avg <= 18
    )

    return {
        "start_ok": start_ok,
        "bottom_ok": bottom_ok,
        "finish_ok": finish_ok,
        "knee_avg": knee_avg,
        "trunk_avg": trunk_avg,
        "hip_y": hip_mid[1],
        "hip_x": hip_mid[0],
    }

def lunge_rep_state(landmarks):
    posture = analizeaza_postura_fandare(landmarks)

    front_knee = posture["unghi_genunchi_fata"]
    back_depth = posture["adancime_spate"]
    trunk = posture["unghi_trunchi"]

    start_ok = front_knee >= 125
    bottom_ok = (70 <= front_knee <= 125) and (back_depth >= -0.12)
    finish_ok = front_knee >= 125

    return {
        "start_ok": start_ok,
        "bottom_ok": bottom_ok,
        "finish_ok": finish_ok,
        "front_knee": front_knee,
        "back_depth": back_depth,
        "trunk": trunk
    }
# PLANK 

def plank_state(landmarks):
    """
    Analizează postura pentru plank.
    Plank-ul nu are repetări, ci se evaluează ca poziție statică.
    """

    left_shoulder = (landmarks[11].x, landmarks[11].y)
    right_shoulder = (landmarks[12].x, landmarks[12].y)
    left_hip = (landmarks[23].x, landmarks[23].y)
    right_hip = (landmarks[24].x, landmarks[24].y)
    left_ankle = (landmarks[27].x, landmarks[27].y)
    right_ankle = (landmarks[28].x, landmarks[28].y)
    left_elbow = (landmarks[13].x, landmarks[13].y)
    right_elbow = (landmarks[14].x, landmarks[14].y)

    shoulder_mid = avg_point(left_shoulder, right_shoulder)
    hip_mid = avg_point(left_hip, right_hip)
    ankle_mid = avg_point(left_ankle, right_ankle)
    elbow_mid = avg_point(left_elbow, right_elbow)

    body_alignment = calculate_angle(shoulder_mid, hip_mid, ankle_mid)

    pelvis_tilt = abs(left_hip[1] - right_hip[1])
    shoulder_elbow_offset = abs(shoulder_mid[0] - elbow_mid[0])

    # Pentru plank corect, corpul este aproximativ drept.
    alignment_ok = 155 <= body_alignment <= 205

    # Dacă șoldul este mult mai jos/sus față de linia corpului, postura e slabă.
    line_dx = ankle_mid[0] - shoulder_mid[0]
    line_dy = ankle_mid[1] - shoulder_mid[1]
    line_len = max(1e-6, math.sqrt(line_dx ** 2 + line_dy ** 2))

    hip_dx = hip_mid[0] - shoulder_mid[0]
    hip_dy = hip_mid[1] - shoulder_mid[1]
    signed_line_deviation = ((line_dx * hip_dy) - (line_dy * hip_dx)) / line_len
    hip_deviation = abs(signed_line_deviation)

    if abs(line_dx) > 1e-6:
        hip_line_y = shoulder_mid[1] + line_dy * ((hip_mid[0] - shoulder_mid[0]) / line_dx)
        hip_position = "high" if hip_mid[1] < hip_line_y else "low"
    else:
        hip_position = "high" if signed_line_deviation < 0 else "low"

    if hip_deviation <= 0.06:
        hip_position = "neutral"

    plank_like = alignment_ok and hip_deviation <= 0.16

    return {
        "plank_like": plank_like,
        "body_alignment": body_alignment,
        "hip_deviation": hip_deviation,
        "hip_signed_deviation": signed_line_deviation,
        "hip_position": hip_position,
        "pelvis_tilt": pelvis_tilt,
        "shoulder_elbow_offset": shoulder_elbow_offset,
    }


def evaluate_plank_alignment(body_alignment):
    if 165 <= body_alignment <= 195:
        return 100
    elif 155 <= body_alignment < 165 or 195 < body_alignment <= 205:
        return 85
    elif 145 <= body_alignment < 155 or 205 < body_alignment <= 215:
        return 60
    else:
        return 35


def evaluate_plank_hip_position(hip_deviation):
    if hip_deviation <= 0.06:
        return 100
    elif hip_deviation <= 0.10:
        return 80
    elif hip_deviation <= 0.14:
        return 55
    else:
        return 30


def evaluate_plank_pelvis_stability(pelvis_tilt):
    if pelvis_tilt <= 0.045:
        return 100
    elif pelvis_tilt <= 0.075:
        return 80
    else:
        return 45


def evaluate_plank_elbow_position(shoulder_elbow_offset):
    if shoulder_elbow_offset <= 0.08:
        return 100
    elif shoulder_elbow_offset <= 0.13:
        return 80
    else:
        return 55


def _legacy_generate_plank_feedback(body_alignment, hip_deviation, pelvis_tilt, shoulder_elbow_offset):
    feedback = []

    if 170 <= body_alignment <= 190:
        feedback.append("Corpul este bine aliniat în poziția de plank.")
    elif body_alignment < 170:
        feedback.append("Bazinul pare prea ridicat; încearcă să păstrezi corpul într-o linie dreaptă.")
    elif body_alignment > 190:
        feedback.append("Bazinul pare să cadă prea jos; încordează abdomenul și fesierii.")
    else:
        feedback.append("Alinierea corpului nu este stabilă; ajustează poziția trunchiului.")

    if hip_deviation <= 0.04:
        feedback.append("Poziția șoldurilor este stabilă.")
    elif hip_deviation <= 0.08:
        feedback.append("Șoldurile sunt ușor deplasate; menține abdomenul mai activ.")
    else:
        feedback.append("Șoldurile sunt prea sus sau prea jos față de linia corpului.")

    if pelvis_tilt <= 0.03:
        feedback.append("Bazinul este drept.")
    elif pelvis_tilt <= 0.06:
        feedback.append("Există o ușoară înclinare a bazinului.")
    else:
        feedback.append("Bazinul este înclinat; distribuie greutatea egal pe ambele părți.")

    if shoulder_elbow_offset <= 0.06:
        feedback.append("Coatele sunt bine poziționate sub umeri.")
    elif shoulder_elbow_offset <= 0.10:
        feedback.append("Coatele sunt ușor deplasate; încearcă să le aliniez mai bine sub umeri.")
    else:
        feedback.append("Coatele sunt prea departe de linia umerilor; ajustează poziția brațelor.")

    return feedback



def bench_press_rep_state(landmarks):
    """
    Detectează fazele unei repetări de bench press:
    start = brațe aproape întinse sus
    bottom = coate flexate jos
    finish = brațe aproape întinse din nou
    """

    left_shoulder = (landmarks[11].x, landmarks[11].y)
    right_shoulder = (landmarks[12].x, landmarks[12].y)
    left_elbow = (landmarks[13].x, landmarks[13].y)
    right_elbow = (landmarks[14].x, landmarks[14].y)
    left_wrist = (landmarks[15].x, landmarks[15].y)
    right_wrist = (landmarks[16].x, landmarks[16].y)
    left_hip = (landmarks[23].x, landmarks[23].y)
    right_hip = (landmarks[24].x, landmarks[24].y)

    left_elbow_angle = calculate_angle(left_shoulder, left_elbow, left_wrist)
    right_elbow_angle = calculate_angle(right_shoulder, right_elbow, right_wrist)
    elbow_avg = (left_elbow_angle + right_elbow_angle) / 2.0

    shoulder_mid = avg_point(left_shoulder, right_shoulder)
    hip_mid = avg_point(left_hip, right_hip)

    wrist_mid = avg_point(left_wrist, right_wrist)
    elbow_mid = avg_point(left_elbow, right_elbow)

    # Corp relativ static / culcat.
    torso_vertical_motion_proxy = abs(shoulder_mid[1] - hip_mid[1])

    # Aliniere încheieturi-coate.
    wrist_elbow_offset = abs(wrist_mid[0] - elbow_mid[0])

    start_ok = elbow_avg >= 145
    bottom_ok = elbow_avg <= 105
    finish_ok = elbow_avg >= 145

    return {
        "start_ok": start_ok,
        "bottom_ok": bottom_ok,
        "finish_ok": finish_ok,
        "elbow_avg": elbow_avg,
        "left_elbow_angle": left_elbow_angle,
        "right_elbow_angle": right_elbow_angle,
        "wrist_elbow_offset": wrist_elbow_offset,
        "torso_vertical_motion_proxy": torso_vertical_motion_proxy,
    }


def evaluate_bench_elbow_depth(elbow_avg):
    if 70 <= elbow_avg <= 105:
        return 100
    elif 105 < elbow_avg <= 120:
        return 70
    else:
        return 30


def evaluate_bench_symmetry(left_elbow_angle, right_elbow_angle):
    diff = abs(left_elbow_angle - right_elbow_angle)

    if diff <= 10:
        return 100
    elif diff <= 20:
        return 70
    else:
        return 30


def evaluate_bench_wrist_alignment(wrist_elbow_offset):
    if wrist_elbow_offset <= 0.06:
        return 100
    elif wrist_elbow_offset <= 0.10:
        return 70
    else:
        return 30


def evaluate_bench_body_stability(torso_vertical_motion_proxy):
    if torso_vertical_motion_proxy <= 0.20:
        return 100
    elif torso_vertical_motion_proxy <= 0.28:
        return 70
    else:
        return 40


def generate_bench_press_feedback(
    elbow_avg,
    left_elbow_angle,
    right_elbow_angle,
    wrist_elbow_offset,
    torso_vertical_motion_proxy
):
    feedback = []

    if 70 <= elbow_avg <= 105:
        feedback.append("Adâncimea repetării este bună.")
    elif 105 < elbow_avg <= 120:
        feedback.append("Coboară puțin mai mult pentru o amplitudine mai bună.")
    else:
        feedback.append("Amplitudinea nu este optimă; controlează mai bine coborârea barei.")

    diff = abs(left_elbow_angle - right_elbow_angle)
    if diff <= 10:
        feedback.append("Brațele lucrează simetric.")
    elif diff <= 20:
        feedback.append("Există o mică diferență între brațe.")
    else:
        feedback.append("Brațele nu lucrează simetric; împinge egal cu ambele părți.")

    if wrist_elbow_offset <= 0.06:
        feedback.append("Încheieturile sunt bine aliniate cu coatele.")
    elif wrist_elbow_offset <= 0.10:
        feedback.append("Încheieturile sunt ușor deplasate; încearcă să le ții deasupra coatelor.")
    else:
        feedback.append("Încheieturile sunt prea departe de linia coatelor; corectează poziția mâinilor.")

    if torso_vertical_motion_proxy <= 0.20:
        feedback.append("Corpul este stabil pe bancă.")
    elif torso_vertical_motion_proxy <= 0.28:
        feedback.append("Corpul este relativ stabil, dar încearcă să eviți ridicarea trunchiului.")
    else:
        feedback.append("Corpul se mișcă prea mult; menține spatele și șoldurile stabile pe bancă.")

    return feedback


def _upper_body_points(landmarks):
    left_shoulder = (landmarks[11].x, landmarks[11].y)
    right_shoulder = (landmarks[12].x, landmarks[12].y)
    left_elbow = (landmarks[13].x, landmarks[13].y)
    right_elbow = (landmarks[14].x, landmarks[14].y)
    left_wrist = (landmarks[15].x, landmarks[15].y)
    right_wrist = (landmarks[16].x, landmarks[16].y)
    left_hip = (landmarks[23].x, landmarks[23].y)
    right_hip = (landmarks[24].x, landmarks[24].y)
    return left_shoulder, right_shoulder, left_elbow, right_elbow, left_wrist, right_wrist, left_hip, right_hip


def biceps_curl_rep_state(landmarks):
    L_sh, R_sh, L_el, R_el, L_wr, R_wr, L_hip, R_hip = _upper_body_points(landmarks)
    left_elbow_angle = calculate_angle(L_sh, L_el, L_wr)
    right_elbow_angle = calculate_angle(R_sh, R_el, R_wr)
    elbow_avg = (left_elbow_angle + right_elbow_angle) / 2.0
    shoulder_mid = avg_point(L_sh, R_sh)
    hip_mid = avg_point(L_hip, R_hip)
    elbow_mid = avg_point(L_el, R_el)
    wrist_mid = avg_point(L_wr, R_wr)
    torso_lean = abs(shoulder_mid[0] - hip_mid[0])
    elbow_drift = abs(elbow_mid[0] - shoulder_mid[0])
    wrist_height = shoulder_mid[1] - wrist_mid[1]

    return {
        "start_ok": elbow_avg >= 130,
        "bottom_ok": elbow_avg <= 110,
        "finish_ok": elbow_avg >= 125,
        "elbow_avg": elbow_avg,
        "left_elbow_angle": left_elbow_angle,
        "right_elbow_angle": right_elbow_angle,
        "torso_lean": torso_lean,
        "elbow_drift": elbow_drift,
        "wrist_height": wrist_height,
    }


def _default_mountain_climber_state():
    return {
        "start_ok": False,
        "bottom_ok": False,
        "finish_ok": False,
        "left_knee_forward": False,
        "right_knee_forward": False,
        "active_side": "none",
        "body_alignment": 180.0,
        "elbow_avg": 180.0,
        "hip_deviation": 1.0,
        "pelvis_tilt": 1.0,
        "left_knee_to_chest": 1.0,
        "right_knee_to_chest": 1.0,
        "left_drive": 0.0,
        "right_drive": 0.0,
        "drive_margin": 0.0,
        "shoulder_wrist_offset": 1.0,
    }


def mountain_climber_rep_state(landmarks):
    if landmarks is None or len(landmarks) <= 28:
        return _default_mountain_climber_state()

    left_shoulder = (landmarks[11].x, landmarks[11].y)
    right_shoulder = (landmarks[12].x, landmarks[12].y)
    left_elbow = (landmarks[13].x, landmarks[13].y)
    right_elbow = (landmarks[14].x, landmarks[14].y)
    left_wrist = (landmarks[15].x, landmarks[15].y)
    right_wrist = (landmarks[16].x, landmarks[16].y)
    left_hip = (landmarks[23].x, landmarks[23].y)
    right_hip = (landmarks[24].x, landmarks[24].y)
    left_knee = (landmarks[25].x, landmarks[25].y)
    right_knee = (landmarks[26].x, landmarks[26].y)
    left_ankle = (landmarks[27].x, landmarks[27].y)
    right_ankle = (landmarks[28].x, landmarks[28].y)

    shoulder_mid = avg_point(left_shoulder, right_shoulder)
    hip_mid = avg_point(left_hip, right_hip)
    ankle_mid = avg_point(left_ankle, right_ankle)
    wrist_mid = avg_point(left_wrist, right_wrist)
    chest_anchor = avg_point(shoulder_mid, hip_mid)

    body_alignment = calculate_angle(shoulder_mid, hip_mid, ankle_mid)
    left_leg_angle = calculate_angle(left_hip, left_knee, left_ankle)
    right_leg_angle = calculate_angle(right_hip, right_knee, right_ankle)
    left_elbow_angle = calculate_angle(left_shoulder, left_elbow, left_wrist)
    right_elbow_angle = calculate_angle(right_shoulder, right_elbow, right_wrist)
    elbow_avg = (left_elbow_angle + right_elbow_angle) / 2.0

    body_len = max(0.25, hypot(shoulder_mid[0] - ankle_mid[0], shoulder_mid[1] - ankle_mid[1]))
    left_knee_to_chest = hypot(left_knee[0] - chest_anchor[0], left_knee[1] - chest_anchor[1]) / body_len
    right_knee_to_chest = hypot(right_knee[0] - chest_anchor[0], right_knee[1] - chest_anchor[1]) / body_len

    line_dx = ankle_mid[0] - shoulder_mid[0]
    line_dy = ankle_mid[1] - shoulder_mid[1]
    line_len = max(1e-6, math.sqrt(line_dx ** 2 + line_dy ** 2))
    hip_dx = hip_mid[0] - shoulder_mid[0]
    hip_dy = hip_mid[1] - shoulder_mid[1]
    hip_deviation = abs(((line_dx * hip_dy) - (line_dy * hip_dx)) / line_len)
    pelvis_tilt = abs(left_hip[1] - right_hip[1])
    shoulder_wrist_offset = abs(shoulder_mid[0] - wrist_mid[0])

    body_aligned = 140 <= body_alignment <= 220 and hip_deviation <= 0.18
    neutral_ok = body_aligned and left_leg_angle >= 130 and right_leg_angle >= 130
    left_drive = max(0.0, 0.60 - left_knee_to_chest)
    right_drive = max(0.0, 0.60 - right_knee_to_chest)
    drive_margin = abs(left_drive - right_drive)
    # Reduced thresholds to detect more valid knee drives
    left_knee_forward = body_aligned and left_drive >= 0.08 and left_leg_angle <= 165
    right_knee_forward = body_aligned and right_drive >= 0.08 and right_leg_angle <= 165

    if body_aligned and left_drive >= 0.08 and left_drive > right_drive + 0.035:
        active_side = "left"
    elif body_aligned and right_drive >= 0.08 and right_drive > left_drive + 0.035:
        active_side = "right"
    else:
        active_side = "none"

    return {
        "start_ok": neutral_ok or left_knee_forward or right_knee_forward,
        "bottom_ok": left_knee_forward or right_knee_forward,
        "finish_ok": neutral_ok or left_knee_forward or right_knee_forward,
        "left_knee_forward": left_knee_forward,
        "right_knee_forward": right_knee_forward,
        "active_side": active_side,
        "body_alignment": body_alignment,
        "elbow_avg": elbow_avg,
        "hip_deviation": hip_deviation,
        "pelvis_tilt": pelvis_tilt,
        "left_knee_to_chest": left_knee_to_chest,
        "right_knee_to_chest": right_knee_to_chest,
        "left_drive": left_drive,
        "right_drive": right_drive,
        "drive_margin": drive_margin,
        "shoulder_wrist_offset": shoulder_wrist_offset,
    }


def lateral_raise_rep_state(landmarks):
    L_sh, R_sh, L_el, R_el, L_wr, R_wr, L_hip, R_hip = _upper_body_points(landmarks)
    left_elbow_angle = calculate_angle(L_sh, L_el, L_wr)
    right_elbow_angle = calculate_angle(R_sh, R_el, R_wr)
    elbow_avg = (left_elbow_angle + right_elbow_angle) / 2.0
    shoulder_mid = avg_point(L_sh, R_sh)
    hip_mid = avg_point(L_hip, R_hip)
    wrist_mid = avg_point(L_wr, R_wr)
    elbow_mid = avg_point(L_el, R_el)
    wrist_level = abs(wrist_mid[1] - shoulder_mid[1])
    elbow_level = abs(elbow_mid[1] - shoulder_mid[1])
    wrist_below_shoulder = wrist_mid[1] - shoulder_mid[1]
    torso_lean = abs(shoulder_mid[0] - hip_mid[0])
    arm_symmetry = abs(L_wr[1] - R_wr[1])

    return {
        "start_ok": wrist_below_shoulder > 0.22,
        "bottom_ok": wrist_level <= 0.12 and elbow_level <= 0.16,
        "finish_ok": wrist_below_shoulder > 0.18,
        "elbow_avg": elbow_avg,
        "left_elbow_angle": left_elbow_angle,
        "right_elbow_angle": right_elbow_angle,
        "wrist_level": wrist_level,
        "elbow_level": elbow_level,
        "torso_lean": torso_lean,
        "arm_symmetry": arm_symmetry,
    }


def score_biceps_curl(elbow_avg, left_elbow_angle, right_elbow_angle, torso_lean, elbow_drift):
    amplitude_score = 100 if elbow_avg <= 60 else 75 if elbow_avg <= 85 else 40
    symmetry_score = 100 if abs(left_elbow_angle - right_elbow_angle) <= 12 else 75 if abs(left_elbow_angle - right_elbow_angle) <= 22 else 45
    torso_score = 100 if torso_lean <= 0.08 else 75 if torso_lean <= 0.14 else 45
    elbow_score = 100 if elbow_drift <= 0.14 else 75 if elbow_drift <= 0.22 else 45
    return amplitude_score, symmetry_score, torso_score, elbow_score


def generate_biceps_curl_feedback(elbow_avg, left_elbow_angle, right_elbow_angle, torso_lean, elbow_drift):
    feedback = []
    feedback.append("Flexia cotului este buna." if elbow_avg <= 75 else "Ridica mai mult greutatea pentru o contractie completa.")
    feedback.append("Bratele lucreaza simetric." if abs(left_elbow_angle - right_elbow_angle) <= 12 else "Exista o diferenta intre brate; incearca sa ridici uniform.")
    feedback.append("Trunchiul ramane stabil." if torso_lean <= 0.08 else "Evita balansul trunchiului in timpul flexiei.")
    feedback.append("Coatele sunt stabile langa corp." if elbow_drift <= 0.14 else "Tine coatele mai fixe langa trunchi.")
    return feedback


def evaluate_mountain_climber_body_alignment(body_alignment):
    if 150 <= body_alignment <= 210:
        return 100
    if 140 <= body_alignment <= 220:
        return 75
    return 40


def evaluate_mountain_climber_knee_drive(knee_to_chest):
    if knee_to_chest <= 0.50:
        return 100
    if knee_to_chest <= 0.60:
        return 75
    return 40


def evaluate_mountain_climber_hip_stability(hip_deviation, pelvis_tilt):
    if hip_deviation <= 0.10 and pelvis_tilt <= 0.06:
        return 100
    if hip_deviation <= 0.18 and pelvis_tilt <= 0.12:
        return 75
    return 40


def evaluate_mountain_climber_arm_support(elbow_avg, shoulder_wrist_offset):
    if elbow_avg >= 145 and shoulder_wrist_offset <= 0.14:
        return 100
    if elbow_avg >= 130 and shoulder_wrist_offset <= 0.22:
        return 75
    return 40


def generate_mountain_climber_feedback(
    body_alignment,
    knee_to_chest,
    hip_deviation,
    pelvis_tilt,
    elbow_avg,
    shoulder_wrist_offset,
):
    feedback = []
    feedback.append(
        "Alinierea corpului este buna."
        if 140 <= body_alignment <= 220
        else "Mentine trunchiul mai drept, ca intr-un plank."
    )
    if knee_to_chest > 0.60:
        feedback.append("Adu genunchiul mai aproape de piept pentru mai multa amplitudine.")
    if hip_deviation > 0.18 or pelvis_tilt > 0.12:
        feedback.append("Soldurile se misca prea mult; stabilizeaza bazinul mai bine.")
    if shoulder_wrist_offset > 0.22:
        feedback.append("Mentine umerii mai direct deasupra incheieturilor.")
    if elbow_avg < 130:
        feedback.append("Bratele se indoaie prea mult; intinde-le mai mult pentru sprijin.")
    if len(feedback) == 1:
        feedback.append("Ritmul si sprijinul sunt buni!")
    return feedback


def score_lateral_raise(elbow_avg, wrist_level, elbow_level, arm_symmetry, torso_lean):
    height_score = 100 if wrist_level <= 0.08 else 75 if wrist_level <= 0.14 else 45
    elbow_height_score = 100 if elbow_level <= 0.12 else 75 if elbow_level <= 0.18 else 45
    elbow_bend_score = 100 if elbow_avg >= 145 else 75 if elbow_avg >= 125 else 45
    symmetry_score = 100 if arm_symmetry <= 0.05 else 75 if arm_symmetry <= 0.09 else 45
    torso_score = 100 if torso_lean <= 0.08 else 75 if torso_lean <= 0.14 else 45
    return height_score, elbow_height_score, elbow_bend_score, symmetry_score, torso_score


def generate_lateral_raise_feedback(elbow_avg, wrist_level, elbow_level, arm_symmetry, torso_lean):
    feedback = []
    feedback.append("Bratele ajung aproape la nivelul umerilor." if wrist_level <= 0.12 else "Ridica bratele pana aproape de nivelul umerilor.")
    feedback.append("Coatele sunt la o inaltime potrivita." if elbow_level <= 0.16 else "Controleaza coatele; nu lasa bratele sa cada.")
    feedback.append("Coatele raman usor flexate, dar controlate." if elbow_avg >= 125 else "Indoi prea mult coatele la ridicare.")
    feedback.append("Ridicarea este simetrica." if arm_symmetry <= 0.06 else "Un brat pare mai jos; ridica simetric.")
    feedback.append("Trunchiul ramane stabil." if torso_lean <= 0.08 else "Evita balansul trunchiului pentru a ridica greutatile.")
    return feedback
