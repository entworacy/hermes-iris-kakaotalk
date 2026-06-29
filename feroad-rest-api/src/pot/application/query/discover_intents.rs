use crate::infrastructure::app_state::AppState;
use crate::pot::domain::model::ride_intent::{RideIntent, RideIntentStatus};
use crate::pot::domain::service::compatibility_scorer::CompatibilityScorer;
use crate::shared_kernel::ids::RideIntentId;
use crate::shared_kernel::value_objects::Capacity;

pub async fn handle(
    state: &AppState,
    for_intent_id: RideIntentId,
) -> Result<Vec<RideIntent>, String> {
    let source = state
        .intents
        .read()
        .unwrap()
        .get(&for_intent_id)
        .cloned()
        .ok_or("intent not found")?;

    let max_capacity = Capacity(40);
    let intents: Vec<RideIntent> = state
        .intents
        .read()
        .unwrap()
        .values()
        .filter(|i| i.id() != for_intent_id && i.status() == RideIntentStatus::Open)
        .filter(|i| CompatibilityScorer::is_compatible(&source, i, max_capacity))
        .cloned()
        .collect();

    Ok(intents)
}