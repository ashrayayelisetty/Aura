"""
Identity Agent for AURA-VIP Orchestration System.

This module implements face recognition and VIP identification.
Validates Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 18.2, 18.4
"""

import asyncio
import logging
import os
import pickle
from datetime import datetime, timezone
from typing import Optional, Tuple

import cv2
import numpy as np
from deepface import DeepFace

from backend.models.schemas import Event, EventType
from backend.orchestrator.event_bus import EventBus
from backend.database.connection import SessionLocal
from backend.database.models import VIPProfileDB

logger = logging.getLogger(__name__)


class IdentityAgent:
    """
    Identity Agent responsible for face recognition and VIP identification.
    
    Responsibilities:
    - Capture faces from camera feed using OpenCV
    - Extract face embeddings using DeepFace
    - Match embeddings against stored VIP profiles
    - Emit VIP_DETECTED event when confidence exceeds threshold
    """
    
    def __init__(self, event_bus: EventBus):
        """
        Initialize the Identity Agent.
        
        Args:
            event_bus: The event bus for publishing events
        """
        self.event_bus = event_bus
        self.confidence_threshold = float(os.getenv("FACE_CONFIDENCE_THRESHOLD", "0.85"))
        self.model_name = os.getenv("FACE_RECOGNITION_MODEL", "VGG-Face")
        self.frame_rate = int(os.getenv("FRAME_PROCESSING_RATE", "2"))
        self.camera_width = int(os.getenv("CAMERA_RESOLUTION_WIDTH", "640"))
        self.camera_height = int(os.getenv("CAMERA_RESOLUTION_HEIGHT", "480"))
        
        # Camera will be initialized when process_camera_feed is called
        self.camera = None
        self._running = False
        
        logger.info(
            f"Identity Agent initialized with threshold={self.confidence_threshold}, "
            f"model={self.model_name}, frame_rate={self.frame_rate} FPS"
        )
    
    async def extract_embedding(self, face_image: np.ndarray) -> np.ndarray:
        """
        Extract face embedding using DeepFace with VGG-Face backend.
        
        Args:
            face_image: Face image as numpy array (BGR format from OpenCV)
        
        Returns:
            Face embedding as numpy array (128-dimensional vector)
        
        Raises:
            ValueError: If no face is detected in the image
        
        Validates: Requirement 1.1
        """
        try:
            # DeepFace.represent returns a list of embeddings (one per face)
            # We use enforce_detection=True to ensure a face is present
            embeddings = DeepFace.represent(
                img_path=face_image,
                model_name=self.model_name,
                enforce_detection=True,
                detector_backend="opencv"
            )
            
            if not embeddings or len(embeddings) == 0:
                raise ValueError("No face detected in image")
            
            # Get the first face embedding
            embedding = np.array(embeddings[0]["embedding"])
            
            logger.debug(f"Extracted embedding with shape {embedding.shape}")
            return embedding
            
        except Exception as e:
            logger.error(f"Failed to extract embedding: {e}")
            raise ValueError(f"Face embedding extraction failed: {e}")
    
    async def match_vip(self, embedding: np.ndarray) -> Tuple[Optional[str], float]:
        """
        Match embedding against stored VIP profiles using cosine similarity.
        
        Args:
            embedding: Face embedding to match
        
        Returns:
            Tuple of (vip_id, confidence) where vip_id is None if no match found
        
        Validates: Requirement 1.2
        """
        try:
            db = SessionLocal()
            try:
                # Get all VIP profiles from database
                vip_profiles = db.query(VIPProfileDB).all()
                
                if not vip_profiles:
                    logger.warning("No VIP profiles in database")
                    return None, 0.0
                
                best_match_id = None
                best_confidence = 0.0
                
                # Compare against each VIP profile
                for vip in vip_profiles:
                    # Deserialize the stored embedding
                    stored_embedding = pickle.loads(vip.face_embedding)
                    
                    # Calculate cosine similarity
                    confidence = self._cosine_similarity(embedding, stored_embedding)
                    
                    logger.debug(f"VIP {vip.name} (ID: {vip.id}): confidence={confidence:.4f}")
                    
                    # Track best match
                    if confidence > best_confidence:
                        best_confidence = confidence
                        best_match_id = vip.id
                
                logger.info(
                    f"Best match: VIP ID={best_match_id}, confidence={best_confidence:.4f}"
                )
                
                return best_match_id, best_confidence
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Failed to match VIP: {e}", exc_info=True)
            return None, 0.0
    
    def _cosine_similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """
        Calculate cosine similarity between two embeddings.
        
        Args:
            embedding1: First embedding
            embedding2: Second embedding
        
        Returns:
            Cosine similarity score (0.0 to 1.0)
        """
        # Normalize embeddings
        embedding1_norm = embedding1 / np.linalg.norm(embedding1)
        embedding2_norm = embedding2 / np.linalg.norm(embedding2)
        
        # Calculate cosine similarity
        similarity = np.dot(embedding1_norm, embedding2_norm)
        
        # Convert to 0-1 range (cosine similarity is -1 to 1)
        similarity = (similarity + 1) / 2
        
        return float(similarity)
    
    async def process_camera_feed(self) -> None:
        """
        Continuous camera monitoring loop.
        
        Processes frames at the configured frame rate (default 2 FPS).
        Emits VIP_DETECTED event when confidence exceeds threshold.
        Logs failed recognition attempts without triggering services.
        
        Validates: Requirements 1.3, 1.4, 1.5
        """
        logger.info("Starting camera feed processing")
        
        # Initialize camera
        self.camera = cv2.VideoCapture(0)
        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, self.camera_width)
        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, self.camera_height)
        
        if not self.camera.isOpened():
            logger.error("Failed to open camera")
            return
        
        self._running = True
        frame_delay = 1.0 / self.frame_rate  # Delay between frames
        
        try:
            while self._running:
                # Capture frame
                ret, frame = self.camera.read()
                
                if not ret:
                    logger.warning("Failed to capture frame")
                    await asyncio.sleep(frame_delay)
                    continue
                
                try:
                    # Extract embedding from frame
                    embedding = await self.extract_embedding(frame)
                    
                    # Match against VIP profiles
                    vip_id, confidence = await self.match_vip(embedding)
                    
                    # Check confidence threshold
                    if vip_id and confidence >= self.confidence_threshold:
                        # Emit VIP_DETECTED event
                        event = Event(
                            event_type=EventType.VIP_DETECTED,
                            payload={
                                "vip_id": vip_id,
                                "confidence": confidence,
                                "timestamp": datetime.now(timezone.utc).isoformat()
                            },
                            source_agent="identity_agent",
                            vip_id=vip_id
                        )
                        
                        await self.event_bus.publish(event)
                        
                        logger.info(
                            f"VIP detected: ID={vip_id}, confidence={confidence:.4f}"
                        )
                    else:
                        # Log failed recognition attempt
                        logger.info(
                            f"Face detected but confidence below threshold: "
                            f"vip_id={vip_id}, confidence={confidence:.4f}, "
                            f"threshold={self.confidence_threshold}"
                        )
                
                except ValueError as e:
                    # No face detected or extraction failed
                    logger.debug(f"Face detection/extraction failed: {e}")
                
                except Exception as e:
                    logger.error(f"Error processing frame: {e}", exc_info=True)
                
                # Wait before processing next frame
                await asyncio.sleep(frame_delay)
        
        finally:
            # Clean up camera
            if self.camera:
                self.camera.release()
                logger.info("Camera released")
    
    def stop(self) -> None:
        """Stop the camera feed processing loop."""
        logger.info("Stopping camera feed processing")
        self._running = False
