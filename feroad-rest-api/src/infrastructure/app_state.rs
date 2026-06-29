use std::collections::HashMap;
use std::sync::{Arc, RwLock};

use crate::booking::domain::model::booking::Booking;
use crate::contract::domain::model::brokerage_contract::BrokerageContract;
use crate::infrastructure::acl::InMemoryAcl;
use crate::infrastructure::event_bus::EventBus;
use crate::pot::domain::model::match_record::MatchRecord;
use crate::pot::domain::model::pot::Pot;
use crate::pot::domain::model::ride_intent::RideIntent;
use crate::shared_kernel::domain_event::StoredEvent;
use crate::shared_kernel::ids::{BookingId, ContractId, PotId, RideIntentId, RouteId};
use crate::supply::domain::model::route::Route;

#[derive(Clone)]
pub struct AppState {
    pub event_bus: Arc<EventBus>,
    pub acl: Arc<InMemoryAcl>,
    pub intents: Arc<RwLock<HashMap<RideIntentId, RideIntent>>>,
    pub matches: Arc<RwLock<Vec<MatchRecord>>>,
    pub pots: Arc<RwLock<HashMap<PotId, Pot>>>,
    pub routes: Arc<RwLock<HashMap<RouteId, Route>>>,
    pub bookings: Arc<RwLock<HashMap<BookingId, Booking>>>,
    pub contracts: Arc<RwLock<HashMap<ContractId, BrokerageContract>>>,
    pending_events: Arc<RwLock<Vec<StoredEvent>>>,
}

impl AppState {
    pub fn new() -> Self {
        let state = Self {
            event_bus: Arc::new(EventBus::new()),
            acl: Arc::new(InMemoryAcl::new()),
            intents: Arc::new(RwLock::new(HashMap::new())),
            matches: Arc::new(RwLock::new(Vec::new())),
            pots: Arc::new(RwLock::new(HashMap::new())),
            routes: Arc::new(RwLock::new(HashMap::new())),
            bookings: Arc::new(RwLock::new(HashMap::new())),
            contracts: Arc::new(RwLock::new(HashMap::new())),
            pending_events: Arc::new(RwLock::new(Vec::new())),
        };
        state.register_handlers();
        state
    }

    pub fn push_events(&self, events: Vec<StoredEvent>) {
        self.pending_events.write().unwrap().extend(events);
    }

    pub async fn dispatch_pending_events(&self) -> Result<(), String> {
        loop {
            let events: Vec<StoredEvent> = {
                let mut pending = self.pending_events.write().unwrap();
                if pending.is_empty() {
                    break;
                }
                pending.drain(..).collect()
            };
            for event in events {
                self.event_bus.publish(event).await?;
            }
        }
        Ok(())
    }

    fn register_handlers(&self) {
        self.event_bus.register(Arc::new(
            crate::supply::infrastructure::event_handlers::PotFormedHandler::new(self.clone()),
        ));
        self.event_bus.register(Arc::new(
            crate::pot::infrastructure::event_handlers::PotRouteSpawnedHandler::new(self.clone()),
        ));
        self.event_bus.register(Arc::new(
            crate::booking::infrastructure::event_handlers::EphemeralRouteActivatedHandler::new(
                self.clone(),
            ),
        ));
        self.event_bus.register(Arc::new(
            crate::contract::infrastructure::event_handlers::BookingConfirmedHandler::new(
                self.clone(),
            ),
        ));
    }
}

impl Default for AppState {
    fn default() -> Self {
        Self::new()
    }
}