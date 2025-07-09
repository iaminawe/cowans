#!/usr/bin/env python3
"""
SPARC Memory Coordination System

Provides distributed memory management and session coordination for SPARC orchestrator.
Built on existing Redis patterns from the Cowans infrastructure.
"""

import json
import time
import uuid
import redis
import pickle
import threading
from typing import Dict, Any, Optional, List, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import logging
from contextlib import contextmanager


class SPARCMemoryEventType(Enum):
    SESSION_CREATED = "session_created"
    SESSION_UPDATED = "session_updated"
    TASK_ASSIGNED = "task_assigned"
    TASK_COMPLETED = "task_completed"
    AGENT_REGISTERED = "agent_registered"
    AGENT_HEARTBEAT = "agent_heartbeat"
    CONTEXT_UPDATED = "context_updated"


@dataclass
class SPARCMemoryEvent:
    id: str
    type: SPARCMemoryEventType
    session_id: str
    timestamp: datetime
    data: Dict[str, Any]
    source_agent: Optional[str] = None
    
    def __post_init__(self):
        if isinstance(self.timestamp, str):
            self.timestamp = datetime.fromisoformat(self.timestamp)


class SPARCMemoryCoordinator:
    """
    SPARC Memory Coordinator - Manages distributed memory and session coordination
    
    Features:
    - Distributed session state management
    - Real-time event streaming
    - Shared context coordination
    - Agent registration and discovery
    - Memory cleanup and optimization
    """
    
    def __init__(self, redis_client: redis.Redis, namespace: str = "sparc", 
                 event_ttl: int = 3600, session_ttl: int = 7200):
        self.redis = redis_client
        self.namespace = namespace
        self.event_ttl = event_ttl
        self.session_ttl = session_ttl
        self.logger = self._setup_logging()
        self.event_handlers: Dict[SPARCMemoryEventType, List[callable]] = {}
        self.pubsub = self.redis.pubsub()
        self._listening = False
        self._listener_thread = None
        
        # Initialize memory structure
        self._initialize_memory_structure()
        
        # Start event listener
        self.start_event_listener()
    
    def _setup_logging(self) -> logging.Logger:
        logger = logging.getLogger("sparc_memory")
        logger.setLevel(logging.INFO)
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        return logger
    
    def _initialize_memory_structure(self):
        """Initialize Redis key structure for SPARC"""
        # Create indexes if they don't exist
        self.redis.sadd(f"{self.namespace}:indexes", "sessions", "agents", "tasks", "events")
    
    def _key(self, *parts) -> str:
        """Generate namespaced Redis key"""
        return f"{self.namespace}:{':'.join(str(p) for p in parts)}"
    
    # Session Management
    def create_session(self, session_id: str, session_data: Dict[str, Any]) -> bool:
        """Create a new session in memory"""
        try:
            session_key = self._key("session", session_id)
            
            # Store main session data
            session_json = json.dumps(session_data, default=str)
            self.redis.setex(session_key, self.session_ttl, session_json)
            
            # Add to session index
            self.redis.sadd(self._key("sessions"), session_id)
            
            # Create session-specific structures
            self._create_session_structures(session_id)
            
            # Emit event
            self._emit_event(SPARCMemoryEventType.SESSION_CREATED, session_id, {"session_data": session_data})
            
            self.logger.info(f"Created session in memory: {session_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to create session {session_id}: {e}")
            return False
    
    def _create_session_structures(self, session_id: str):
        """Create Redis structures for a session"""
        # Task queue for the session
        self.redis.delete(self._key("session", session_id, "task_queue"))
        
        # Agent assignments
        self.redis.delete(self._key("session", session_id, "agents"))
        
        # Shared context
        self.redis.hset(self._key("session", session_id, "context"), "created", datetime.now().isoformat())
        
        # Progress tracking
        progress_data = {
            "total_tasks": 0,
            "completed_tasks": 0,
            "failed_tasks": 0,
            "completion_percentage": 0.0,
            "started_at": datetime.now().isoformat()
        }
        self.redis.hset(self._key("session", session_id, "progress"), mapping=progress_data)
    
    def update_session(self, session_id: str, updates: Dict[str, Any]) -> bool:
        """Update session data"""
        try:
            session_key = self._key("session", session_id)
            
            # Get current data
            current_data = self.get_session(session_id)
            if not current_data:
                return False
            
            # Apply updates
            current_data.update(updates)
            
            # Store updated data
            session_json = json.dumps(current_data, default=str)
            self.redis.setex(session_key, self.session_ttl, session_json)
            
            # Emit event
            self._emit_event(SPARCMemoryEventType.SESSION_UPDATED, session_id, {"updates": updates})
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to update session {session_id}: {e}")
            return False
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session data"""
        try:
            session_key = self._key("session", session_id)
            session_json = self.redis.get(session_key)
            
            if session_json:
                return json.loads(session_json)
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to get session {session_id}: {e}")
            return None
    
    def list_sessions(self, status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all sessions with optional status filter"""
        try:
            session_ids = self.redis.smembers(self._key("sessions"))
            sessions = []
            
            for session_id in session_ids:
                session_data = self.get_session(session_id.decode() if isinstance(session_id, bytes) else session_id)
                if session_data:
                    if not status_filter or session_data.get("status") == status_filter:
                        sessions.append(session_data)
            
            return sessions
            
        except Exception as e:
            self.logger.error(f"Failed to list sessions: {e}")
            return []
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a session and all related data"""
        try:
            # Delete main session data
            self.redis.delete(self._key("session", session_id))
            
            # Delete session structures
            self.redis.delete(self._key("session", session_id, "task_queue"))
            self.redis.delete(self._key("session", session_id, "agents"))
            self.redis.delete(self._key("session", session_id, "context"))
            self.redis.delete(self._key("session", session_id, "progress"))
            
            # Remove from index
            self.redis.srem(self._key("sessions"), session_id)
            
            self.logger.info(f"Deleted session: {session_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to delete session {session_id}: {e}")
            return False
    
    # Shared Context Management
    def set_shared_context(self, session_id: str, key: str, value: Any) -> bool:
        """Set a value in shared context"""
        try:
            context_key = self._key("session", session_id, "context")
            
            # Serialize complex objects
            if isinstance(value, (dict, list)):
                value = json.dumps(value, default=str)
            
            self.redis.hset(context_key, key, value)
            self.redis.expire(context_key, self.session_ttl)
            
            # Emit event
            self._emit_event(SPARCMemoryEventType.CONTEXT_UPDATED, session_id, 
                           {"key": key, "value": value})
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to set context {key} for session {session_id}: {e}")
            return False
    
    def get_shared_context(self, session_id: str, key: Optional[str] = None) -> Any:
        """Get shared context value(s)"""
        try:
            context_key = self._key("session", session_id, "context")
            
            if key:
                value = self.redis.hget(context_key, key)
                if value:
                    value = value.decode() if isinstance(value, bytes) else value
                    try:
                        return json.loads(value)
                    except (json.JSONDecodeError, TypeError):
                        return value
                return None
            else:
                # Get all context
                context = self.redis.hgetall(context_key)
                result = {}
                for k, v in context.items():
                    k = k.decode() if isinstance(k, bytes) else k
                    v = v.decode() if isinstance(v, bytes) else v
                    try:
                        result[k] = json.loads(v)
                    except (json.JSONDecodeError, TypeError):
                        result[k] = v
                return result
                
        except Exception as e:
            self.logger.error(f"Failed to get context for session {session_id}: {e}")
            return None
    
    def update_shared_context(self, session_id: str, updates: Dict[str, Any]) -> bool:
        """Update multiple context values"""
        try:
            for key, value in updates.items():
                self.set_shared_context(session_id, key, value)
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to update context for session {session_id}: {e}")
            return False
    
    # Agent Registration and Discovery
    def register_agent(self, session_id: str, agent_id: str, agent_data: Dict[str, Any]) -> bool:
        """Register an agent for a session"""
        try:
            agent_key = self._key("session", session_id, "agent", agent_id)
            
            # Add registration timestamp
            agent_data["registered_at"] = datetime.now().isoformat()
            agent_data["last_heartbeat"] = datetime.now().isoformat()
            
            # Store agent data
            agent_json = json.dumps(agent_data, default=str)
            self.redis.setex(agent_key, self.session_ttl, agent_json)
            
            # Add to session agents set
            self.redis.sadd(self._key("session", session_id, "agents"), agent_id)
            
            # Emit event
            self._emit_event(SPARCMemoryEventType.AGENT_REGISTERED, session_id, 
                           {"agent_id": agent_id, "agent_data": agent_data})
            
            self.logger.info(f"Registered agent {agent_id} for session {session_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to register agent {agent_id}: {e}")
            return False
    
    def update_agent_heartbeat(self, session_id: str, agent_id: str, 
                              status_data: Dict[str, Any] = None) -> bool:
        """Update agent heartbeat and status"""
        try:
            agent_key = self._key("session", session_id, "agent", agent_id)
            
            # Get current agent data
            agent_json = self.redis.get(agent_key)
            if not agent_json:
                return False
            
            agent_data = json.loads(agent_json)
            
            # Update heartbeat
            agent_data["last_heartbeat"] = datetime.now().isoformat()
            
            # Update status if provided
            if status_data:
                agent_data.update(status_data)
            
            # Store updated data
            agent_json = json.dumps(agent_data, default=str)
            self.redis.setex(agent_key, self.session_ttl, agent_json)
            
            # Emit event
            self._emit_event(SPARCMemoryEventType.AGENT_HEARTBEAT, session_id, 
                           {"agent_id": agent_id, "status": status_data or {}})
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to update heartbeat for agent {agent_id}: {e}")
            return False
    
    def get_session_agents(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all agents for a session"""
        try:
            agent_ids = self.redis.smembers(self._key("session", session_id, "agents"))
            agents = []
            
            for agent_id in agent_ids:
                agent_id_str = agent_id.decode() if isinstance(agent_id, bytes) else agent_id
                agent_key = self._key("session", session_id, "agent", agent_id_str)
                agent_json = self.redis.get(agent_key)
                
                if agent_json:
                    agent_data = json.loads(agent_json)
                    agents.append(agent_data)
            
            return agents
            
        except Exception as e:
            self.logger.error(f"Failed to get agents for session {session_id}: {e}")
            return []
    
    def find_available_agents(self, session_id: str, capabilities: List[str] = None) -> List[Dict[str, Any]]:
        """Find available agents with optional capability filtering"""
        try:
            agents = self.get_session_agents(session_id)
            available_agents = []
            
            for agent in agents:
                # Check if agent is available (idle status and recent heartbeat)
                if agent.get("status") == "idle":
                    # Check heartbeat recency (within last 60 seconds)
                    last_heartbeat = datetime.fromisoformat(agent.get("last_heartbeat", "1970-01-01"))
                    if datetime.now() - last_heartbeat < timedelta(seconds=60):
                        # Check capabilities if specified
                        if not capabilities:
                            available_agents.append(agent)
                        else:
                            agent_capabilities = agent.get("capabilities", [])
                            if any(cap in agent_capabilities for cap in capabilities):
                                available_agents.append(agent)
            
            return available_agents
            
        except Exception as e:
            self.logger.error(f"Failed to find available agents for session {session_id}: {e}")
            return []
    
    # Progress Tracking
    def update_progress(self, session_id: str, progress_data: Dict[str, Any]) -> bool:
        """Update session progress"""
        try:
            progress_key = self._key("session", session_id, "progress")
            
            # Get current progress
            current_progress = self.redis.hgetall(progress_key)
            
            # Update with new data
            for key, value in progress_data.items():
                self.redis.hset(progress_key, key, str(value))
            
            # Set expiration
            self.redis.expire(progress_key, self.session_ttl)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to update progress for session {session_id}: {e}")
            return False
    
    def get_progress(self, session_id: str) -> Dict[str, Any]:
        """Get session progress"""
        try:
            progress_key = self._key("session", session_id, "progress")
            progress_data = self.redis.hgetall(progress_key)
            
            # Convert bytes to strings and parse numbers
            result = {}
            for key, value in progress_data.items():
                key_str = key.decode() if isinstance(key, bytes) else key
                value_str = value.decode() if isinstance(value, bytes) else value
                
                # Try to parse as number
                try:
                    if '.' in value_str:
                        result[key_str] = float(value_str)
                    else:
                        result[key_str] = int(value_str)
                except ValueError:
                    result[key_str] = value_str
            
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to get progress for session {session_id}: {e}")
            return {}
    
    # Event System
    def _emit_event(self, event_type: SPARCMemoryEventType, session_id: str, 
                   data: Dict[str, Any], source_agent: str = None):
        """Emit a memory event"""
        try:
            event = SPARCMemoryEvent(
                id=str(uuid.uuid4()),
                type=event_type,
                session_id=session_id,
                timestamp=datetime.now(),
                data=data,
                source_agent=source_agent
            )
            
            # Store event
            event_key = self._key("event", event.id)
            event_json = json.dumps(asdict(event), default=str)
            self.redis.setex(event_key, self.event_ttl, event_json)
            
            # Add to session events
            self.redis.lpush(self._key("session", session_id, "events"), event.id)
            self.redis.ltrim(self._key("session", session_id, "events"), 0, 999)  # Keep last 1000 events
            
            # Publish to channel
            channel = self._key("events", session_id)
            self.redis.publish(channel, event_json)
            
        except Exception as e:
            self.logger.error(f"Failed to emit event {event_type}: {e}")
    
    def subscribe_to_events(self, session_id: str, event_handler: callable):
        """Subscribe to events for a session"""
        channel = self._key("events", session_id)
        self.pubsub.subscribe(channel)
        
        # Add to handlers
        if SPARCMemoryEventType.SESSION_UPDATED not in self.event_handlers:
            self.event_handlers[SPARCMemoryEventType.SESSION_UPDATED] = []
        self.event_handlers[SPARCMemoryEventType.SESSION_UPDATED].append(event_handler)
    
    def start_event_listener(self):
        """Start the event listener thread"""
        if not self._listening:
            self._listening = True
            self._listener_thread = threading.Thread(target=self._event_listener_loop, daemon=True)
            self._listener_thread.start()
            self.logger.info("Started SPARC memory event listener")
    
    def _event_listener_loop(self):
        """Event listener loop"""
        while self._listening:
            try:
                message = self.pubsub.get_message(timeout=1)
                if message and message['type'] == 'message':
                    try:
                        event_data = json.loads(message['data'])
                        event = SPARCMemoryEvent(**event_data)
                        self._handle_event(event)
                    except Exception as e:
                        self.logger.error(f"Failed to process event: {e}")
            except Exception as e:
                self.logger.error(f"Error in event listener: {e}")
                time.sleep(1)
    
    def _handle_event(self, event: SPARCMemoryEvent):
        """Handle incoming events"""
        handlers = self.event_handlers.get(event.type, [])
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                self.logger.error(f"Error in event handler: {e}")
    
    def get_session_events(self, session_id: str, limit: int = 100) -> List[SPARCMemoryEvent]:
        """Get recent events for a session"""
        try:
            event_ids = self.redis.lrange(self._key("session", session_id, "events"), 0, limit - 1)
            events = []
            
            for event_id in event_ids:
                event_id_str = event_id.decode() if isinstance(event_id, bytes) else event_id
                event_key = self._key("event", event_id_str)
                event_json = self.redis.get(event_key)
                
                if event_json:
                    event_data = json.loads(event_json)
                    # Convert string timestamp back to datetime
                    if 'timestamp' in event_data:
                        event_data['timestamp'] = datetime.fromisoformat(event_data['timestamp'])
                    event = SPARCMemoryEvent(**event_data)
                    events.append(event)
            
            return events
            
        except Exception as e:
            self.logger.error(f"Failed to get events for session {session_id}: {e}")
            return []
    
    # Cleanup and Maintenance
    def cleanup_expired_sessions(self):
        """Clean up expired sessions and related data"""
        try:
            current_time = datetime.now()
            session_ids = self.redis.smembers(self._key("sessions"))
            
            for session_id in session_ids:
                session_id_str = session_id.decode() if isinstance(session_id, bytes) else session_id
                session = self.get_session(session_id_str)
                
                if not session:
                    # Session doesn't exist, remove from index
                    self.redis.srem(self._key("sessions"), session_id_str)
                    continue
                
                # Check if session is expired
                completed_at = session.get("completed_at")
                if completed_at:
                    completed_time = datetime.fromisoformat(completed_at)
                    if current_time - completed_time > timedelta(seconds=self.session_ttl):
                        self.delete_session(session_id_str)
                        self.logger.info(f"Cleaned up expired session: {session_id_str}")
            
        except Exception as e:
            self.logger.error(f"Failed to cleanup expired sessions: {e}")
    
    @contextmanager
    def atomic_update(self, session_id: str):
        """Context manager for atomic session updates"""
        pipe = self.redis.pipeline()
        try:
            yield pipe
            pipe.execute()
        except Exception as e:
            self.logger.error(f"Atomic update failed for session {session_id}: {e}")
            raise
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """Get memory usage statistics"""
        try:
            total_sessions = self.redis.scard(self._key("sessions"))
            
            # Get memory usage info
            info = self.redis.info('memory')
            
            return {
                "total_sessions": total_sessions,
                "memory_used_mb": info.get('used_memory', 0) / 1024 / 1024,
                "memory_peak_mb": info.get('used_memory_peak', 0) / 1024 / 1024,
                "redis_version": info.get('redis_version', 'unknown'),
                "keyspace_hits": info.get('keyspace_hits', 0),
                "keyspace_misses": info.get('keyspace_misses', 0)
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get memory stats: {e}")
            return {}
    
    def shutdown(self):
        """Shutdown the memory coordinator"""
        self._listening = False
        if self._listener_thread:
            self._listener_thread.join(timeout=5)
        self.pubsub.close()
        self.logger.info("SPARC Memory Coordinator shutdown complete")


if __name__ == "__main__":
    # Example usage
    import redis
    
    redis_client = redis.from_url("redis://localhost:6379/0")
    coordinator = SPARCMemoryCoordinator(redis_client)
    
    # Create a test session
    session_data = {
        "id": "test_session_1",
        "name": "Test Session",
        "status": "active",
        "created_at": datetime.now().isoformat()
    }
    
    coordinator.create_session("test_session_1", session_data)
    
    # Test shared context
    coordinator.set_shared_context("test_session_1", "test_key", {"data": [1, 2, 3]})
    context = coordinator.get_shared_context("test_session_1", "test_key")
    print(f"Context: {context}")
    
    # Test agent registration
    agent_data = {
        "id": "agent_1",
        "name": "Test Agent",
        "capabilities": ["data_processing", "analysis"],
        "status": "idle"
    }
    
    coordinator.register_agent("test_session_1", "agent_1", agent_data)
    agents = coordinator.get_session_agents("test_session_1")
    print(f"Agents: {agents}")
    
    # Get memory stats
    stats = coordinator.get_memory_stats()
    print(f"Memory stats: {stats}")
    
    coordinator.shutdown()