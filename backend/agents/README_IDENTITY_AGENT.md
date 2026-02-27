# Identity Agent Implementation

## Overview

The Identity Agent is responsible for face recognition and VIP identification in the AURA-VIP system. It uses DeepFace with VGG-Face backend for face embedding extraction and cosine similarity for matching against stored VIP profiles.

## Implementation Details

### Requirements Validated

- **Requirement 1.1**: Extract face embeddings using DeepFace
- **Requirement 1.2**: Compare embeddings against stored VIP profiles
- **Requirement 1.3**: Emit VIP_DETECTED event when confidence exceeds threshold
- **Requirement 1.4**: Broadcast events through Event Bus
- **Requirement 1.5**: Log failed recognition attempts without triggering services
- **Requirement 18.2**: Subscribe to Event Bus during initialization
- **Requirement 18.4**: Execute event handlers asynchronously

### Key Features

1. **Face Embedding Extraction** (`extract_embedding`)
   - Uses DeepFace with VGG-Face backend
   - Returns 128-dimensional embedding vector
   - Enforces face detection (raises error if no face found)
   - Uses OpenCV detector backend for consistency

2. **VIP Matching** (`match_vip`)
   - Compares input embedding against all stored VIP profiles
   - Uses cosine similarity for matching
   - Returns best match VIP ID and confidence score
   - Handles empty database gracefully

3. **Confidence Threshold Check**
   - Default threshold: 0.85 (configurable via environment variable)
   - Only emits VIP_DETECTED event if confidence >= threshold
   - Logs failed attempts for audit trail

4. **Camera Feed Processing** (`process_camera_feed`)
   - Processes frames at 2 FPS (configurable)
   - Continuous monitoring loop
   - Emits VIP_DETECTED events when VIP identified
   - Graceful error handling for camera failures

5. **Cosine Similarity Calculation** (`_cosine_similarity`)
   - Normalizes embeddings before comparison
   - Returns similarity score in range [0.0, 1.0]
   - Higher score indicates better match

## Configuration

The agent reads configuration from environment variables:

```env
FACE_CONFIDENCE_THRESHOLD=0.85
FACE_RECOGNITION_MODEL=VGG-Face
CAMERA_RESOLUTION_WIDTH=640
CAMERA_RESOLUTION_HEIGHT=480
FRAME_PROCESSING_RATE=2
```

## Usage Example

```python
from backend.agents.identity_agent import IdentityAgent
from backend.orchestrator.event_bus import EventBus

# Initialize event bus
event_bus = EventBus()

# Create identity agent
identity_agent = IdentityAgent(event_bus)

# Start camera feed processing (runs continuously)
await identity_agent.process_camera_feed()

# Stop processing when done
identity_agent.stop()
```

## Event Emission

When a VIP is detected with confidence above threshold, the agent emits:

```python
Event(
    event_type=EventType.VIP_DETECTED,
    payload={
        "vip_id": "vip-uuid",
        "confidence": 0.95,
        "timestamp": "2024-01-01T12:00:00Z"
    },
    source_agent="identity_agent",
    vip_id="vip-uuid"
)
```

## Database Integration

The agent queries VIP profiles from the database:

- Reads from `vip_profiles` table
- Deserializes face embeddings (stored as pickled numpy arrays)
- Compares against all profiles to find best match

## Error Handling

1. **No face detected**: Logs debug message, continues processing
2. **DeepFace extraction failure**: Logs error, continues processing
3. **Database query failure**: Logs error, returns None match
4. **Camera initialization failure**: Logs error, exits gracefully
5. **Frame capture failure**: Logs warning, continues processing

## Testing

### Basic Tests (No DeepFace Required)

Run basic structure tests:

```bash
pytest backend/tests/test_identity_agent_basic.py -v
```

### Full Tests (Requires DeepFace)

Install dependencies first:

```bash
pip install -r backend/requirements.txt
```

Then run full tests:

```bash
pytest backend/tests/test_identity_agent.py -v
```

## Dependencies

- **opencv-python**: Camera capture and image processing
- **deepface**: Face recognition and embedding extraction
- **numpy**: Numerical operations for embeddings
- **sqlalchemy**: Database queries
- **asyncio**: Asynchronous processing

## Performance Considerations

1. **Frame Rate**: Set to 2 FPS to reduce CPU load
2. **Embedding Extraction**: ~100-200ms per frame (depends on hardware)
3. **VIP Matching**: O(n) where n = number of VIP profiles
4. **Memory**: Minimal, embeddings are 128 floats (~1KB each)

## Future Enhancements

1. **GPU Acceleration**: Use GPU for faster embedding extraction
2. **Caching**: Cache embeddings to reduce database queries
3. **Batch Processing**: Process multiple faces in single frame
4. **Face Tracking**: Track faces across frames to reduce redundant processing
5. **Quality Checks**: Verify face image quality before extraction
