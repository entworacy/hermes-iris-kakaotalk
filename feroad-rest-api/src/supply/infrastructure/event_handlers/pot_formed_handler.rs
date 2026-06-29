use async_trait::async_trait;

use crate::infrastructure::app_state::AppState;
use crate::infrastructure::event_bus::EventHandler;
use crate::shared_kernel::domain_event::StoredEvent;
use crate::shared_kernel::event_types;
use crate::shared_kernel::pot_payload::PotFormedPayload;
use crate::supply::domain::model::route::{has_active_ephemeral_for_pot, spawn_ephemeral_route_from_pot};

pub struct PotFormedHandler {
    state: AppState,
}

impl PotFormedHandler {
    pub fn new(state: AppState) -> Self {
        Self { state }
    }
}

#[async_trait]
impl EventHandler for PotFormedHandler {
    async fn handle(&self, event: &StoredEvent) -> Result<(), String> {
        if event.event_type != event_types::POT_FORMED {
            return Ok(());
        }

        let payload: PotFormedPayload =
            serde_json::from_str(&event.payload).map_err(|e| e.to_string())?;

        {
            let routes: Vec<_> = self.state.routes.read().unwrap().values().cloned().collect();
            if has_active_ephemeral_for_pot(&routes, payload.pot_id) {
                return Err("active ephemeral route already exists for pot".into());
            }
        }

        if let Some(pot) = self.state.pots.write().unwrap().get_mut(&payload.pot_id) {
            pot.mark_spawning_route();
        }

        let route = spawn_ephemeral_route_from_pot(&payload).map_err(|e| e.to_string())?;
        let route_id = route.id();

        let activated = StoredEvent::new(
            event_types::EPHEMERAL_ROUTE_ACTIVATED,
            serde_json::to_string(&route).map_err(|e| e.to_string())?,
            route_id.to_string(),
        );

        self.state.routes.write().unwrap().insert(route_id, route);
        self.state.event_bus.publish(activated).await
    }
}