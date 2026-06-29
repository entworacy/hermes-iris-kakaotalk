use serde::{Deserialize, Serialize};

use crate::shared_kernel::ids::OrganizationId;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum OrganizationType {
    Corporate,
    Operator,
    Platform,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum OrganizationStatus {
    Draft,
    PendingVerification,
    Verified,
    Suspended,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Organization {
    id: OrganizationId,
    org_type: OrganizationType,
    status: OrganizationStatus,
}

impl Organization {
    pub fn new(org_type: OrganizationType) -> Self {
        Self {
            id: OrganizationId::new(),
            org_type,
            status: OrganizationStatus::Draft,
        }
    }

    pub fn verify(mut self) -> Self {
        self.status = OrganizationStatus::Verified;
        self
    }

    pub fn id(&self) -> OrganizationId {
        self.id
    }

    pub fn org_type(&self) -> OrganizationType {
        self.org_type
    }

    pub fn status(&self) -> OrganizationStatus {
        self.status
    }

    pub fn is_verified_operator(&self) -> bool {
        self.org_type == OrganizationType::Operator && self.status == OrganizationStatus::Verified
    }
}