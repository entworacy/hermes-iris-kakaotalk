use async_trait::async_trait;

use crate::contract::domain::model::brokerage_contract::BrokerageContract;
use crate::infrastructure::app_state::AppState;
use crate::infrastructure::event_bus::EventHandler;
use crate::shared_kernel::domain_event::StoredEvent;
use crate::shared_kernel::event_types;
use crate::booking::domain::model::booking::Booking;

pub struct BookingConfirmedHandler {
    state: AppState,
}

impl BookingConfirmedHandler {
    pub fn new(state: AppState) -> Self {
        Self { state }
    }
}

#[async_trait]
impl EventHandler for BookingConfirmedHandler {
    async fn handle(&self, event: &StoredEvent) -> Result<(), String> {
        if event.event_type != event_types::BOOKING_CONFIRMED {
            return Ok(());
        }

        let booking: Booking =
            serde_json::from_str(&event.payload).map_err(|e| e.to_string())?;

        if self
            .state
            .contracts
            .read()
            .unwrap()
            .values()
            .any(|c| c.booking_id() == booking.id())
        {
            return Ok(());
        }

        let (contract, _events) = BrokerageContract::from_booking(&booking);
        self.state
            .contracts
            .write()
            .unwrap()
            .insert(contract.id(), contract);
        Ok(())
    }
}