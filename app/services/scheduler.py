"""
Scheduler Service

APScheduler-based task scheduler for automated video generation and upload.
Supports cron-style scheduling for multiple channels.
"""

import signal
import sys
from datetime import datetime
from typing import Optional, Dict, Any, Callable

from loguru import logger

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED
    APSCHEDULER_AVAILABLE = True
except ImportError:
    APSCHEDULER_AVAILABLE = False
    logger.warning("APScheduler not installed. Run: pip install APScheduler")


class ShortsScheduler:
    """
    Scheduler for automated YouTube Shorts creation and upload.
    
    Uses APScheduler with cron-style triggers for flexible scheduling.
    """
    
    def __init__(
        self,
        timezone: str = "Europe/Istanbul",
        blocking: bool = True
    ):
        """
        Initialize the scheduler.
        
        Args:
            timezone: Timezone for schedule interpretation
            blocking: If True, uses BlockingScheduler (keeps process alive)
        """
        if not APSCHEDULER_AVAILABLE:
            raise ImportError(
                "APScheduler not installed. "
                "Run: pip install APScheduler"
            )
        
        self.timezone = timezone
        self.blocking = blocking
        
        if blocking:
            self.scheduler = BlockingScheduler(timezone=timezone)
        else:
            self.scheduler = BackgroundScheduler(timezone=timezone)
        
        # Track scheduled jobs
        self.jobs: Dict[str, Any] = {}
        
        # Add event listeners
        self.scheduler.add_listener(
            self._on_job_executed,
            EVENT_JOB_EXECUTED
        )
        self.scheduler.add_listener(
            self._on_job_error,
            EVENT_JOB_ERROR
        )
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        logger.info("Shutdown signal received, stopping scheduler...")
        self.stop()
        sys.exit(0)
    
    def _on_job_executed(self, event):
        """Callback when a job is executed successfully."""
        job_id = event.job_id
        logger.info(f"Job executed successfully: {job_id}")
    
    def _on_job_error(self, event):
        """Callback when a job encounters an error."""
        job_id = event.job_id
        exception = event.exception
        logger.error(f"Job {job_id} failed with error: {exception}")
    
    def add_channel_job(
        self,
        channel_name: str,
        schedule: str,
        job_func: Callable,
        **job_kwargs
    ) -> bool:
        """
        Add a scheduled job for a channel.
        
        Args:
            channel_name: Unique identifier for the channel
            schedule: Cron expression (e.g., "0 9,15,21 * * *")
            job_func: Function to execute
            **job_kwargs: Arguments to pass to the job function
            
        Returns:
            True if job added successfully
        """
        try:
            # Parse cron expression
            trigger = CronTrigger.from_crontab(schedule, timezone=self.timezone)
            
            job_id = f"channel_{channel_name}"
            
            # Remove existing job if any
            if job_id in self.jobs:
                self.scheduler.remove_job(job_id)
            
            # Add the job
            job = self.scheduler.add_job(
                job_func,
                trigger=trigger,
                id=job_id,
                name=f"Video generation for {channel_name}",
                kwargs={'channel_name': channel_name, **job_kwargs},
                replace_existing=True,
                max_instances=1,  # Prevent overlapping runs
                coalesce=True     # Combine missed runs
            )
            
            self.jobs[job_id] = job
            
            # Log next run time
            next_run = getattr(job, 'next_run_time', None)
            logger.info(f"Scheduled job for {channel_name}: {schedule}")
            logger.info(f"Next run: {next_run}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to add job for {channel_name}: {e}")
            return False
    
    def add_interval_job(
        self,
        job_id: str,
        job_func: Callable,
        hours: int = 0,
        minutes: int = 0,
        seconds: int = 0,
        **job_kwargs
    ) -> bool:
        """
        Add an interval-based job.
        
        Args:
            job_id: Unique identifier for the job
            job_func: Function to execute
            hours, minutes, seconds: Interval timing
            **job_kwargs: Arguments to pass to the job function
            
        Returns:
            True if job added successfully
        """
        try:
            if job_id in self.jobs:
                self.scheduler.remove_job(job_id)
            
            job = self.scheduler.add_job(
                job_func,
                'interval',
                id=job_id,
                hours=hours,
                minutes=minutes,
                seconds=seconds,
                kwargs=job_kwargs,
                replace_existing=True,
                max_instances=1
            )
            
            self.jobs[job_id] = job
            logger.info(f"Added interval job: {job_id} (every {hours}h {minutes}m {seconds}s)")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to add interval job {job_id}: {e}")
            return False
    
    def remove_job(self, job_id: str) -> bool:
        """Remove a scheduled job."""
        try:
            if job_id in self.jobs:
                self.scheduler.remove_job(job_id)
                del self.jobs[job_id]
                logger.info(f"Removed job: {job_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to remove job {job_id}: {e}")
            return False
    
    def get_job_info(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a scheduled job."""
        job = self.scheduler.get_job(job_id)
        if not job:
            return None
        
        return {
            'id': job.id,
            'name': job.name,
            'next_run_time': getattr(job, 'next_run_time', None),
            'trigger': str(job.trigger)
        }
    
    def list_jobs(self) -> list:
        """Get list of all scheduled jobs."""
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                'id': job.id,
                'name': job.name,
                'next_run_time': getattr(job, 'next_run_time', None),
                'trigger': str(job.trigger)
            })
        return jobs
    
    def start(self):
        """Start the scheduler."""
        logger.info(f"Starting scheduler (timezone: {self.timezone})...")
        
        # Print all scheduled jobs
        for job in self.scheduler.get_jobs():
            next_run = getattr(job, 'next_run_time', None)
            logger.info(f"  Job: {job.name} -> Next run: {next_run}")
        
        if self.blocking:
            logger.info("Scheduler running in blocking mode. Press Ctrl+C to stop.")
            self.scheduler.start()  # This blocks
        else:
            self.scheduler.start()
            logger.info("Scheduler started in background mode.")
    
    def stop(self):
        """Stop the scheduler."""
        logger.info("Stopping scheduler...")
        self.scheduler.shutdown(wait=True)
        logger.info("Scheduler stopped.")
    
    def is_running(self) -> bool:
        """Check if scheduler is running."""
        return self.scheduler.running
    
    def run_job_now(self, job_id: str) -> bool:
        """
        Trigger a job to run immediately.
        
        Args:
            job_id: ID of the job to run
            
        Returns:
            True if job was triggered
        """
        try:
            job = self.scheduler.get_job(job_id)
            if not job:
                logger.error(f"Job not found: {job_id}")
                return False
            
            # Run the job function directly
            job.func(**job.kwargs)
            return True
            
        except Exception as e:
            logger.error(f"Failed to run job {job_id}: {e}")
            return False


def parse_cron_expression(expression: str) -> Dict[str, str]:
    """
    Parse a cron expression into its components.
    
    Args:
        expression: Cron expression (e.g., "0 9,15,21 * * *")
        
    Returns:
        Dict with minute, hour, day, month, day_of_week
    """
    parts = expression.split()
    if len(parts) != 5:
        raise ValueError(f"Invalid cron expression: {expression}")
    
    return {
        'minute': parts[0],
        'hour': parts[1],
        'day': parts[2],
        'month': parts[3],
        'day_of_week': parts[4]
    }


if __name__ == "__main__":
    # Test the scheduler
    def test_job(channel_name: str):
        print(f"[{datetime.now()}] Executing job for: {channel_name}")
    
    scheduler = ShortsScheduler(blocking=False)
    
    # Add a test job that runs every 10 seconds
    scheduler.add_interval_job(
        job_id="test_job",
        job_func=test_job,
        seconds=10,
        channel_name="test_channel"
    )
    
    scheduler.start()
    
    print("Scheduler started. Jobs:")
    for job in scheduler.list_jobs():
        print(f"  - {job['name']}: next run at {job['next_run_time']}")
    
    # Keep running for a while
    import time
    try:
        time.sleep(35)
    except KeyboardInterrupt:
        pass
    
    scheduler.stop()
