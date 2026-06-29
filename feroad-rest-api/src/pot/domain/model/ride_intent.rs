use chrono::NaiveTime;
use serde::{Deserialize, Serialize};

use crate::shared_kernel::ids::{OrganizationId, PotId, RideIntentId, UserId};
use crate::shared_kernel::value_objects::{GeoPoint, ServiceDate};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum RideIntentStatus {
    Open,
    Matched,
    Withdrawn,
    Expired,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct RideIntent {
    id: RideIntentId,
    user_id: UserId,
    origin: GeoPoint,
    destination: GeoPoint,
    service_date: ServiceDate,
    departure_time: NaiveTime,
    passenger_count: u16,
    corporate_org_id: Option<OrganizationId>,
    pot_id: Option<PotId>,
    status: RideIntentStatus,
}

impl RideIntent {
    pub fn post(
        user_id: UserId,
        origin: GeoPoint,
        destination: GeoPoint,
        service_date: ServiceDate,
        departure_time: NaiveTime,
        passenger_count: u16,
        corporate_org_id: Option<OrganizationId>,
    ) -> Self {
        Self {
            id: RideIntentId::new(),
            user_id,
            origin,
            destination,
            service_date,
            departure_time,
            passenger_count,
            corporate_org_id,
            pot_id: None,
            status: RideIntentStatus::Open,
        }
    }

    pub fn withdraw(&mut self) -> Result<(), &'static str> {
        if self.status != RideIntentStatus::Open {
            return Err("only open intents can be withdrawn");
        }
        self.status = RideIntentStatus::Withdrawn;
        Ok(())
    }

    pub fn mark_matched(&mut self, pot_id: PotId) {
        self.pot_id = Some(pot_id);
        self.status = RideIntentStatus::Matched;
    }

    pub fn id(&self) -> RideIntentId {
        self.id
    }

    pub fn user_id(&self) -> UserId {
        self.user_id
    }

    pub fn origin(&self) -> GeoPoint {
        self.origin
    }

    pub fn destination(&self) -> GeoPoint {
        self.destination
    }

    pub fn service_date(&self) -> ServiceDate {
        self.service_date
    }

    pub fn departure_time(&self) -> NaiveTime {
        self.departure_time
    }

    pub fn passenger_count(&self) -> u16 {
        self.passenger_count
    }

    pub fn corporate_org_id(&self) -> Option<OrganizationId> {
        self.corporate_org_id
    }

    pub fn pot_id(&self) -> Option<PotId> {
        self.pot_id
    }

    pub fn status(&self) -> RideIntentStatus {
        self.status
    }

    pub fn can_receive_like(&self) -> bool {
        self.status == RideIntentStatus::Open
    }
}