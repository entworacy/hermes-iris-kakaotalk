use chrono::{NaiveDate, NaiveTime};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

use crate::pot::domain::model::pot::{Pot, PotStatus};
use crate::pot::domain::model::ride_intent::{RideIntent, RideIntentStatus};
use crate::shared_kernel::ids::{PotId, RideIntentId, RouteId, UserId};
use crate::shared_kernel::value_objects::{GeoPoint, ServiceDate};
use crate::supply::domain::model::route::Route;

#[derive(Debug, Deserialize)]
pub struct GeoPointDto {
    pub lat: f64,
    pub lng: f64,
}

#[derive(Debug, Deserialize)]
pub struct PostIntentRequest {
    pub user_id: Uuid,
    pub origin: GeoPointDto,
    pub destination: GeoPointDto,
    pub service_date: NaiveDate,
    pub departure_time: NaiveTime,
    pub passenger_count: u16,
}

#[derive(Debug, Deserialize)]
pub struct LikeIntentRequest {
    pub from_intent_id: Uuid,
}

#[derive(Debug, Deserialize)]
pub struct DiscoverQuery {
    pub for_intent_id: Uuid,
}

#[derive(Debug, Serialize)]
pub struct IntentResponse {
    pub id: Uuid,
    pub user_id: Uuid,
    pub status: String,
    pub pot_id: Option<Uuid>,
}

#[derive(Debug, Serialize)]
pub struct PotResponse {
    pub id: Uuid,
    pub status: String,
    pub route_id: Option<Uuid>,
    pub member_count: usize,
}

#[derive(Debug, Serialize)]
pub struct RouteSummaryResponse {
    pub id: Uuid,
    pub name: String,
    pub route_type: String,
    pub status: String,
}

impl From<RideIntent> for IntentResponse {
    fn from(i: RideIntent) -> Self {
        Self {
            id: i.id().as_uuid(),
            user_id: i.user_id().as_uuid(),
            status: intent_status_label(i.status()),
            pot_id: i.pot_id().map(|id| id.as_uuid()),
        }
    }
}

impl From<Pot> for PotResponse {
    fn from(p: Pot) -> Self {
        Self {
            id: p.id().as_uuid(),
            status: pot_status_label(p.status()),
            route_id: p.route_id().map(|id| id.as_uuid()),
            member_count: p.members().len(),
        }
    }
}

impl From<Route> for RouteSummaryResponse {
    fn from(r: Route) -> Self {
        Self {
            id: r.id().as_uuid(),
            name: r.name().to_string(),
            route_type: format!("{:?}", r.route_type()),
            status: format!("{:?}", r.status()),
        }
    }
}

fn intent_status_label(s: RideIntentStatus) -> String {
    match s {
        RideIntentStatus::Open => "open",
        RideIntentStatus::Matched => "matched",
        RideIntentStatus::Withdrawn => "withdrawn",
        RideIntentStatus::Expired => "expired",
    }
    .into()
}

fn pot_status_label(s: PotStatus) -> String {
    format!("{:?}", s).to_lowercase()
}

pub fn parse_user_id(id: Uuid) -> UserId {
    UserId::from_uuid(id)
}

pub fn parse_intent_id(id: Uuid) -> RideIntentId {
    RideIntentId::from_uuid(id)
}

pub fn parse_pot_id(id: Uuid) -> PotId {
    PotId::from_uuid(id)
}

pub fn parse_route_id(id: Uuid) -> RouteId {
    RouteId::from_uuid(id)
}

pub fn geo_from_dto(dto: GeoPointDto) -> Result<GeoPoint, &'static str> {
    GeoPoint::new(dto.lat, dto.lng)
}

pub fn service_date_from(date: NaiveDate) -> ServiceDate {
    ServiceDate::new(date)
}