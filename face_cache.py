import pickle
import os
import json
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional, Any
import threading
from dataclasses import dataclass, asdict
import hashlib

@dataclass
class FaceCacheEntry:
    """Data class for face cache entry"""
    employee_id: int
    encoding: List[float]
    created_at: str
    last_accessed: str
    hash_md5: str
    version: int = 1

class FaceCache:
    """Production-ready face encoding cache manager"""
    
    def __init__(self, cache_file='face_cache.pkl', max_size=1000):
        """
        Initialize Face Cache
        
        Args:
            cache_file: Path to cache file
            max_size: Maximum number of entries to keep in cache
        """
        self.cache_file = cache_file
        self.max_size = max_size
        self.cache: Dict[int, FaceCacheEntry] = {}
        self.lock = threading.RLock()
        self._load_cache()
    
    def _calculate_hash(self, encoding: List[float]) -> str:
        """Calculate MD5 hash of encoding for integrity check"""
        encoding_bytes = np.array(encoding, dtype=np.float32).tobytes()
        return hashlib.md5(encoding_bytes).hexdigest()
    
    def _load_cache(self):
        """Load cache from file with thread safety"""
        with self.lock:
            try:
                if os.path.exists(self.cache_file):
                    with open(self.cache_file, 'rb') as f:
                        data = pickle.load(f)
                        
                        # Handle both old and new format
                        if isinstance(data, dict):
                            if 'cache' in data and 'metadata' in data:
                                # New format
                                cache_data = data['cache']
                                for emp_id, entry_data in cache_data.items():
                                    if isinstance(entry_data, FaceCacheEntry):
                                        self.cache[emp_id] = entry_data
                                    elif isinstance(entry_data, dict):
                                        # Convert dict to FaceCacheEntry
                                        self.cache[emp_id] = FaceCacheEntry(**entry_data)
                            else:
                                # Old format: dict of encodings only
                                for emp_id, encoding in data.items():
                                    entry = FaceCacheEntry(
                                        employee_id=emp_id,
                                        encoding=encoding,
                                        created_at=datetime.now().isoformat(),
                                        last_accessed=datetime.now().isoformat(),
                                        hash_md5=self._calculate_hash(encoding)
                                    )
                                    self.cache[emp_id] = entry
                    
                    print(f"📂 Loaded {len(self.cache)} face encodings from cache")
                    
                    # Clean up old entries if over limit
                    if len(self.cache) > self.max_size:
                        self._cleanup_old_entries()
                        
            except Exception as e:
                print(f"⚠️ Error loading face cache: {e}")
                self.cache = {}
    
    def _save_cache(self):
        """Save cache to file with thread safety"""
        with self.lock:
            try:
                # Prepare data for saving
                cache_data = {}
                for emp_id, entry in self.cache.items():
                    cache_data[emp_id] = asdict(entry)
                
                save_data = {
                    'cache': cache_data,
                    'metadata': {
                        'version': '1.0',
                        'total_entries': len(self.cache),
                        'saved_at': datetime.now().isoformat()
                    }
                }
                
                # Save to file
                with open(self.cache_file, 'wb') as f:
                    pickle.dump(save_data, f)
                    
            except Exception as e:
                print(f"⚠️ Error saving face cache: {e}")
    
    def _cleanup_old_entries(self):
        """Remove least recently accessed entries if over limit"""
        if len(self.cache) <= self.max_size:
            return
        
        # Sort by last accessed time (oldest first)
        sorted_entries = sorted(
            self.cache.items(),
            key=lambda x: x[1].last_accessed
        )
        
        # Remove oldest entries
        entries_to_remove = len(self.cache) - self.max_size
        for i in range(entries_to_remove):
            emp_id, _ = sorted_entries[i]
            del self.cache[emp_id]
        
        print(f"🧹 Cleaned up {entries_to_remove} old entries from cache")
        self._save_cache()
    
    def add(self, employee_id: int, encoding: List[float]) -> bool:
        """
        Add or update face encoding in cache
        
        Args:
            employee_id: Employee ID
            encoding: 128-D face encoding
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Validate encoding
            if not encoding or len(encoding) != 128:
                print(f"⚠️ Invalid encoding length: {len(encoding) if encoding else 0}")
                return False
            
            # Convert to list if numpy array
            if isinstance(encoding, np.ndarray):
                encoding = encoding.tolist()
            
            # Create cache entry
            now = datetime.now().isoformat()
            entry = FaceCacheEntry(
                employee_id=employee_id,
                encoding=encoding,
                created_at=now,
                last_accessed=now,
                hash_md5=self._calculate_hash(encoding)
            )
            
            with self.lock:
                self.cache[employee_id] = entry
                self._save_cache()
            
            print(f"✅ Added face encoding for employee {employee_id}")
            return True
            
        except Exception as e:
            print(f"❌ Error adding face encoding: {e}")
            return False
    
    def get(self, employee_id: int) -> Optional[List[float]]:
        """
        Get face encoding from cache
        
        Args:
            employee_id: Employee ID
            
        Returns:
            Face encoding or None if not found
        """
        with self.lock:
            if employee_id in self.cache:
                entry = self.cache[employee_id]
                
                # Update last accessed time
                entry.last_accessed = datetime.now().isoformat()
                
                # Verify integrity
                current_hash = self._calculate_hash(entry.encoding)
                if current_hash != entry.hash_md5:
                    print(f"⚠️ Hash mismatch for employee {employee_id}, removing corrupted entry")
                    self.remove(employee_id)
                    return None
                
                return entry.encoding.copy()
        
        return None
    
    def remove(self, employee_id: int) -> bool:
        """
        Remove face encoding from cache
        
        Args:
            employee_id: Employee ID to remove
            
        Returns:
            True if removed, False if not found
        """
        with self.lock:
            if employee_id in self.cache:
                del self.cache[employee_id]
                self._save_cache()
                print(f"🗑️ Removed face encoding for employee {employee_id}")
                return True
        
        return False
    
    def update(self, employee_id: int, encoding: List[float]) -> bool:
        """
        Update existing face encoding
        
        Args:
            employee_id: Employee ID
            encoding: New 128-D face encoding
            
        Returns:
            True if updated, False if employee not found
        """
        if employee_id not in self.cache:
            return False
        
        return self.add(employee_id, encoding)
    
    def get_all(self) -> Dict[int, List[float]]:
        """
        Get all face encodings from cache
        Returns: {employee_id: encoding}
        """
        with self.lock:
            result = {}
            for emp_id, entry in self.cache.items():
                result[emp_id] = entry.encoding.copy()
            return result
    
    def get_all_entries(self) -> Dict[int, FaceCacheEntry]:
        """
        Get all cache entries with metadata
        Returns: {employee_id: FaceCacheEntry}
        """
        with self.lock:
            return self.cache.copy()
    
    def exists(self, employee_id: int) -> bool:
        """
        Check if face encoding exists in cache
        
        Args:
            employee_id: Employee ID
            
        Returns:
            True if exists, False otherwise
        """
        with self.lock:
            return employee_id in self.cache
    
    def clear(self):
        """Clear all cached face encodings"""
        with self.lock:
            self.cache.clear()
            if os.path.exists(self.cache_file):
                os.remove(self.cache_file)
            print("🗑️ Cleared all face encodings")
    
    def size(self) -> int:
        """Get number of cached encodings"""
        with self.lock:
            return len(self.cache)
    
    def get_stats(self) -> dict:
        """Get cache statistics"""
        with self.lock:
            now = datetime.now()
            total_size = len(self.cache)
            
            if total_size == 0:
                return {
                    'total_entries': 0,
                    'cache_file_exists': os.path.exists(self.cache_file),
                    'cache_file_size': os.path.getsize(self.cache_file) if os.path.exists(self.cache_file) else 0
                }
            
            # Calculate age statistics
            ages = []
            for entry in self.cache.values():
                created_at = datetime.fromisoformat(entry.created_at)
                age_days = (now - created_at).days
                ages.append(age_days)
            
            # Calculate access recency
            last_accesses = []
            for entry in self.cache.values():
                last_accessed = datetime.fromisoformat(entry.last_accessed)
                days_since_access = (now - last_accessed).days
                last_accesses.append(days_since_access)
            
            return {
                'total_entries': total_size,
                'max_size': self.max_size,
                'cache_file_exists': os.path.exists(self.cache_file),
                'cache_file_size': os.path.getsize(self.cache_file) if os.path.exists(self.cache_file) else 0,
                'age_stats': {
                    'min_days': min(ages) if ages else 0,
                    'max_days': max(ages) if ages else 0,
                    'avg_days': sum(ages) / len(ages) if ages else 0
                },
                'access_stats': {
                    'min_days_since_access': min(last_accesses) if last_accesses else 0,
                    'max_days_since_access': max(last_accesses) if last_accesses else 0,
                    'avg_days_since_access': sum(last_accesses) / len(last_accesses) if last_accesses else 0
                }
            }
    
    def backup(self, backup_path: str = None) -> bool:
        """
        Create backup of cache
        
        Args:
            backup_path: Path for backup file
            
        Returns:
            True if backup successful
        """
        try:
            if backup_path is None:
                backup_dir = os.path.dirname(self.cache_file)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_path = os.path.join(backup_dir, f'face_cache_backup_{timestamp}.pkl')
            
            with self.lock:
                if os.path.exists(self.cache_file):
                    import shutil
                    shutil.copy2(self.cache_file, backup_path)
                    print(f"💾 Cache backed up to: {backup_path}")
                    return True
                else:
                    print("⚠️ No cache file to backup")
                    return False
                    
        except Exception as e:
            print(f"❌ Error backing up cache: {e}")
            return False
    
    def restore(self, backup_path: str) -> bool:
        """
        Restore cache from backup
        
        Args:
            backup_path: Path to backup file
            
        Returns:
            True if restore successful
        """
        try:
            if not os.path.exists(backup_path):
                print(f"❌ Backup file not found: {backup_path}")
                return False
            
            with self.lock:
                # Backup current cache first
                current_backup = self.cache_file + '.pre_restore'
                if os.path.exists(self.cache_file):
                    import shutil
                    shutil.copy2(self.cache_file, current_backup)
                
                # Copy backup to cache file
                import shutil
                shutil.copy2(backup_path, self.cache_file)
                
                # Reload cache
                self._load_cache()
                
                print(f"✅ Cache restored from: {backup_path}")
                if os.path.exists(current_backup):
                    print(f"💾 Previous cache backed up to: {current_backup}")
                
                return True
                
        except Exception as e:
            print(f"❌ Error restoring cache: {e}")
            
            # Try to restore from pre_restore backup
            if os.path.exists(self.cache_file + '.pre_restore'):
                try:
                    import shutil
                    shutil.copy2(self.cache_file + '.pre_restore', self.cache_file)
                    self._load_cache()
                    print("✅ Restored original cache after failed restore attempt")
                except:
                    pass
            
            return False
    
    def validate_all(self) -> Dict[int, bool]:
        """
        Validate integrity of all cache entries
        
        Returns:
            Dictionary of employee_id -> validation result
        """
        results = {}
        with self.lock:
            for emp_id, entry in self.cache.items():
                current_hash = self._calculate_hash(entry.encoding)
                results[emp_id] = current_hash == entry.hash_md5
        
        return results
    
    def cleanup_invalid(self) -> List[int]:
        """
        Remove invalid/corrupted entries from cache
        
        Returns:
            List of removed employee IDs
        """
        removed = []
        with self.lock:
            entries_to_remove = []
            
            for emp_id, entry in self.cache.items():
                current_hash = self._calculate_hash(entry.encoding)
                if current_hash != entry.hash_md5:
                    entries_to_remove.append(emp_id)
            
            for emp_id in entries_to_remove:
                del self.cache[emp_id]
                removed.append(emp_id)
            
            if removed:
                self._save_cache()
                print(f"🧹 Removed {len(removed)} invalid entries: {removed}")    
        return removed

# Global instance for easy import
face_cache = FaceCache()

# Export for backward compatibility
__all__ = ['FaceCache', 'FaceCacheEntry', 'face_cache']