# Copyright 2025 John Brosnihan
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Tests for debug status endpoint.

Validates the /debug/status endpoint for manual status publishing testing.
"""

from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from spec_compiler.config import settings


@pytest.fixture
def mock_publisher():
    """Mock PlanSchedulerPublisher for testing."""
    with patch("spec_compiler.app.routes.health.PlanSchedulerPublisher") as mock_cls:
        mock_instance = Mock()
        mock_cls.return_value = mock_instance
        yield mock_instance


class TestDebugStatusEndpoint:
    """Tests for /debug/status endpoint."""

    def test_debug_status_disabled_in_production(self, test_client: TestClient) -> None:
        """Test that debug endpoint is disabled in production."""
        original_env = settings.app_env
        try:
            # Temporarily set to production
            settings.app_env = "production"
            
            response = test_client.post("/debug/status")
            
            assert response.status_code == 403
            data = response.json()
            assert "detail" in data
            assert "production" in data["detail"].lower()
        finally:
            settings.app_env = original_env

    def test_debug_status_enabled_in_development(
        self, test_client: TestClient, mock_publisher: Mock
    ) -> None:
        """Test that debug endpoint works in development."""
        original_env = settings.app_env
        try:
            # Ensure we're in development mode
            settings.app_env = "development"
            
            response = test_client.post("/debug/status")
            
            # Should succeed
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "published"
            assert "plan_id" in data
            assert data["plan_id"] == "debug-test-plan"
            
            # Verify publish_status was called
            assert mock_publisher.publish_status.call_count == 1
            msg = mock_publisher.publish_status.call_args[0][0]
            assert msg.plan_id == "debug-test-plan"
            assert msg.spec_index == 0
            assert msg.status == "in_progress"
            assert msg.request_id == "debug-test-request"
        finally:
            settings.app_env = original_env

    def test_debug_status_returns_500_on_config_error(
        self, test_client: TestClient
    ) -> None:
        """Test that debug endpoint returns 500 when publisher not configured."""
        from spec_compiler.services.plan_scheduler_publisher import ConfigurationError
        
        original_env = settings.app_env
        try:
            settings.app_env = "development"
            
            with patch("spec_compiler.app.routes.health.PlanSchedulerPublisher") as mock_cls:
                mock_cls.side_effect = ConfigurationError("Not configured")
                
                response = test_client.post("/debug/status")
                
                assert response.status_code == 500
                data = response.json()
                assert "detail" in data
                assert data["detail"]["error"] == "publisher_not_configured"
        finally:
            settings.app_env = original_env

    def test_debug_status_returns_503_on_publish_error(
        self, test_client: TestClient, mock_publisher: Mock
    ) -> None:
        """Test that debug endpoint returns 503 when publish fails."""
        original_env = settings.app_env
        try:
            settings.app_env = "development"
            
            # Make publish_status raise an exception
            mock_publisher.publish_status.side_effect = Exception("Pub/Sub error")
            
            response = test_client.post("/debug/status")
            
            assert response.status_code == 503
            data = response.json()
            assert "detail" in data
            assert data["detail"]["error"] == "publish_failed"
        finally:
            settings.app_env = original_env
