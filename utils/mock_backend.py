
import time
import numpy as np

# Fake agents database
AGENTS = {
    "vet01":  {"password": "test", "name": "Dr. Sharma",   "role": "vet"},
    "vet02":  {"password": "test", "name": "Dr. Reddy",    "role": "vet"},
    "surv01": {"password": "test", "name": "R. Kumar",     "role": "surveyor"},
}

# In-memory "database"
ANIMALS = {
    "0142": {"cow_id": "0142", "breed": "Gir", "age": 4, "owner": "Ramesh Patel",
             "policy_id": "POL-9921", "status": "active",
             "registration_date": "2026-09-15", "photo_path": "assets/cow.jpg"},
    "0088": {"cow_id": "0088", "breed": "Sahiwal", "age": 5, "owner": "Suresh Yadav",
             "policy_id": "POL-9922", "status": "active",
             "registration_date": "2026-09-15", "photo_path": "assets/cow.jpg"},
    "0211": {"cow_id": "0211", "breed": "Red Sindhi", "age": 3, "owner": "Anita Devi",
             "policy_id": "POL-9923", "status": "active",
             "registration_date": "2026-09-15", "photo_path": "assets/cow.jpg"},
}

VERIFICATIONS = []
FRAUD_FLAGS = []


def check_agent_login(agent_id, password):
    agent = AGENTS.get(agent_id)
    if agent and agent["password"] == password:
        return {"ok": True, "name": agent["name"], "role": agent["role"]}
    return {"ok": False, "name": None, "role": None}


def get_all_animals():
    return list(ANIMALS.keys())


def get_animal(cow_id):
    return ANIMALS.get(cow_id)


def get_verification_history(cow_id):
    return [v for v in VERIFICATIONS if v.get("cow_id") == cow_id]


def get_all_photo_paths():
    return [a["photo_path"] for a in ANIMALS.values()]


def find_matches(image_path, top_k=3):
    """Mock: randomly picks one of 4 states for testing."""
    time.sleep(1)
    state = "high_confidence"   # change to test other states

    if state == "unusable":
        return {"status": "unusable", "quality_ok": False, "top_matches": []}

    matches = [
        {"cow_id": "0142", "score": 0.94, "photo_path": "assets/cow.jpg"},
        {"cow_id": "0088", "score": 0.62, "photo_path": "assets/cow.jpg"},
        {"cow_id": "0211", "score": 0.55, "photo_path": "assets/cow.jpg"},
    ][:top_k]
    return {"status": state, "quality_ok": True, "top_matches": matches}


def check_duplicate(image_path, existing_photo_paths):
    return {"is_duplicate": False, "matched_photo_path": None, "hash_distance": 20}


def register_animal(breed, age, owner_name, policy_id, muzzle_photo_path):
    new_id = f"0{len(ANIMALS) + 142}"
    ANIMALS[new_id] = {
        "cow_id": new_id, "breed": breed, "age": age, "owner": owner_name,
        "policy_id": policy_id, "status": "active",
        "registration_date": "2026-09-18", "photo_path": muzzle_photo_path,
    }
    return new_id


def log_verification(cow_id, verification_type, photo_path, top_match_cow_id, similarity_score, result_status):
    VERIFICATIONS.append({
        "cow_id": cow_id, "type": verification_type, "photo_path": photo_path,
        "top_match_cow_id": top_match_cow_id, "score": similarity_score,
        "result_status": result_status, "timestamp": time.strftime("%Y-%m-%d %H:%M"),
    })


def add_fraud_flag(cow_id, flag_type, details):
    FRAUD_FLAGS.append({
        "cow_id": cow_id, "flag_type": flag_type, "details": details,
        "created_at": time.strftime("%Y-%m-%d %H:%M"),
    })


def get_all_fraud_flags():
    return FRAUD_FLAGS


def get_all_embeddings():
    """Returns fake 2D embeddings for the plot."""
    rng = np.random.default_rng(42)
    ids = list(ANIMALS.keys())
    return {cid: rng.standard_normal(2) for cid in ids}


def get_embedding_for_image(image_path):
    """Fake: returns a 2D point for the uploaded image."""
    return np.array([0.5, -0.3])