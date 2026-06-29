use chrono::NaiveTime;
use serde::{Deserialize, Serialize};

use crate::shared_kernel::domain_event::StoredEvent;
use crate::shared_kernel::event_types;
use crate::shared_kernel::ids::{PotId, RideIntentId, RouteId, UserId};
use crate::shared_kernel::pot_payload::{PotFormedPayload, PotMemberSnapshot};
use crate::shared_kernel::value_objects::{Capacity, CorridorSignature, ServiceDate, TimeWindow};

use super::ride_intent::RideIntent;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum PotStatus {
    Gathering,
    Formed,
    SpawningRoute,
    RouteSpawned,
    Converted,
    Dissolved,
    Expired,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct PotMember {
    pub intent_id: RideIntentId,
    pub user_id: UserId,
    pub origin: crate::shared_kernel::value_objects::GeoPoint,
    pub destination: crate::shared_kernel::value_objects::GeoPoint,
    pub passenger_count: u16,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Pot {
    id: PotId,
    corridor: CorridorSignature,
    service_date: ServiceDate,
    departure_time: NaiveTime,
    members: Vec<PotMember>,
    min_members: u16,
    max_capacity: Capacity,
    route_id: Option<RouteId>,
    status: PotStatus,
}

impl Pot {
    pub fn create_from_intents(intents: &[RideIntent]) -> Result<(Self, Vec<StoredEvent>), &'static str> {
        if intents.len() < 2 {
            return Err("pot requires at least two intents");
        }

        let service_date = intents[0].service_date();
        let departure_time = intents[0].departure_time();

        let members: Vec<PotMember> = intents
            .iter()
            .map(|i| PotMember {
                intent_id: i.id(),
                user_id: i.user_id(),
                origin: i.origin(),
                destination: i.destination(),
                passenger_count: i.passenger_count(),
            })
            .collect();

        let total_passengers: u16 = members.iter().map(|m| m.passenger_count).sum();
        let max_capacity = Capacity(total_passengers.max(2));

        let mut pot = Self {
            id: PotId::new(),
            corridor: CorridorSignature {
                origin_zone: "origin".into(),
                destination_zone: "destination".into(),
                time_band: format!("{departure_time}"),
            },
            service_date,
            departure_time,
            members,
            min_members: 2,
            max_capacity,
            route_id: None,
            status: PotStatus::Gathering,
        };

        let mut events = vec![StoredEvent::new(
            event_types::POT_CREATED,
            serde_json::to_string(&pot.id()).unwrap_or_default(),
            pot.id.to_string(),
        )];

        for member in &pot.members {
            events.push(StoredEvent::new(
                event_types::POT_MEMBER_JOINED,
                serde_json::to_string(member).unwrap_or_default(),
                pot.id.to_string(),
            ));
        }

        events.extend(pot.try_form()?);
        Ok((pot, events))
    }

    pub fn try_form(&mut self) -> Result<Vec<StoredEvent>, &'static str> {
        if self.status != PotStatus::Gathering {
            return Ok(Vec::new());
        }
        if self.members.len() < self.min_members as usize {
            return Ok(Vec::new());
        }

        self.status = PotStatus::Formed;
        let payload = self.formed_payload();
        Ok(vec![StoredEvent::new(
            event_types::POT_FORMED,
            serde_json::to_string(&payload).unwrap_or_default(),
            self.id.to_string(),
        )])
    }

    pub fn mark_spawning_route(&mut self) {
        if self.status == PotStatus::Formed {
            self.status = PotStatus::SpawningRoute;
        }
    }

    pub fn mark_route_spawned(&mut self, route_id: RouteId) -> Vec<StoredEvent> {
        self.route_id = Some(route_id);
        self.status = PotStatus::RouteSpawned;
        vec![StoredEvent::new(
            event_types::POT_ROUTE_SPAWNED,
            serde_json::to_string(&route_id).unwrap_or_default(),
            self.id.to_string(),
        )]
    }

    pub fn mark_converted(&mut self) {
        self.status = PotStatus::Converted;
    }

    pub fn formed_payload(&self) -> PotFormedPayload {
        PotFormedPayload {
            pot_id: self.id,
            service_date: self.service_date,
            departure_time: self.departure_time,
            max_capacity: self.max_capacity,
            members: self
                .members
                .iter()
                .map(|m| PotMemberSnapshot {
                    intent_id: m.intent_id,
                    user_id: m.user_id,
                    origin: m.origin,
                    destination: m.destination,
                    passenger_count: m.passenger_count,
                })
                .collect(),
        }
    }

    pub fn id(&self) -> PotId {
        self.id
    }

    pub fn status(&self) -> PotStatus {
        self.status
    }

    pub fn route_id(&self) -> Option<RouteId> {
        self.route_id
    }

    pub fn members(&self) -> &[PotMember] {
        &self.members
    }

    pub fn service_date(&self) -> ServiceDate {
        self.service_date
    }

    pub fn departure_time(&self) -> NaiveTime {
        self.departure_time
    }

    pub fn max_capacity(&self) -> Capacity {
        self.max_capacity
    }

    pub fn time_window(&self) -> TimeWindow {
        let start = crate::shared_kernel::value_objects::departure_datetime(
            self.service_date,
            self.departure_time,
        );
        TimeWindow {
            start,
            end: start,
        }
    }
}