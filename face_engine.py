import os
import io
import base64
import pickle
import numpy as np
from datetime import datetime
from PIL import Image

class FaceEngine:
    """Face recognition engine with fallback for headless environments"""
    
    def __init__(self):
        self.face_encodings = {}
        self.face_cache_file = 'face_cache.pkl'
        self.load_cache()
        print(f"✅ FaceEngine initialized with {len(self.face_encodings)} face encodings")
    
    def extract_face_encoding_from_bytes(self, image_bytes):
        """Extract face encoding from image bytes"""
        try:
            # Try to use face_recognition if available
            try:
                import face_recognition
                
                # Load image from bytes
                img = Image.open(io.BytesIO(image_bytes))
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                img_np = np.array(img)
                
                # Find face locations
                face_locations = face_recognition.face_locations(img_np)
                
                if not face_locations:
                    print("⚠️ No face locations found")
                    return None
                
                # Get face encodings
                encodings = face_recognition.face_encodings(img_np, face_locations)
                
                if not encodings:
                    print("⚠️ No face encodings found")
                    return None
                
                print("✅ Face encoding extracted successfully")
                return encodings[0].tolist()
                
            except ImportError:
                print("⚠️ face_recognition not available, using fallback method")
                return self._extract_face_encoding_fallback(image_bytes)
            except Exception as e:
                print(f"⚠️ face_recognition error: {e}, using fallback")
                return self._extract_face_encoding_fallback(image_bytes)
            
        except Exception as e:
            print(f"❌ Error extracting face encoding: {e}")
            return None
    
    def _extract_face_encoding_fallback(self, image_bytes):
        """Fallback method using simple image features"""
        try:
            # Load image
            img = Image.open(io.BytesIO(image_bytes))
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Resize for faster processing
            img.thumbnail((300, 300))
            img_np = np.array(img)
            
            # Extract simple features
            features = []
            
            # Color statistics
            for channel in range(3):
                channel_data = img_np[:, :, channel].flatten()
                features.extend([
                    float(np.mean(channel_data)),
                    float(np.std(channel_data)),
                    float(np.median(channel_data)),
                    float(np.percentile(channel_data, 25)),
                    float(np.percentile(channel_data, 75))
                ])
            
            # Texture features (simple gradient)
            if img_np.shape[0] > 1 and img_np.shape[1] > 1:
                for channel in range(3):
                    grad_y = np.diff(img_np[:, :, channel], axis=0)
                    grad_x = np.diff(img_np[:, :, channel], axis=1)
                    if grad_y.size > 0:
                        features.append(float(np.mean(np.abs(grad_y))))
                        features.append(float(np.std(grad_y)))
                    if grad_x.size > 0:
                        features.append(float(np.mean(np.abs(grad_x))))
                        features.append(float(np.std(grad_x)))
            
            # Pad to 128 dimensions
            while len(features) < 128:
                features.append(0.0)
            
            # Truncate to 128 dimensions
            features = features[:128]
            
            print(f"✅ Fallback encoding created ({len(features)} dimensions)")
            return features
            
        except Exception as e:
            print(f"❌ Fallback encoding failed: {e}")
            return None
    
    def extract_face_encoding(self, image_data):
        """Extract face encoding from various input formats"""
        try:
            # OpenCV image (numpy array)
            if isinstance(image_data, np.ndarray):
                img = Image.fromarray(image_data)
                buffer = io.BytesIO()
                img.save(buffer, format="JPEG")
                return self.extract_face_encoding_from_bytes(buffer.getvalue())

            # Base64 string
            elif isinstance(image_data, str):
                if image_data.startswith("data:image"):
                    image_data = image_data.split(",")[1]
                image_bytes = base64.b64decode(image_data)
                return self.extract_face_encoding_from_bytes(image_bytes)

            # Raw bytes
            elif isinstance(image_data, bytes):
                return self.extract_face_encoding_from_bytes(image_data)

            # Already encoding
            elif isinstance(image_data, list):
                return image_data

            else:
                print(f"⚠️ Unsupported image type: {type(image_data)}")
                return None

        except Exception as e:
            print(f"❌ Error extract_face_encoding: {e}")
            return None
    
    def add_face_encoding(self, employee_id, encoding):
        """Add face encoding to cache"""
        self.face_encodings[employee_id] = encoding
        self.save_cache()
        print(f"✅ Added face encoding for employee {employee_id}")
    
    def find_face(self, image_data):
        """Find matching face in cache"""
        try:
            encoding = self.extract_face_encoding(image_data)
            
            if encoding is None:
                return None
            
            best_match = None
            best_distance = float('inf')
            
            for emp_id, cached_encoding in self.face_encodings.items():
                distance = np.linalg.norm(np.array(encoding) - np.array(cached_encoding))
                
                if distance < 0.6 and distance < best_distance:
                    best_match = emp_id
                    best_distance = distance
            
            return best_match
            
        except Exception as e:
            print(f"❌ Error finding face: {e}")
            return None
    
    def process_attendance(self, image_data):
        try:
            print("===== PROCESS ATTENDANCE =====")

            encoding = self.extract_face_encoding(image_data)

            if encoding is None:
                print("Encoding gagal")
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

            if best_distance > 0.6:
                print("Face not recognized")
            return {
                "employee_id": None,
                "message": "Face not recognized",
                "similarity": 0,
                "liveness_ok": False
            }

            print("Matched employee =", employee_id)

            return {
            "employee_id": employee_id,
            "similarity": 1 - best_distance,
            "liveness_ok": True
        }

        except Exception as e:
            print(e)
        raise
    
    def load_cache(self):
        """Load face cache from file"""
        if os.path.exists(self.face_cache_file):
            try:
                with open(self.face_cache_file, 'rb') as f:
                    cache = pickle.load(f)
                    self.face_encodings = cache.get('encodings', {})
                    print(f"📂 Loaded {len(self.face_encodings)} face encodings from cache")
            except Exception as e:
                print(f"⚠️ Error loading cache: {e}")
                self.face_encodings = {}
        else:
            print("📂 No cache file found, starting fresh")
    
    def save_cache(self):
        """Save face cache to file"""
        try:
            cache = {
                'encodings': self.face_encodings,
                'updated_at': datetime.now().isoformat()
            }
            with open(self.face_cache_file, 'wb') as f:
                pickle.dump(cache, f)
            print(f"💾 Saved {len(self.face_encodings)} face encodings to cache")
        except Exception as e:
            print(f"⚠️ Error saving cache: {e}")
    
    def get_stats(self):
        """Get cache statistics"""
        return {
            'total_encodings': len(self.face_encodings),
            'employee_ids': list(self.face_encodings.keys()),
            'cache_file_exists': os.path.exists(self.face_cache_file)
        }

# Singleton instance
_face_engine = None

def get_face_engine():
    global _face_engine
    if _face_engine is None:
        try:
            _face_engine = FaceEngine()
            print("✅ FaceEngine initialized successfully")
        except Exception as e:
            print(f"❌ Failed to initialize FaceEngine: {e}")
            _face_engine = None
    return _face_engine

def get_face_engine_safe():
    """Get FaceEngine safely"""
    try:
        return get_face_engine()
    except Exception as e:
        print(f"⚠️ Error getting face engine: {e}")
        return None