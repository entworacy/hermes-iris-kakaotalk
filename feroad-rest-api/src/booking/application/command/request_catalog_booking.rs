use crate::infrastructure::app_state::AppState;
use crate::booking::domain::model::booking::Booking;
use crate::shared_kernel::ids::{RouteId, UserId};
use crate::supply::domain::model::route::RouteType;

pub async fn handle(
    state: &AppState,
    user_id: UserId,
    route_id: RouteId,
) -> Result<Booking, String> {
    let route = state
        .routes
        .read()
        .unwrap()
        .get(&route_id)
        .cloned()
        .ok_or("route not found")?;

    if !route.is_catalog_listing() {
        return Err("route is not available for catalog booking".into());
    }

    let flexible = route.route_type() == RouteType::Flexible;
    let (mut booking, mut events) = Booking::request_catalog(user_id, route_id, flexible);

    if !flexible {
        events.extend(booking.confirm());
    }
    state.push_events(events);

    state
        .bookings
        .write()
        .unwrap()
        .insert(booking.id(), booking.clone());

    Ok(booking)
}