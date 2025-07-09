"""
Job Repository for managing background job database operations.
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func
from datetime import datetime, timedelta
import uuid

from models import Job, JobStatus
from .base import BaseRepository

class JobRepository(BaseRepository):
    """Repository for Job model operations."""
    
    def __init__(self, session: Session):
        super().__init__(Job, session)
    
    def get_by_uuid(self, job_uuid: str) -> Optional[Job]:
        """Get job by UUID."""
        return self.get_by(job_uuid=job_uuid)
    
    def create_job(self, script_name: str, user_id: int, parameters: Optional[Dict[str, Any]] = None,
                  options: Optional[Dict[str, Any]] = None, display_name: Optional[str] = None,
                  description: Optional[str] = None) -> Job:
        """Create a new job."""
        return self.create(
            job_uuid=str(uuid.uuid4()),
            script_name=script_name,
            user_id=user_id,
            parameters=parameters or {},
            options=options or {},
            display_name=display_name,
            description=description,
            status=JobStatus.PENDING.value
        )
    
    def start_job(self, job_id: int) -> Optional[Job]:
        """Mark job as started."""
        return self.update(
            job_id,
            status=JobStatus.RUNNING.value,
            started_at=datetime.utcnow()
        )
    
    def complete_job(self, job_id: int, result: Optional[Dict[str, Any]] = None,
                    output_log: Optional[str] = None) -> Optional[Job]:
        """Mark job as completed."""
        job = self.get(job_id)
        if not job:
            return None
        
        duration = None
        if job.started_at:
            duration = int((datetime.utcnow() - job.started_at).total_seconds())
        
        return self.update(
            job_id,
            status=JobStatus.COMPLETED.value,
            completed_at=datetime.utcnow(),
            actual_duration=duration,
            result=result,
            output_log=output_log,
            progress=100
        )
    
    def fail_job(self, job_id: int, error_message: str, output_log: Optional[str] = None) -> Optional[Job]:
        """Mark job as failed."""
        job = self.get(job_id)
        if not job:
            return None
        
        duration = None
        if job.started_at:
            duration = int((datetime.utcnow() - job.started_at).total_seconds())
        
        return self.update(
            job_id,
            status=JobStatus.FAILED.value,
            completed_at=datetime.utcnow(),
            actual_duration=duration,
            error_message=error_message,
            output_log=output_log
        )
    
    def cancel_job(self, job_id: int) -> Optional[Job]:
        """Cancel a pending or running job."""
        job = self.get(job_id)
        if not job or job.status not in [JobStatus.PENDING.value, JobStatus.RUNNING.value]:
            return None
        
        return self.update(
            job_id,
            status=JobStatus.CANCELLED.value,
            completed_at=datetime.utcnow()
        )
    
    def update_progress(self, job_id: int, progress: int, current_stage: Optional[str] = None,
                       message: Optional[str] = None) -> Optional[Job]:
        """Update job progress."""
        updates = {'progress': min(100, max(0, progress))}
        if current_stage:
            updates['current_stage'] = current_stage
        if message:
            updates['meta_data'] = {'last_message': message}
        
        return self.update(job_id, **updates)
    
    def get_user_jobs(self, user_id: int, limit: Optional[int] = None,
                     status: Optional[str] = None) -> List[Job]:
        """Get jobs for a specific user."""
        query = self.session.query(Job).filter(Job.user_id == user_id)
        
        if status:
            query = query.filter(Job.status == status)
        
        query = query.order_by(Job.created_at.desc())
        
        if limit:
            query = query.limit(limit)
        
        return query.all()
    
    def get_pending_jobs(self, limit: Optional[int] = None) -> List[Job]:
        """Get pending jobs ordered by priority and creation time."""
        query = self.session.query(Job).filter(
            Job.status == JobStatus.PENDING.value
        ).order_by(
            Job.priority.desc(),
            Job.created_at.asc()
        )
        
        if limit:
            query = query.limit(limit)
        
        return query.all()
    
    def get_running_jobs(self) -> List[Job]:
        """Get all currently running jobs."""
        return self.filter({'status': JobStatus.RUNNING.value})
    
    def get_stuck_jobs(self, timeout_minutes: int = 30) -> List[Job]:
        """Get jobs that have been running too long."""
        timeout_threshold = datetime.utcnow() - timedelta(minutes=timeout_minutes)
        
        return self.session.query(Job).filter(
            Job.status == JobStatus.RUNNING.value,
            Job.started_at < timeout_threshold
        ).all()
    
    def get_recent_jobs(self, hours: int = 24, limit: int = 100) -> List[Job]:
        """Get recently created jobs."""
        since_date = datetime.utcnow() - timedelta(hours=hours)
        
        return self.session.query(Job).filter(
            Job.created_at >= since_date
        ).order_by(Job.created_at.desc()).limit(limit).all()
    
    def get_job_statistics(self, user_id: Optional[int] = None) -> Dict[str, Any]:
        """Get job statistics."""
        query = self.session.query(Job)
        if user_id:
            query = query.filter(Job.user_id == user_id)
        
        # Status counts
        status_counts = query.with_entities(
            Job.status,
            func.count(Job.id).label('count')
        ).group_by(Job.status).all()
        
        # Script counts
        script_counts = query.with_entities(
            Job.script_name,
            func.count(Job.id).label('count')
        ).group_by(Job.script_name).order_by(
            func.count(Job.id).desc()
        ).limit(10).all()
        
        # Average duration by script
        avg_durations = query.filter(
            Job.actual_duration.isnot(None)
        ).with_entities(
            Job.script_name,
            func.avg(Job.actual_duration).label('avg_duration')
        ).group_by(Job.script_name).all()
        
        # Success rate
        total_completed = query.filter(
            Job.status.in_([JobStatus.COMPLETED.value, JobStatus.FAILED.value])
        ).count()
        
        successful = query.filter(
            Job.status == JobStatus.COMPLETED.value
        ).count()
        
        success_rate = (successful / total_completed * 100) if total_completed > 0 else 0
        
        return {
            'status_breakdown': {status: count for status, count in status_counts},
            'popular_scripts': [{'script': script, 'count': count} for script, count in script_counts],
            'average_durations': {script: round(avg_dur, 2) for script, avg_dur in avg_durations},
            'success_rate': round(success_rate, 2),
            'total_jobs': query.count()
        }
    
    def cleanup_old_jobs(self, days: int = 30, keep_failed: bool = True) -> int:
        """Clean up old completed jobs."""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        query = self.session.query(Job).filter(
            Job.completed_at < cutoff_date
        )
        
        if keep_failed:
            query = query.filter(Job.status != JobStatus.FAILED.value)
        
        deleted_count = query.count()
        query.delete(synchronize_session=False)
        self.session.flush()
        
        return deleted_count
    
    def get_with_user(self, job_id: int) -> Optional[Job]:
        """Get job with user eagerly loaded."""
        return self.session.query(Job).options(
            joinedload(Job.user)
        ).filter(Job.id == job_id).first()
    
    def count_by_status(self, status: str) -> int:
        """Count jobs by status."""
        return self.count({'status': status})
    
    def count_created_today(self) -> int:
        """Count jobs created today."""
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        return self.session.query(Job).filter(
            Job.created_at >= today_start
        ).count()
    
    def get_recent(self, limit: int = 10) -> List[Job]:
        """Get recent jobs."""
        return self.session.query(Job).options(
            joinedload(Job.user)
        ).order_by(Job.created_at.desc()).limit(limit).all()
    
    def get_avg_duration(self) -> float:
        """Get average job duration in seconds."""
        avg_duration = self.session.query(
            func.avg(Job.actual_duration)
        ).filter(
            Job.actual_duration.isnot(None)
        ).scalar()
        
        return round(avg_duration or 0, 2)
    
    def get_jobs_per_hour(self) -> float:
        """Get average jobs per hour over the last 24 hours."""
        since_date = datetime.utcnow() - timedelta(hours=24)
        job_count = self.session.query(Job).filter(
            Job.created_at >= since_date
        ).count()
        
        return round(job_count / 24, 2)
    
    def get_success_rate(self) -> float:
        """Get overall success rate as percentage."""
        total_completed = self.session.query(Job).filter(
            Job.status.in_([JobStatus.COMPLETED.value, JobStatus.FAILED.value])
        ).count()
        
        if total_completed == 0:
            return 0.0
            
        successful = self.session.query(Job).filter(
            Job.status == JobStatus.COMPLETED.value
        ).count()
        
        return round((successful / total_completed) * 100, 2)
    
    def count_by_user(self, user_id: int) -> int:
        """Count jobs by user."""
        return self.count({'user_id': user_id})
    
    def count_by_user_and_status(self, user_id: int, status: str) -> int:
        """Count jobs by user and status."""
        return self.count({'user_id': user_id, 'status': status})
    
    def get_avg_duration_by_user(self, user_id: int) -> float:
        """Get average job duration for a specific user."""
        avg_duration = self.session.query(
            func.avg(Job.actual_duration)
        ).filter(
            Job.user_id == user_id,
            Job.actual_duration.isnot(None)
        ).scalar()
        
        return round(avg_duration or 0, 2)
    
    def get_paginated_with_users(self, page: int = 1, limit: int = 50, 
                                filters: Dict[str, Any] = None,
                                date_filters: Dict[str, Any] = None) -> tuple:
        """Get paginated jobs with user information."""
        query = self.session.query(Job).options(joinedload(Job.user))
        
        # Apply filters
        if filters:
            for field, value in filters.items():
                if hasattr(Job, field):
                    query = query.filter(getattr(Job, field) == value)
        
        # Apply date filters
        if date_filters:
            if date_filters.get('date_from'):
                query = query.filter(Job.created_at >= date_filters['date_from'])
            if date_filters.get('date_to'):
                query = query.filter(Job.created_at <= date_filters['date_to'])
        
        # Get total count
        total = query.count()
        
        # Apply pagination
        query = query.order_by(Job.created_at.desc())
        query = query.offset((page - 1) * limit).limit(limit)
        
        return query.all(), total
    
    def get_daily_metrics(self, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """Get daily job metrics."""
        # This is a simplified implementation
        # In production, you'd use more sophisticated queries
        metrics = []
        current_date = start_date
        
        while current_date <= end_date:
            next_date = current_date + timedelta(days=1)
            
            day_jobs = self.session.query(Job).filter(
                Job.created_at >= current_date,
                Job.created_at < next_date
            ).all()
            
            completed = sum(1 for j in day_jobs if j.status == JobStatus.COMPLETED.value)
            failed = sum(1 for j in day_jobs if j.status == JobStatus.FAILED.value)
            
            metrics.append({
                'date': current_date.strftime('%Y-%m-%d'),
                'total': len(day_jobs),
                'completed': completed,
                'failed': failed,
                'success_rate': (completed / len(day_jobs) * 100) if day_jobs else 0
            })
            
            current_date = next_date
        
        return metrics
    
    def get_script_performance_stats(self) -> List[Dict[str, Any]]:
        """Get performance statistics by script."""
        scripts = self.session.query(
            Job.script_name,
            func.count(Job.id).label('total'),
            func.avg(Job.actual_duration).label('avg_duration'),
            func.sum(func.case([(Job.status == JobStatus.COMPLETED.value, 1)], else_=0)).label('successful'),
            func.sum(func.case([(Job.status == JobStatus.FAILED.value, 1)], else_=0)).label('failed')
        ).group_by(Job.script_name).all()
        
        return [{
            'script_name': script,
            'total_runs': total,
            'avg_duration': round(avg_dur or 0, 2),
            'successful': successful,
            'failed': failed,
            'success_rate': round((successful / total * 100) if total > 0 else 0, 2)
        } for script, total, avg_dur, successful, failed in scripts]
    
    def get_error_analysis(self, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Get error analysis for the given period."""
        failed_jobs = self.session.query(Job).filter(
            Job.status == JobStatus.FAILED.value,
            Job.created_at >= start_date,
            Job.created_at <= end_date
        ).all()
        
        # Group errors by message patterns
        error_patterns = {}
        for job in failed_jobs:
            if job.error_message:
                # Simple grouping by first part of error
                error_key = job.error_message.split(':')[0][:50]
                error_patterns[error_key] = error_patterns.get(error_key, 0) + 1
        
        return {
            'total_errors': len(failed_jobs),
            'error_patterns': sorted(
                [{'pattern': k, 'count': v} for k, v in error_patterns.items()],
                key=lambda x: x['count'],
                reverse=True
            )[:10]
        }
    
    def count_in_period(self, start_date: datetime, end_date: datetime) -> int:
        """Count jobs in a specific period."""
        return self.session.query(Job).filter(
            Job.created_at >= start_date,
            Job.created_at <= end_date
        ).count()
    
    def get_avg_duration_in_period(self, start_date: datetime, end_date: datetime) -> float:
        """Get average duration for jobs in a period."""
        avg_duration = self.session.query(
            func.avg(Job.actual_duration)
        ).filter(
            Job.created_at >= start_date,
            Job.created_at <= end_date,
            Job.actual_duration.isnot(None)
        ).scalar()
        
        return round(avg_duration or 0, 2)
    
    def get_success_rate_in_period(self, start_date: datetime, end_date: datetime) -> float:
        """Get success rate for jobs in a period."""
        total = self.session.query(Job).filter(
            Job.created_at >= start_date,
            Job.created_at <= end_date,
            Job.status.in_([JobStatus.COMPLETED.value, JobStatus.FAILED.value])
        ).count()
        
        if total == 0:
            return 0.0
            
        successful = self.session.query(Job).filter(
            Job.created_at >= start_date,
            Job.created_at <= end_date,
            Job.status == JobStatus.COMPLETED.value
        ).count()
        
        return round((successful / total) * 100, 2)
    
    def get_peak_concurrent_jobs(self, start_date: datetime, end_date: datetime) -> int:
        """Get peak number of concurrent jobs in a period."""
        # This is a simplified implementation
        # In production, you'd use more sophisticated queries
        return 5  # Placeholder value
    
    def get_by_user(self, user_id: int, limit: int = 5) -> List[Job]:
        """Get jobs by user with limit."""
        return self.session.query(Job).filter(
            Job.user_id == user_id
        ).order_by(Job.created_at.desc()).limit(limit).all()