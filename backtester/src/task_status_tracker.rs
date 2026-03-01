use crate::DbPool;
use chrono::{DateTime, Utc};
use std::fmt;

pub enum TaskStatus {
    InProgress,
    Failed,
    Complete,
}

impl fmt::Display for TaskStatus {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            TaskStatus::InProgress => write!(f, "In Progress"),
            TaskStatus::Failed => write!(f, "Failed"),
            TaskStatus::Complete => write!(f, "Complete"),
        }
    }
}

pub struct TaskStatusTracker<'a> {
    pool: &'a DbPool,
    task_id: &'a str,
    component_name: &'a str,
    task_description: &'a str,
}

impl<'a> TaskStatusTracker<'a> {
    pub fn new(
        pool: &'a DbPool,
        task_id: &'a str,
        component_name: &'a str,
        task_description: &'a str,
    ) -> Self {
        Self {
            pool,
            task_id,
            component_name,
            task_description,
        }
    }

    pub fn start_task(&self) {
        let status = TaskStatus::InProgress;
        let status_message = "Task started";
        let progress: f64 = 0.1;
        let start_time: DateTime<Utc> = Utc::now();

        let sql = "
            INSERT INTO etl_task_status (
                task_id,
                component_name,
                task_description,
                status,
                status_message,
                progress,
                start_time
            ) VALUES ($1, $2, $3, $4, $5, $6, $7);
        ";
        let mut client = self.pool.get().unwrap();
        client
            .execute(
                sql,
                &[
                    &self.task_id,
                    &self.component_name,
                    &self.task_description,
                    &status.to_string(),
                    &status_message,
                    &progress,
                    &start_time,
                ],
            )
            .expect("Error writing data to db");
    }

    pub fn complete_task(&self) {
        let status = TaskStatus::Complete;
        let progress = 1.0;
        let end_time: DateTime<Utc> = Utc::now();

        let sql = "
            UPDATE etl_task_status
            SET
                status = $1,
                progress = $2,
                end_time = $3
            WHERE task_id = $4;
        ";
        let mut client = self.pool.get().unwrap();
        client
            .execute(
                sql,
                &[&status.to_string(), &progress, &end_time, &self.task_id],
            )
            .expect("Error updating task status");
    }

    pub fn fail_task(&self, error_message: &str) {
        let status = TaskStatus::Failed;
        let end_time: DateTime<Utc> = Utc::now();

        let sql = "
            UPDATE etl_task_status
            SET
                status = $1,
                end_time = $2,
                status_message = $3
            WHERE task_id = $4
        ";
        let mut client = self.pool.get().unwrap();
        client
            .execute(
                sql,
                &[
                    &status.to_string(),
                    &end_time,
                    &error_message,
                    &self.task_id,
                ],
            )
            .expect("Error updating task status");
    }

    pub fn update_status_message(&self, message: &str) {
        let sql = "UPDATE etl_task_status SET status_message = $1 WHERE task_id = $2";
        let mut client = self.pool.get().unwrap();
        client
            .execute(sql, &[&message, &self.task_id])
            .expect("Error updating task status");
    }

    pub fn update_progress(&self, progress_pct: f64) {
        // TODO this works different than the python version since this is threaded.
        // Consider adding bool arg to control functionality
        let sql = "UPDATE etl_task_status SET progress_pct = progress_pct + $1 WHERE task_id = $2";
        let mut client = self.pool.get().unwrap();
        client
            .execute(sql, &[&progress_pct, &self.task_id])
            .expect("Error updating task status");
    }
}
