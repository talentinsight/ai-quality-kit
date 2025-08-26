"""Global settings and environment configuration for AI Quality Kit."""

import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Settings:
    """Global application settings."""
    
    def __init__(self):
        # Power BI Integration Settings
        self.POWERBI_ENABLED: bool = os.getenv("POWERBI_ENABLED", "false").lower() == "true"
        self.POWERBI_TENANT_ID: Optional[str] = os.getenv("POWERBI_TENANT_ID")
        self.POWERBI_CLIENT_ID: Optional[str] = os.getenv("POWERBI_CLIENT_ID")
        self.POWERBI_CLIENT_SECRET: Optional[str] = os.getenv("POWERBI_CLIENT_SECRET")
        self.POWERBI_WORKSPACE_ID: Optional[str] = os.getenv("POWERBI_WORKSPACE_ID")
        self.POWERBI_DATASET_NAME: str = os.getenv("POWERBI_DATASET_NAME", "AIQK Results")
        self.POWERBI_EMBED_REPORT_URL: Optional[str] = os.getenv("POWERBI_EMBED_REPORT_URL")
        
        # Reports Configuration
        self.REPORTS_DIR: str = os.getenv("REPORTS_DIR", "./reports")
        self.REPORT_AUTO_DELETE_MINUTES: int = int(os.getenv("REPORT_AUTO_DELETE_MINUTES", "10"))
        
        # Audit Configuration
        self.AUDIT_ENABLED: bool = os.getenv("AUDIT_ENABLED", "true").lower() == "true"
        
        # Ragas Evaluation Configuration
        self.RAGAS_ENABLED: bool = os.getenv("RAGAS_ENABLED", "false").lower() == "true"
    
    def validate_powerbi_config(self) -> bool:
        """Validate Power BI configuration when enabled."""
        if not self.POWERBI_ENABLED:
            return True
            
        required_fields = [
            self.POWERBI_TENANT_ID,
            self.POWERBI_CLIENT_ID,
            self.POWERBI_CLIENT_SECRET,
            self.POWERBI_WORKSPACE_ID
        ]
        
        return all(field is not None and field.strip() != "" for field in required_fields)
    
    def get_powerbi_config_dict(self) -> dict:
        """Get Power BI configuration as dictionary for API responses."""
        return {
            "powerbi_enabled": self.POWERBI_ENABLED,
            "powerbi_embed_report_url": self.POWERBI_EMBED_REPORT_URL
        }


# Global settings instance
settings = Settings()
