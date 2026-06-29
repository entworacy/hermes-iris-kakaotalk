use chrono::{DateTime, NaiveDate, NaiveTime, Utc};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct GeoPoint {
    pub lat: f64,
    pub lng: f64,
}

impl GeoPoint {
    pub fn new(lat: f64, lng: f64) -> Result<Self, &'static str> {
        if !(-90.0..=90.0).contains(&lat) || !(-180.0..=180.0).contains(&lng) {
            return Err("invalid coordinates");
        }
        Ok(Self { lat, lng })
    }

    pub fn distance_meters(&self, other: &Self) -> f64 {
        const R: f64 = 6_371_000.0;
        let d_lat = (other.lat - self.lat).to_radians();
        let d_lng = (other.lng - self.lng).to_radians();
        let a = (d_lat / 2.0).sin().powi(2)
            + self.lat.to_radians().cos()
                * other.lat.to_radians().cos()
                * (d_lng / 2.0).sin().powi(2);
        let c = 2.0 * a.sqrt().atan2((1.0 - a).sqrt());
        R * c
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct ServiceDate(pub NaiveDate);

impl ServiceDate {
    pub fn new(date: NaiveDate) -> Self {
        Self(date)
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct TimeWindow {
    pub start: DateTime<Utc>,
    pub end: DateTime<Utc>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct Capacity(pub u16);

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct Money {
    pub amount: i64,
    pub currency: &'static str,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct CorridorSignature {
    pub origin_zone: String,
    pub destination_zone: String,
    pub time_band: String,
}

pub fn departure_datetime(date: ServiceDate, time: NaiveTime) -> DateTime<Utc> {
    date.0.and_time(time).and_utc()
}

pub fn minutes_apart(a: DateTime<Utc>, b: DateTime<Utc>) -> i64 {
    (a - b).num_minutes().abs()
}