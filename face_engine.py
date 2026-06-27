import face_recognition
import numpy as np
import pickle
import os
from datetime import datetime
from PIL import Image
import io
import base64

class FaceEngine:
    """Face recognition engine using face_recognition library (no OpenCV/MediaPipe)"""
    
    def __init__(self):
        self.face_encodings = {}
        self.face_cache_file = 'face_cache.pkl'
        self.load_cache()
        print(f"✅ FaceEngine initialized with {len(self.face_encodings)} face encodings")
    
    def extract_face_encoding_from_bytes(self, image_bytes):
        """Extract face encoding from image bytes using face_recognition"""
        try:
            # Load image from bytes
            img = Image.open(io.BytesIO(image_bytes))
            
            # Convert to RGB if needed
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Convert to numpy array
            img_np = np.array(img)
            
            # Find face locations
            face_locations = face_recognition.face_locations(img_np)
            
            if not face_locations:
                return None
            
            # Get face encodings
            encodings = face_recognition.face_encodings(img_np, face_locations)
            
            if not encodings:
                return None
            
            return encodings[0].tolist()
            
        except Exception as e:
            print(f"Error extracting face encoding: {e}")
            return None
    
    def extract_face_encoding(self, image_data):
        """Extract face encoding from various input formats"""
        try:
            # If it's base64 string
            if isinstance(image_data, str):
                if image_data.startswith('data:image'):
                    image_data = image_data.split(',')[1]
                image_bytes = base64.b64decode(image_data)
                return self.extract_face_encoding_from_bytes(image_bytes)
            
            # If it's bytes
            elif isinstance(image_data, bytes):
                return self.extract_face_encoding_from_bytes(image_data)
            
            # If it's already a list (encoding)
            elif isinstance(image_data, list):
                return image_data
            
            else:
                print(f"Unsupported image data type: {type(image_data)}")
                return None
                
        except Exception as e:
            print(f"Error in extract_face_encoding: {e}")
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
            
            # Compare with cached encodings
            best_match = None
            best_distance = float('inf')
            
            for emp_id, cached_encoding in self.face_encodings.items():
                distance = np.linalg.norm(np.array(encoding) - np.array(cached_encoding))
                
                if distance < 0.6 and distance < best_distance:
                    best_match = emp_id
                    best_distance = distance
            
            return best_match
            
        except Exception as e:
            print(f"Error finding face: {e}")
            return None
    
    def process_attendance(self, image_data):
        """Process attendance with face recognition"""
        try:
            # Extract face encoding
            encoding = self.extract_face_encoding(image_data)
            
            if encoding is None:
                return {
                    'employee_id': None,
                    'similarity': 0.0,
                    'liveness_ok': False,
                    'message': 'Face not detected'
                }
            
            # Find matching employee
            employee_id = None
            best_distance = float('inf')
            
            for emp_id, cached_encoding in self.face_encodings.items():
                distance = np.linalg.norm(np.array(encoding) - np.array(cached_encoding))
                
                if distance < 0.6 and distance < best_distance:
                    employee_id = emp_id
                    best_distance = distance
            
            if employee_id is None:
                return {
                    'employee_id': None,
                    'similarity': 0.0,
                    'liveness_ok': False,
                    'message': 'Face not recognized'
                }
            
            return {
                'employee_id': employee_id,
                'similarity': 1.0 - best_distance,
                'liveness_ok': True,
                'message': 'Attendance recorded'
            }
            
        except Exception as e:
            print(f"Error processing attendance: {e}")
            return {
                'employee_id': None,
                'similarity': 0.0,
                'liveness_ok': False,
                'message': f'Error: {str(e)}'
            }
    
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
            'employee_ids': list(self.face_encodings.keys())
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