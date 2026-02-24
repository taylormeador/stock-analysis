use postgres::Client;
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

pub struct TaskStatusTracker {
    client: Client,
    task_id: String,
    component_name: String,
    task_description: String
}

impl TaskStatusTracker {
    pub fn new(client: Client, task_id: String, component_name: String, task_description: String) -> Self {
        Self {
            client,
            task_id,
            component_name,
            task_description,
        }
    }

    pub fn start_task(&mut self) {
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
        self.client.execute(sql, &[&self.task_id, &self.component_name, &self.task_description, &status.to_string(), &status_message, &progress, &start_time]).expect("Error writing data to db");

    }

    pub fn complete_task(&mut self) {
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
        self.client.execute(sql, &[&status.to_string(), &progress, &end_time, &self.task_id]).expect("Error updating task status");
    }

    pub fn fail_task(&mut self, error_message: String) {
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
        self.client.execute(sql, &[&status.to_string(), &end_time, &error_message, &self.task_id]).expect("Error updating task status");
    }
}
