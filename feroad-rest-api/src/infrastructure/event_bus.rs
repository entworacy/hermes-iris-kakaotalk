use std::sync::{Arc, RwLock};

use async_trait::async_trait;

use crate::shared_kernel::domain_event::StoredEvent;

#[async_trait]
pub trait EventHandler: Send + Sync {
    async fn handle(&self, event: &StoredEvent) -> Result<(), String>;
}

pub struct EventBus {
    handlers: RwLock<Vec<Arc<dyn EventHandler>>>,
}

impl EventBus {
    pub fn new() -> Self {
        Self {
            handlers: RwLock::new(Vec::new()),
        }
    }

    pub fn register(&self, handler: Arc<dyn EventHandler>) {
        self.handlers.write().unwrap().push(handler);
    }

    pub async fn publish(&self, event: StoredEvent) -> Result<(), String> {
        let handlers: Vec<Arc<dyn EventHandler>> = self.handlers.read().unwrap().clone();
        for handler in handlers {
            handler.handle(&event).await?;
        }
        Ok(())
    }
}

impl Default for EventBus {
    fn default() -> Self {
        Self::new()
    }
}