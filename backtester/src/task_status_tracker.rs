use postgres::{Client, NoTls};
use chrono::{NaiveDate, DateTime, Utc};
use std::env;
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
    // redis_client: Redis,
    // redis_key: &str,
    task_id: String,
    component_name: String,
    task_description: String,
    // values: Map,
}

impl TaskStatusTracker {
    pub fn new(task_id: String, component_name: String, task_description: String) -> Self {
        Self {
            task_id: task_id,
            component_name: component_name,
            task_description: task_description,
        }
    }

    pub fn start_task(&self, mut client: Client) {
        // Write data
        let status = TaskStatus::InProgress;
        let status_message = "Rust is tight";
        let progress: f64 = 0.420;
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
        client.execute(sql, &[&self.task_id, &self.component_name, &self.task_description, &&status.to_string(), &status_message, &progress, &start_time]).expect("Error writing data to db");

    }
}
