use std::collections::HashMap;
use std::sync::{Arc, RwLock};

use async_trait::async_trait;

use crate::identity::domain::model::user::UserStatus;
use crate::organization::domain::model::organization::OrganizationStatus;
use crate::shared_kernel::ids::{OrganizationId, UserId};

#[async_trait]
pub trait UserProfilePort: Send + Sync {
    async fn is_active_user(&self, user_id: UserId) -> bool;
}

#[async_trait]
pub trait OperatorVerificationPort: Send + Sync {
    async fn is_verified_operator(&self, org_id: OrganizationId) -> bool;
}

pub struct InMemoryAcl {
    users: Arc<RwLock<HashMap<UserId, UserStatus>>>,
    operators: Arc<RwLock<HashMap<OrganizationId, OrganizationStatus>>>,
}

impl InMemoryAcl {
    pub fn new() -> Self {
        Self {
            users: Arc::new(RwLock::new(HashMap::new())),
            operators: Arc::new(RwLock::new(HashMap::new())),
        }
    }

    pub fn seed_active_user(&self, user_id: UserId) {
        self.users
            .write()
            .unwrap()
            .insert(user_id, UserStatus::Active);
    }

    pub fn seed_verified_operator(&self, org_id: OrganizationId) {
        self.operators
            .write()
            .unwrap()
            .insert(org_id, OrganizationStatus::Verified);
    }
}

#[async_trait]
impl UserProfilePort for InMemoryAcl {
    async fn is_active_user(&self, user_id: UserId) -> bool {
        self.users
            .read()
            .unwrap()
            .get(&user_id)
            .map(|s| *s == UserStatus::Active)
            .unwrap_or(false)
    }
}

#[async_trait]
impl OperatorVerificationPort for InMemoryAcl {
    async fn is_verified_operator(&self, org_id: OrganizationId) -> bool {
        self.operators
            .read()
            .unwrap()
            .get(&org_id)
            .map(|s| *s == OrganizationStatus::Verified)
            .unwrap_or(false)
    }
}

impl Default for InMemoryAcl {
    fn default() -> Self {
        Self::new()
    }
}