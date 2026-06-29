use chrono::NaiveTime;
use serde::{Deserialize, Serialize};

use crate::shared_kernel::ids::{PotId, RideIntentId, UserId};
use crate::shared_kernel::value_objects::{Capacity, GeoPoint, ServiceDate};

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct PotMemberSnapshot {
    pub intent_id: RideIntentId,
    pub user_id: UserId,
    pub origin: GeoPoint,
    pub destination: GeoPoint,
    pub passenger_count: u16,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct PotFormedPayload {
    pub pot_id: PotId,
    pub service_date: ServiceDate,
    pub departure_time: NaiveTime,
    pub max_capacity: Capacity,
    pub members: Vec<PotMemberSnapshot>,
}