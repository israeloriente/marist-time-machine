import os

MODEL_NAME = os.getenv("ML_MODEL_NAME", "buffalo_l")
DET_THRESHOLD = float(os.getenv("ML_DET_THRESHOLD", "0.7"))
DET_SIZE = int(os.getenv("ML_DET_SIZE", "640"))
