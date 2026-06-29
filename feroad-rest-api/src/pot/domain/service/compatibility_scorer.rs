use crate::pot::domain::model::ride_intent::RideIntent;
use crate::shared_kernel::value_objects::{departure_datetime, minutes_apart, Capacity};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CompatibilityBand {
    High,
    Medium,
    Low,
}

pub struct CompatibilityScore {
    pub band: CompatibilityBand,
    pub compatible: bool,
}

pub struct CompatibilityScorer;

impl CompatibilityScorer {
    pub fn score(a: &RideIntent, b: &RideIntent, max_capacity: Capacity) -> CompatibilityScore {
        let compatible = Self::is_compatible(a, b, max_capacity);
        let band = if compatible {
            CompatibilityBand::High
        } else {
            CompatibilityBand::Low
        };
        CompatibilityScore { band, compatible }
    }

    pub fn is_compatible(a: &RideIntent, b: &RideIntent, max_capacity: Capacity) -> bool {
        if a.service_date() != b.service_date() {
            return false;
        }

        let a_dt = departure_datetime(a.service_date(), a.departure_time());
        let b_dt = departure_datetime(b.service_date(), b.departure_time());
        if minutes_apart(a_dt, b_dt) > 20 {
            return false;
        }

        if a.origin().distance_meters(&b.origin()) > 700.0 {
            return false;
        }

        if a.destination().distance_meters(&b.destination()) > 700.0 {
            return false;
        }

        let total = a.passenger_count() + b.passenger_count();
        total <= max_capacity.0
    }
}