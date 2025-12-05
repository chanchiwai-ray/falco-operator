# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for Falco charm."""

from unittest.mock import MagicMock, patch

import ops
import ops.testing
import pytest
from scenario.errors import UncaughtCharmError

from charm import Charm


class TestCharm:
    """Test Charm class."""

    @patch("charm.FalcoService")
    def test_charm_initialization(self, mock_service, mock_charm_dir):
        """Test charm initialization."""
        context = ops.testing.Context(charm_type=Charm, charm_root=mock_charm_dir)
        state = ops.testing.State()

        with context(context.on.install(), state) as manager:
            charm = manager.charm
            assert charm.falco_layout is not None
            assert charm.falco_service_file is not None
            assert charm.managed_falco_config is not None
            assert charm.falco_service is not None

    def test_charm_initialization_missing_falco_directory(self, mock_charm_dir):
        """Test charm initialization when Falco directory is missing."""
        import shutil

        context = ops.testing.Context(charm_type=Charm, charm_root=mock_charm_dir)
        state = ops.testing.State()

        # Remove the falco directory that was created by the fixture
        shutil.rmtree(mock_charm_dir / "falco")

        with pytest.raises(UncaughtCharmError, match=r"ValueError.*does not exist"):
            context.run(context.on.install(), state)

    @patch("charm.FalcoService")
    def test_on_install(self, mock_service_class, mock_charm_dir):
        """Test the install event handler."""
        mock_service = MagicMock()
        mock_service.check_active.return_value = True
        mock_service_class.return_value = mock_service

        context = ops.testing.Context(charm_type=Charm, charm_root=mock_charm_dir)
        state_in = ops.testing.State()
        state_out = context.run(context.on.install(), state_in)

        mock_service.install.assert_called_once()
        mock_service.check_active.assert_called()
        assert state_out.unit_status == ops.testing.ActiveStatus()

    @patch("charm.FalcoService")
    def test_on_install_service_not_active_after_install(self, mock_service_class, mock_charm_dir):
        """Test install event when service is not active after installation."""
        mock_service = MagicMock()
        mock_service.check_active.return_value = False
        mock_service_class.return_value = mock_service

        context = ops.testing.Context(charm_type=Charm, charm_root=mock_charm_dir)
        state_in = ops.testing.State()

        with pytest.raises(RuntimeError, match=r"Falco service is not running"):
            context.run(context.on.install(), state_in)

        mock_service.install.assert_called_once()
        mock_service.check_active.assert_called_once()

    @patch("charm.FalcoService")
    def test_on_upgrade_charm(self, mock_service_class, mock_charm_dir):
        """Test the upgrade_charm event handler."""
        mock_service = MagicMock()
        mock_service.check_active.return_value = True
        mock_service_class.return_value = mock_service

        context = ops.testing.Context(charm_type=Charm, charm_root=mock_charm_dir)
        state_in = ops.testing.State()
        state_out = context.run(context.on.upgrade_charm(), state_in)

        mock_service.install.assert_called_once()
        mock_service.check_active.assert_called()
        assert state_out.unit_status == ops.testing.ActiveStatus()

    @patch("charm.FalcoService")
    def test_on_upgrade_fails_service_exception(self, mock_service_class, mock_charm_dir):
        """Test upgrade_charm event when service installation raises an exception."""
        mock_service = MagicMock()
        mock_service.install.side_effect = OSError("Upgrade failed")
        mock_service_class.return_value = mock_service

        context = ops.testing.Context(charm_type=Charm, charm_root=mock_charm_dir)
        state_in = ops.testing.State()

        with pytest.raises(UncaughtCharmError, match=r"OSError.*Upgrade failed"):
            context.run(context.on.upgrade_charm(), state_in)

        mock_service.install.assert_called_once()

    @patch("charm.FalcoService")
    def test_on_upgrade_service_not_active_after_upgrade(self, mock_service_class, mock_charm_dir):
        """Test upgrade_charm event when service is not active after upgrade."""
        mock_service = MagicMock()
        mock_service.check_active.return_value = False
        mock_service_class.return_value = mock_service

        context = ops.testing.Context(charm_type=Charm, charm_root=mock_charm_dir)
        state_in = ops.testing.State()

        with pytest.raises(RuntimeError, match=r"Falco service is not running"):
            context.run(context.on.upgrade_charm(), state_in)

        mock_service.install.assert_called_once()
        mock_service.check_active.assert_called_once()

    @patch("charm.FalcoService")
    def test_on_remove(self, mock_service_class, mock_charm_dir):
        """Test the remove event handler."""
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        context = ops.testing.Context(charm_type=Charm, charm_root=mock_charm_dir)
        state_in = ops.testing.State()
        state_out = context.run(context.on.remove(), state_in)

        mock_service.remove.assert_called_once()
        assert state_out.unit_status == ops.testing.MaintenanceStatus("Removing Falco service")

    @patch("charm.FalcoService")
    def test_on_remove_fails_service_exception(self, mock_service_class, mock_charm_dir):
        """Test remove event when service removal raises an exception."""
        mock_service = MagicMock()
        mock_service.remove.side_effect = PermissionError("Cannot remove service")
        mock_service_class.return_value = mock_service

        context = ops.testing.Context(charm_type=Charm, charm_root=mock_charm_dir)
        state_in = ops.testing.State()

        with pytest.raises(UncaughtCharmError, match=r"PermissionError.*Cannot remove service"):
            context.run(context.on.remove(), state_in)

        mock_service.remove.assert_called_once()

    @patch("charm.FalcoService")
    def test_update_status_active(self, mock_service_class, mock_charm_dir):
        """Test update_status when Falco service is running."""
        mock_service = MagicMock()
        mock_service.check_active.return_value = True
        mock_service_class.return_value = mock_service

        context = ops.testing.Context(charm_type=Charm, charm_root=mock_charm_dir)
        state_in = ops.testing.State()
        state_out = context.run(context.on.update_status(), state_in)

        mock_service.check_active.assert_called_once()
        assert state_out.unit_status == ops.testing.ActiveStatus()

    @patch("charm.FalcoService")
    def test_update_status_inactive(self, mock_service_class, mock_charm_dir):
        """Test update_status when Falco service is not running."""
        mock_service = MagicMock()
        mock_service.check_active.return_value = False
        mock_service_class.return_value = mock_service

        context = ops.testing.Context(charm_type=Charm, charm_root=mock_charm_dir)
        state_in = ops.testing.State()

        with pytest.raises(
            UncaughtCharmError, match=r"RuntimeError.*Falco service is not running"
        ):
            context.run(context.on.update_status(), state_in)


class TestCharmConfigHandling:
    """Test charm configuration handling."""

    @patch("charm.FalcoService")
    @patch("charm.SettingRepoManager")
    def test_config_changed_with_setting_repo(
        self, mock_repo_manager_class, mock_service_class, mock_charm_dir
    ):
        """Test config_changed event with setting repo configured."""
        mock_service = MagicMock()
        mock_service.check_active.return_value = True
        mock_service_class.return_value = mock_service

        mock_repo_manager = MagicMock()
        mock_repo_manager_class.return_value = mock_repo_manager

        context = ops.testing.Context(charm_type=Charm, charm_root=mock_charm_dir)
        state_in = ops.testing.State(config={"setting-repo": "git+ssh://github.com/user/repo.git"})
        state_out = context.run(context.on.config_changed(), state_in)

        assert mock_repo_manager.sync.called
        assert mock_service.configure.called
        assert state_out.unit_status == ops.testing.ActiveStatus()

    @patch("charm.FalcoService")
    def test_config_changed_without_setting_repo(self, mock_service_class, mock_charm_dir):
        """Test config_changed event without setting repo."""
        mock_service = MagicMock()
        mock_service.check_active.return_value = True
        mock_service_class.return_value = mock_service

        context = ops.testing.Context(charm_type=Charm, charm_root=mock_charm_dir)
        state_in = ops.testing.State()
        state_out = context.run(context.on.config_changed(), state_in)

        mock_service.configure.assert_not_called()
        assert state_out.unit_status == ops.testing.ActiveStatus()

    @patch("charm.FalcoService")
    def test_config_changed_clears_existing_rules(self, mock_service_class, mock_charm_dir):
        """Test config_changed clears existing rules when setting repo is empty."""
        mock_service = MagicMock()
        mock_service.check_active.return_value = True
        mock_service_class.return_value = mock_service

        # Create some existing rule files
        falco_dir = mock_charm_dir / "falco"
        rules_dir = falco_dir / "etc/falco/rules.d"
        configs_dir = falco_dir / "etc/falco/config.overrides.d"

        # Ensure directories exist
        rules_dir.mkdir(parents=True, exist_ok=True)
        configs_dir.mkdir(parents=True, exist_ok=True)

        # Add some test files
        (rules_dir / "custom_rule.yaml").write_text("test rule")
        (configs_dir / "custom_config.yaml").write_text("test config")

        context = ops.testing.Context(charm_type=Charm, charm_root=mock_charm_dir)
        state_in = ops.testing.State(config={"setting-repo": ""})
        state_out = context.run(context.on.config_changed(), state_in)

        # Verify files were deleted
        assert not (rules_dir / "custom_rule.yaml").exists()
        assert not (configs_dir / "custom_config.yaml").exists()
        assert state_out.unit_status == ops.testing.ActiveStatus()

    @patch("charm.FalcoService")
    def test_config_changed_validation_error(self, mock_service_class, mock_charm_dir):
        """Test config_changed with validation error."""
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        # Mock load_config to raise ValidationError
        with patch.object(Charm, "load_config") as mock_load_config:
            import pydantic
            from pydantic_core import InitErrorDetails

            mock_load_config.side_effect = pydantic.ValidationError.from_exception_data(
                "CharmConfig",
                [
                    InitErrorDetails(
                        type="value_error", loc=("field",), input="bad", ctx={"error": "Invalid"}
                    )
                ],
            )

            context = ops.testing.Context(charm_type=Charm, charm_root=mock_charm_dir)
            state_in = ops.testing.State(
                config={"setting-repo": "git+ssh://github.com/user/repo.git"}
            )
            state_out = context.run(context.on.config_changed(), state_in)

            assert state_out.unit_status == ops.testing.BlockedStatus("Invalid configuration")

    @patch("charm.FalcoService")
    @patch("charm.SettingRepoManager")
    def test_config_changed_git_clone_error(
        self, mock_repo_manager_class, mock_service_class, mock_charm_dir
    ):
        """Test config_changed with git clone error."""
        from config import GitCloneError

        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        mock_repo_manager = MagicMock()
        mock_repo_manager.sync.side_effect = GitCloneError("Clone failed")
        mock_repo_manager_class.return_value = mock_repo_manager

        context = ops.testing.Context(charm_type=Charm, charm_root=mock_charm_dir)
        state_in = ops.testing.State(config={"setting-repo": "git+ssh://github.com/user/repo.git"})
        state_out = context.run(context.on.config_changed(), state_in)

        assert state_out.unit_status == ops.testing.BlockedStatus("Failed to clone setting repo")

    @patch("charm.FalcoService")
    @patch("charm.SettingRepoManager")
    def test_config_changed_ssh_keyscan_error(
        self, mock_repo_manager_class, mock_service_class, mock_charm_dir
    ):
        """Test config_changed with SSH keyscan error."""
        from config import SshKeyScanError

        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        mock_repo_manager = MagicMock()
        mock_repo_manager.sync.side_effect = SshKeyScanError("Keyscan failed")
        mock_repo_manager_class.return_value = mock_repo_manager

        context = ops.testing.Context(charm_type=Charm, charm_root=mock_charm_dir)
        state_in = ops.testing.State(config={"setting-repo": "git+ssh://github.com/user/repo.git"})
        state_out = context.run(context.on.config_changed(), state_in)

        assert state_out.unit_status == ops.testing.BlockedStatus("Failed to clone setting repo")

    @patch("charm.FalcoService")
    @patch("charm.SettingRepoManager")
    def test_config_changed_rsync_error(
        self, mock_repo_manager_class, mock_service_class, mock_charm_dir
    ):
        """Test config_changed with rsync error."""
        from config import RsyncError

        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        mock_repo_manager = MagicMock()
        mock_repo_manager.sync.side_effect = RsyncError("Rsync failed")
        mock_repo_manager_class.return_value = mock_repo_manager

        context = ops.testing.Context(charm_type=Charm, charm_root=mock_charm_dir)
        state_in = ops.testing.State(config={"setting-repo": "git+ssh://github.com/user/repo.git"})
        state_out = context.run(context.on.config_changed(), state_in)

        assert state_out.unit_status == ops.testing.BlockedStatus("Failed to clone setting repo")


class TestCharmEventObservers:
    """Test charm event observers are properly registered."""

    @patch("charm.FalcoService")
    def test_all_events_observed(self, mock_service_class, mock_charm_dir):
        """Test that all expected events are observed."""
        context = ops.testing.Context(charm_type=Charm, charm_root=mock_charm_dir)
        state = ops.testing.State()

        with context(context.on.install(), state) as manager:
            charm = manager.charm

            # Check that observers are registered
            assert len(charm.framework._observers) > 0
