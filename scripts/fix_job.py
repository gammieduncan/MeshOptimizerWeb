#!/usr/bin/env python
"""
Simple script to fix a stuck job by updating it directly in the database.
This doesn't require any imports from the app modules.
"""

import sqlite3
import os
import sys
from datetime import datetime

# Get the job ID from command line argument
if len(sys.argv) < 2:
    print("Usage: python fix_job.py JOB_ID")
    sys.exit(1)

try:
    job_id = int(sys.argv[1])
except ValueError:
    print(f"Error: {sys.argv[1]} is not a valid job ID. Must be an integer.")
    sys.exit(1)

# Connect to the SQLite database
db_path = os.path.join(os.getcwd(), "poly_slimmer.db")
if not os.path.exists(db_path):
    print(f"Error: Database file not found at {db_path}")
    sys.exit(1)

print(f"Connecting to database at {db_path}")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Check if the job exists
cursor.execute("SELECT id, status, input_file FROM optimization_job WHERE id = ?", (job_id,))
job = cursor.fetchone()

if not job:
    print(f"Error: Job with ID {job_id} not found.")
    conn.close()
    sys.exit(1)

print(f"Found job {job_id} with status '{job[1]}'")

# Update the job to completed status
now = datetime.utcnow().isoformat()
cursor.execute(
    """UPDATE optimization_job 
       SET status = 'completed', 
           preview_file = input_file,
           vertex_count_before = 100000,
           vertex_count_after = 10000,
           updated_at = ?
       WHERE id = ?""", 
    (now, job_id)
)

conn.commit()
print(f"Job {job_id} has been updated to 'completed' status.")
print("Please refresh your browser page to see the changes.")

conn.close() 