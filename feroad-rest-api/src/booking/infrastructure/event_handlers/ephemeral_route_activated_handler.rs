use async_trait::async_trait;

use crate::booking::domain::model::booking::Booking;
use crate::infrastructure::app_state::AppState;
use crate::infrastructure::event_bus::EventHandler;
use crate::shared_kernel::domain_event::StoredEvent;
use crate::shared_kernel::event_types;
use crate::supply::domain::model::route::{Route, StopType};

pub struct EphemeralRouteActivatedHandler {
    state: AppState,
}

impl EphemeralRouteActivatedHandler {
    pub fn new(state: AppState) -> Self {
        Self { state }
    }
}

#[async_trait]
impl EventHandler for EphemeralRouteActivatedHandler {
    async fn handle(&self, event: &StoredEvent) -> Result<(), String> {
        if event.event_type != event_types::EPHEMERAL_ROUTE_ACTIVATED {
            return Ok(());
        }

        let route: Route =
            serde_json::from_str(&event.payload).map_err(|e| e.to_string())?;
        let pot_id = route.pot_id().ok_or("missing pot_id on ephemeral route")?;

        let pot = self
            .state
            .pots
            .read()
            .unwrap()
            .get(&pot_id)
            .cloned()
            .ok_or("pot not found")?;

        let payload = pot.formed_payload();
        let mut all_events = Vec::new();

        for (idx, member) in payload.members.iter().enumerate() {
            let pickup_order = (idx * 2) as u16;
            let dropoff_order = pickup_order + 1;
            let pickup = route
                .stops()
                .iter()
                .find(|s| s.stop_type == StopType::Pickup && s.order == pickup_order)
                .ok_or("pickup stop missing")?
                .id;
            let dropoff = route
                .stops()
                .iter()
                .find(|s| s.stop_type == StopType::Dropoff && s.order == dropoff_order)
                .ok_or("dropoff stop missing")?
                .id;

            let (booking, events) =
                Booking::from_pot_member(pot_id, route.id(), member, pickup, dropoff);
            self.state
                .bookings
                .write()
                .unwrap()
                .insert(booking.id(), booking);
            all_events.extend(events);
        }

        if let Some(pot_mut) = self.state.pots.write().unwrap().get_mut(&pot_id) {
            pot_mut.mark_converted();
        }

        self.state.push_events(all_events);
        Ok(())
    }
}