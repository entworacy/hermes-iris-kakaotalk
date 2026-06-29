use crate::infrastructure::acl::OperatorVerificationPort;
use crate::infrastructure::app_state::AppState;
use crate::shared_kernel::domain_event::StoredEvent;
use crate::shared_kernel::event_types;
use crate::shared_kernel::ids::RouteId;
use crate::supply::domain::model::route::Route;

pub async fn handle(state: &AppState, route_id: RouteId) -> Result<Route, String> {
    let mut route = state
        .routes
        .read()
        .unwrap()
        .get(&route_id)
        .cloned()
        .ok_or("route not found")?;

    if let Some(org_id) = route.operator_org_id() {
        if !state.acl.is_verified_operator(org_id).await {
            return Err("operator not verified".into());
        }
    }

    route.activate().map_err(|e| e.to_string())?;
    state.routes.write().unwrap().insert(route_id, route.clone());

    state.push_events(vec![StoredEvent::new(
        event_types::ROUTE_ACTIVATED,
        route_id.to_string(),
        route_id.to_string(),
    )]);

    Ok(route)
}