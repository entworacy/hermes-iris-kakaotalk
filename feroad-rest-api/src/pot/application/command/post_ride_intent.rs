use chrono::NaiveTime;

use crate::infrastructure::acl::UserProfilePort;
use crate::infrastructure::app_state::AppState;
use crate::pot::domain::model::ride_intent::RideIntent;
use crate::shared_kernel::domain_event::StoredEvent;
use crate::shared_kernel::event_types;
use crate::shared_kernel::ids::{OrganizationId, UserId};
use crate::shared_kernel::value_objects::{GeoPoint, ServiceDate};

pub struct PostRideIntentCommand {
    pub user_id: UserId,
    pub origin: GeoPoint,
    pub destination: GeoPoint,
    pub service_date: ServiceDate,
    pub departure_time: NaiveTime,
    pub passenger_count: u16,
    pub corporate_org_id: Option<OrganizationId>,
}

pub async fn handle(
    state: &AppState,
    cmd: PostRideIntentCommand,
) -> Result<RideIntent, String> {
    if !state.acl.is_active_user(cmd.user_id).await {
        return Err("user is not active".into());
    }

    let intent = RideIntent::post(
        cmd.user_id,
        cmd.origin,
        cmd.destination,
        cmd.service_date,
        cmd.departure_time,
        cmd.passenger_count,
        cmd.corporate_org_id,
    );

    state
        .intents
        .write()
        .unwrap()
        .insert(intent.id(), intent.clone());

    state.push_events(vec![StoredEvent::new(
        event_types::RIDE_INTENT_POSTED,
        intent.id().to_string(),
        intent.id().to_string(),
    )]);

    Ok(intent)
}