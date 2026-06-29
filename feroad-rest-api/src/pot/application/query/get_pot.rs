use crate::infrastructure::app_state::AppState;
use crate::pot::domain::model::pot::Pot;
use crate::shared_kernel::ids::PotId;

pub async fn handle(state: &AppState, pot_id: PotId) -> Result<Pot, String> {
    state
        .pots
        .read()
        .unwrap()
        .get(&pot_id)
        .cloned()
        .ok_or_else(|| "pot not found".into())
}