use serde::{Deserialize, Serialize};

use crate::booking::domain::model::booking::{Booking, BookingSource};
use crate::shared_kernel::domain_event::StoredEvent;
use crate::shared_kernel::event_types;
use crate::shared_kernel::ids::{BookingId, ContractId, OrganizationId, PotId, RouteId, UserId};
use crate::shared_kernel::value_objects::Money;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ContractStatus {
    Draft,
    Active,
    Terminated,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum BrokerageType {
    Catalog,
    PotEphemeral,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct BrokerageContract {
    id: ContractId,
    booking_id: BookingId,
    brokerage_type: BrokerageType,
    broker_role: &'static str,
    operator_org_id: Option<OrganizationId>,
    rider_user_id: UserId,
    route_id: RouteId,
    pot_id: Option<PotId>,
    fare_snapshot: Money,
    terms_version: &'static str,
    status: ContractStatus,
}

impl BrokerageContract {
    pub fn from_booking(booking: &Booking) -> (Self, Vec<StoredEvent>) {
        let brokerage_type = match booking.source() {
            BookingSource::Catalog | BookingSource::Corporate => BrokerageType::Catalog,
            BookingSource::Pot => BrokerageType::PotEphemeral,
        };

        let mut contract = Self {
            id: ContractId::new(),
            booking_id: booking.id(),
            brokerage_type,
            broker_role: "feroad",
            operator_org_id: None,
            rider_user_id: booking.user_id(),
            route_id: booking.route_id(),
            pot_id: booking.pot_id(),
            fare_snapshot: Money {
                amount: 0,
                currency: "KRW",
            },
            terms_version: "mvp-1",
            status: ContractStatus::Draft,
        };

        let mut events = vec![StoredEvent::new(
            event_types::CONTRACT_DRAFTED,
            contract.id.to_string(),
            contract.id.to_string(),
        )];
        events.extend(contract.activate());
        (contract, events)
    }

    pub fn activate(&mut self) -> Vec<StoredEvent> {
        self.status = ContractStatus::Active;
        vec![StoredEvent::new(
            event_types::CONTRACT_ACTIVATED,
            serde_json::to_string(self).unwrap_or_default(),
            self.id.to_string(),
        )]
    }

    pub fn id(&self) -> ContractId {
        self.id
    }

    pub fn booking_id(&self) -> BookingId {
        self.booking_id
    }

    pub fn brokerage_type(&self) -> BrokerageType {
        self.brokerage_type
    }

    pub fn status(&self) -> ContractStatus {
        self.status
    }

    pub fn pot_id(&self) -> Option<PotId> {
        self.pot_id
    }
}