use serde::{Deserialize, Serialize};

use crate::shared_kernel::domain_event::StoredEvent;
use crate::shared_kernel::event_types;
use crate::shared_kernel::ids::{BookingId, PotId, RouteId, StopId, UserId};
use crate::shared_kernel::pot_payload::PotMemberSnapshot;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum BookingSource {
    Catalog,
    Pot,
    Corporate,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum BookingStatus {
    Requested,
    PendingApproval,
    Confirmed,
    Cancelled,
    Completed,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Booking {
    id: BookingId,
    source: BookingSource,
    user_id: UserId,
    route_id: RouteId,
    pot_id: Option<PotId>,
    pickup_stop_id: Option<StopId>,
    dropoff_stop_id: Option<StopId>,
    status: BookingStatus,
}

impl Booking {
    pub fn request_catalog(user_id: UserId, route_id: RouteId, flexible: bool) -> (Self, Vec<StoredEvent>) {
        let status = if flexible {
            BookingStatus::PendingApproval
        } else {
            BookingStatus::Requested
        };
        let booking = Self {
            id: BookingId::new(),
            source: BookingSource::Catalog,
            user_id,
            route_id,
            pot_id: None,
            pickup_stop_id: None,
            dropoff_stop_id: None,
            status,
        };
        let events = vec![StoredEvent::new(
            event_types::BOOKING_REQUESTED,
            booking.id.to_string(),
            booking.id.to_string(),
        )];
        (booking, events)
    }

    pub fn from_pot_member(
        pot_id: PotId,
        route_id: RouteId,
        member: &PotMemberSnapshot,
        pickup_stop_id: StopId,
        dropoff_stop_id: StopId,
    ) -> (Self, Vec<StoredEvent>) {
        let mut booking = Self {
            id: BookingId::new(),
            source: BookingSource::Pot,
            user_id: member.user_id,
            route_id,
            pot_id: Some(pot_id),
            pickup_stop_id: Some(pickup_stop_id),
            dropoff_stop_id: Some(dropoff_stop_id),
            status: BookingStatus::Requested,
        };
        let mut events = vec![StoredEvent::new(
            event_types::BOOKING_REQUESTED,
            booking.id.to_string(),
            booking.id.to_string(),
        )];
        events.extend(booking.confirm());
        (booking, events)
    }

    pub fn confirm(&mut self) -> Vec<StoredEvent> {
        if self.status == BookingStatus::Confirmed {
            return Vec::new();
        }
        self.status = BookingStatus::Confirmed;
        vec![StoredEvent::new(
            event_types::BOOKING_CONFIRMED,
            serde_json::to_string(self).unwrap_or_default(),
            self.id.to_string(),
        )]
    }

    pub fn id(&self) -> BookingId {
        self.id
    }

    pub fn source(&self) -> BookingSource {
        self.source
    }

    pub fn user_id(&self) -> UserId {
        self.user_id
    }

    pub fn route_id(&self) -> RouteId {
        self.route_id
    }

    pub fn pot_id(&self) -> Option<PotId> {
        self.pot_id
    }

    pub fn status(&self) -> BookingStatus {
        self.status
    }
}