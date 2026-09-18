import random

EMBED_SIZE = 512
THRESHOLD = 0.75

def enroll(image_path):
    """Photo -> fingerprint (embedding). Ippo fake, appuram real."""
    return [random.random() for _ in range(EMBED_SIZE)]

def verify(emb_a, emb_b):
    """Rendu fingerprint compare -> similarity 0 to 1."""
    return random.uniform(0.2, 0.95)

def is_match(similarity):
    return similarity >= THRESHOLD