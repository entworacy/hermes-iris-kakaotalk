use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct StoredEvent {
    pub event_type: String,
    pub payload: String,
    pub aggregate_id: String,
}

impl StoredEvent {
    pub fn new(event_type: impl Into<String>, payload: impl Into<String>, aggregate_id: impl Into<String>) -> Self {
        Self {
            event_type: event_type.into(),
            payload: payload.into(),
            aggregate_id: aggregate_id.into(),
        }
    }
}