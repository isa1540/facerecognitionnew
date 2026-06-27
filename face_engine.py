import os
import io
import base64
import pickle
import numpy as np
from datetime import datetime
from PIL import Image


class FaceEngine:
    def __init__(self):
        self.face_encodings = {}
        self.face_cache_file = "face_cache.pkl"

        self.load_cache()

        if len(self.face_encodings) == 0:
            self.load_from_database()

        print(f"✅ FaceEngine initialized with {len(self.face_encodings)} face encodings")

    def load_from_database(self):
        try:
            from app import FaceEncoding

            rows = FaceEncoding.query.all()
            self.face_encodings = {}

            for row in rows:
                self.face_encodings[row.employee_id] = row.encoding

            print(f"✅ Loaded {len(rows)} face encodings from database")

        except Exception as e:
            print(f"⚠️ Failed load encodings from database: {e}")

    def extract_face_encoding_from_bytes(self, image_bytes):
        try:
            import face_recognition

            img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            img_np = np.array(img)

            face_locations = face_recognition.face_locations(
                img_np,
                model="hog"
            )

            if not face_locations:
                print("⚠️ No face locations found")
                return None

            encodings = face_recognition.face_encodings(
                img_np,
                face_locations,
                num_jitters=0
            )

            if not encodings:
                print("⚠️ No face encodings found")
                return None

            print("✅ Face encoding extracted successfully")
            return encodings[0].tolist()

        except ImportError:
            print("⚠️ face_recognition not available")
            return None

        except Exception as e:
            print(f"❌ Face encoding error: {e}")
            return None

    def extract_face_encoding(self, image_data):
        try:
            if isinstance(image_data, np.ndarray):
                if image_data.ndim == 3 and image_data.shape[2] == 3:
                    image_data = image_data[:, :, ::-1]

                img = Image.fromarray(image_data.astype("uint8")).convert("RGB")
                buffer = io.BytesIO()
                img.save(buffer, format="JPEG", quality=90)

                return self.extract_face_encoding_from_bytes(buffer.getvalue())

            elif isinstance(image_data, str):
                if image_data.startswith("data:image"):
                    image_data = image_data.split(",", 1)[1]

                image_bytes = base64.b64decode(image_data)
                return self.extract_face_encoding_from_bytes(image_bytes)

            elif isinstance(image_data, bytes):
                return self.extract_face_encoding_from_bytes(image_data)

            elif isinstance(image_data, list):
                return image_data

            else:
                print(f"⚠️ Unsupported image type: {type(image_data)}")
                return None

        except Exception as e:
            print(f"❌ Error extract_face_encoding: {e}")
            return None

    def add_face_encoding(self, employee_id, encoding):
        self.face_encodings[int(employee_id)] = encoding
        self.save_cache()
        print(f"✅ Added face encoding for employee {employee_id}")

    def process_attendance(self, image_data):
        try:
            print("===== PROCESS ATTENDANCE =====")

            if len(self.face_encodings) == 0:
                print("⚠️ Cache kosong, load ulang dari database")
                self.load_from_database()

            encoding = self.extract_face_encoding(image_data)

            print("Encoding:", "OK" if encoding is not None else "NONE")

            if encoding is None:
                return {
                    "employee_id": None,
                    "message": "Face not detected",
                    "similarity": 0,
                    "liveness_ok": False
                }

            print("Jumlah wajah di cache:", len(self.face_encodings))

            employee_id = None
            best_distance = 999

            for emp_id, cached in self.face_encodings.items():
                distance = np.linalg.norm(
                    np.array(encoding) - np.array(cached)
                )

                print(f"Employee {emp_id} distance = {distance}")

                if distance < best_distance:
                    best_distance = distance
                    employee_id = emp_id

            print("Best distance =", best_distance)

            if employee_id is None or best_distance > 0.6:
                return {
                    "employee_id": None,
                    "message": "Face not recognized",
                    "similarity": 0,
                    "liveness_ok": False
                }

            return {
                "employee_id": int(employee_id),
                "similarity": float(1 - best_distance),
                "liveness_ok": True,
                "message": "Attendance recorded"
            }

        except Exception as e:
            print("❌ Process attendance error:", e)
            raise

    def load_cache(self):
        if os.path.exists(self.face_cache_file):
            try:
                with open(self.face_cache_file, "rb") as f:
                    cache = pickle.load(f)
                    self.face_encodings = cache.get("encodings", {})
                    print(f"📂 Loaded {len(self.face_encodings)} face encodings from cache")
            except Exception as e:
                print(f"⚠️ Error loading cache: {e}")
                self.face_encodings = {}
        else:
            print("📂 No cache file found, starting fresh")

    def save_cache(self):
        try:
            cache = {
                "encodings": self.face_encodings,
                "updated_at": datetime.now().isoformat()
            }

            with open(self.face_cache_file, "wb") as f:
                pickle.dump(cache, f)

            print(f"💾 Saved {len(self.face_encodings)} face encodings to cache")

        except Exception as e:
            print(f"⚠️ Error saving cache: {e}")

    def get_stats(self):
        return {
            "total_encodings": len(self.face_encodings),
            "employee_ids": list(self.face_encodings.keys()),
            "cache_file_exists": os.path.exists(self.face_cache_file)
        }


_face_engine = None


def get_face_engine():
    global _face_engine

    if _face_engine is None:
        _face_engine = FaceEngine()
        print("✅ FaceEngine initialized successfully")

    return _face_engine


def get_face_engine_safe():
    try:
        return get_face_engine()
    except Exception as e:
        print(f"⚠️ Error getting face engine: {e}")
        return None