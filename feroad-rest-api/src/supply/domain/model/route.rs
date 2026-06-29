use chrono::NaiveTime;
use serde::{Deserialize, Serialize};

use crate::shared_kernel::ids::{OrganizationId, PotId, RouteId, ScheduleId, StopId};
use crate::shared_kernel::pot_payload::PotFormedPayload;
use crate::shared_kernel::value_objects::{Capacity, GeoPoint, ServiceDate};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum RouteOrigin {
    Catalog,
    Pot { pot_id: PotId },
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum RouteType {
    Fixed,
    Flexible,
    Ephemeral,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum RouteStatus {
    Draft,
    Active,
    Inactive,
    Completed,
    Archived,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum StopType {
    Pickup,
    Dropoff,
    Regular,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Stop {
    pub id: StopId,
    pub stop_type: StopType,
    pub location: GeoPoint,
    pub label: String,
    pub order: u16,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct RouteSchedule {
    pub id: ScheduleId,
    pub service_date: ServiceDate,
    pub departure_time: NaiveTime,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Route {
    id: RouteId,
    origin: RouteOrigin,
    route_type: RouteType,
    status: RouteStatus,
    operator_org_id: Option<OrganizationId>,
    name: String,
    stops: Vec<Stop>,
    schedules: Vec<RouteSchedule>,
    capacity: Capacity,
}

impl Route {
    pub fn new_catalog_fixed(operator_org_id: OrganizationId, name: impl Into<String>) -> Self {
        Self {
            id: RouteId::new(),
            origin: RouteOrigin::Catalog,
            route_type: RouteType::Fixed,
            status: RouteStatus::Draft,
            operator_org_id: Some(operator_org_id),
            name: name.into(),
            stops: Vec::new(),
            schedules: Vec::new(),
            capacity: Capacity(40),
        }
    }

    pub fn add_stop(&mut self, stop_type: StopType, location: GeoPoint, label: impl Into<String>) {
        let order = self.stops.len() as u16;
        self.stops.push(Stop {
            id: StopId::new(),
            stop_type,
            location,
            label: label.into(),
            order,
        });
    }

    pub fn add_schedule(&mut self, service_date: ServiceDate, departure_time: NaiveTime) {
        self.schedules.push(RouteSchedule {
            id: ScheduleId::new(),
            service_date,
            departure_time,
        });
    }

    pub fn activate(&mut self) -> Result<(), &'static str> {
        if self.stops.is_empty() {
            return Err("route requires at least one stop");
        }
        if self.schedules.is_empty() {
            return Err("route requires at least one schedule");
        }
        self.status = RouteStatus::Active;
        Ok(())
    }

    pub fn id(&self) -> RouteId {
        self.id
    }

    pub fn origin(&self) -> RouteOrigin {
        self.origin
    }

    pub fn route_type(&self) -> RouteType {
        self.route_type
    }

    pub fn status(&self) -> RouteStatus {
        self.status
    }

    pub fn operator_org_id(&self) -> Option<OrganizationId> {
        self.operator_org_id
    }

    pub fn name(&self) -> &str {
        &self.name
    }

    pub fn stops(&self) -> &[Stop] {
        &self.stops
    }

    pub fn schedules(&self) -> &[RouteSchedule] {
        &self.schedules
    }

    pub fn capacity(&self) -> Capacity {
        self.capacity
    }

    pub fn is_catalog_listing(&self) -> bool {
        matches!(self.origin, RouteOrigin::Catalog) && self.status == RouteStatus::Active
    }

    pub fn pot_id(&self) -> Option<PotId> {
        match self.origin {
            RouteOrigin::Pot { pot_id } => Some(pot_id),
            RouteOrigin::Catalog => None,
        }
    }
}

pub fn spawn_ephemeral_route_from_pot(payload: &PotFormedPayload) -> Result<Route, &'static str> {
    if payload.members.is_empty() {
        return Err("pot has no members");
    }

    let mut route = Route {
        id: RouteId::new(),
        origin: RouteOrigin::Pot {
            pot_id: payload.pot_id,
        },
        route_type: RouteType::Ephemeral,
        status: RouteStatus::Draft,
        operator_org_id: None,
        name: format!("Pot route {}", payload.pot_id),
        stops: Vec::new(),
        schedules: Vec::new(),
        capacity: payload.max_capacity,
    };

    for (idx, member) in payload.members.iter().enumerate() {
        route.add_stop(
            StopType::Pickup,
            member.origin,
            format!("pickup-{}", idx),
        );
        route.add_stop(
            StopType::Dropoff,
            member.destination,
            format!("dropoff-{}", idx),
        );
    }

    route.add_schedule(payload.service_date, payload.departure_time);
    route.activate()?;
    Ok(route)
}

pub fn has_active_ephemeral_for_pot(routes: &[Route], pot_id: PotId) -> bool {
    routes.iter().any(|r| {
        matches!(r.origin, RouteOrigin::Pot { pot_id: id } if id == pot_id)
            && matches!(r.status, RouteStatus::Active | RouteStatus::Draft)
    })
}