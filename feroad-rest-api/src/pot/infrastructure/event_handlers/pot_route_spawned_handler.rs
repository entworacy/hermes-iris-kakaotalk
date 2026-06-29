use async_trait::async_trait;

use crate::infrastructure::app_state::AppState;
use crate::infrastructure::event_bus::EventHandler;
use crate::shared_kernel::domain_event::StoredEvent;
use crate::shared_kernel::event_types;
use crate::supply::domain::model::route::Route;

pub struct PotRouteSpawnedHandler {
    state: AppState,
}

impl PotRouteSpawnedHandler {
    pub fn new(state: AppState) -> Self {
        Self { state }
    }
}

#[async_trait]
impl EventHandler for PotRouteSpawnedHandler {
    async fn handle(&self, event: &StoredEvent) -> Result<(), String> {
        if event.event_type != event_types::EPHEMERAL_ROUTE_ACTIVATED {
            return Ok(());
        }

        let route: Route =
            serde_json::from_str(&event.payload).map_err(|e| e.to_string())?;
        let pot_id = route.pot_id().ok_or("ephemeral route missing pot_id")?;

        if let Some(pot) = self.state.pots.write().unwrap().get_mut(&pot_id) {
            let events = pot.mark_route_spawned(route.id());
            self.state.push_events(events);
        }

        Ok(())
    }
}