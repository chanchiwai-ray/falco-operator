# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for config module."""

from unittest.mock import MagicMock, mock_open, patch

import pytest

from config import (
    CharmConfig,
    GitCloneError,
    RsyncError,
    SettingRepoManager,
    SshKeyScanError,
    SshKeyWriteError,
)


class TestCharmConfig:
    """Test CharmConfig class."""

    def test_init_empty(self):
        """Test initialization with empty values."""
        config = CharmConfig()
        assert config.setting_repo == ""
        assert config.setting_repo_ssh_key_id is None

    def test_init_with_values(self):
        """Test initialization with values."""
        config = CharmConfig(
            setting_repo="git+ssh://github.com/user/repo.git",
        )
        assert config.setting_repo == "git+ssh://github.com/user/repo.git"
        assert config.setting_repo_ssh_key_id is None

    def test_init_with_invalid_url(self):
        """Test initialization with invalid URL."""
        with pytest.raises(ValueError, match="Invalid setting repo URL"):
            CharmConfig(setting_repo="not a url at all")

    def test_init_with_unsupported_scheme(self):
        """Test initialization with unsupported URL scheme."""
        with pytest.raises(ValueError, match="Only git\\+ssh are supported"):
            CharmConfig(setting_repo="https://github.com/user/repo.git")


class TestSettingRepoManager:
    """Test SettingRepoManager class."""

    def test_init(self, mock_charm):
        """Test SettingRepoManager initialization."""
        config = CharmConfig(setting_repo="git+ssh://github.com/user/repo.git")
        manager = SettingRepoManager(mock_charm.model, config)

        assert manager.model == mock_charm.model
        assert manager.charm_config == config

    def test_url_property(self, mock_charm):
        """Test url property."""
        config = CharmConfig(setting_repo="git+ssh://github.com/user/repo.git?ref=main")
        manager = SettingRepoManager(mock_charm.model, config)

        assert manager.url == "git+ssh://github.com/user/repo.git"

    def test_url_property_without_query(self, mock_charm):
        """Test url property without query params."""
        config = CharmConfig(setting_repo="git+ssh://github.com/user/repo.git")
        manager = SettingRepoManager(mock_charm.model, config)

        assert manager.url == "git+ssh://github.com/user/repo.git"

    def test_ref_property(self, mock_charm):
        """Test ref property."""
        config = CharmConfig(setting_repo="git+ssh://github.com/user/repo.git?ref=main")
        manager = SettingRepoManager(mock_charm.model, config)

        assert manager.ref == "main"

    def test_ref_property_empty(self, mock_charm):
        """Test ref property when not specified."""
        config = CharmConfig(setting_repo="git+ssh://github.com/user/repo.git")
        manager = SettingRepoManager(mock_charm.model, config)

        assert manager.ref == ""

    def test_host_property(self, mock_charm):
        """Test host property."""
        config = CharmConfig(setting_repo="git+ssh://github.com/user/repo.git")
        manager = SettingRepoManager(mock_charm.model, config)

        assert manager.host == "github.com"

    def test_sub_path_property(self, mock_charm):
        """Test sub_path property."""
        config = CharmConfig(setting_repo="git+ssh://github.com/user/repo.git?sub_path=configs")
        manager = SettingRepoManager(mock_charm.model, config)

        assert manager.sub_path == "configs"

    def test_sub_path_property_empty(self, mock_charm):
        """Test sub_path property when not specified."""
        config = CharmConfig(setting_repo="git+ssh://github.com/user/repo.git")
        manager = SettingRepoManager(mock_charm.model, config)

        assert manager.sub_path == ""

    def test_ssh_private_key_no_secret(self, mock_charm):
        """Test ssh_private_key when no secret is configured."""
        config = CharmConfig(setting_repo="git+ssh://github.com/user/repo.git")
        manager = SettingRepoManager(mock_charm.model, config)

        assert manager.ssh_private_key == ""

    def test_ssh_private_key_with_secret(self, mock_charm):
        """Test ssh_private_key with secret."""
        config = CharmConfig(
            setting_repo="git+ssh://github.com/user/repo.git",
        )
        # Manually set the secret ID after construction
        mock_secret = MagicMock()
        mock_secret.id = "secret-123"
        config.setting_repo_ssh_key_id = mock_secret

        mock_secret_obj = MagicMock()
        mock_secret_obj.get_content.return_value = {"value": "private-key-content"}
        mock_charm.model.get_secret.return_value = mock_secret_obj

        manager = SettingRepoManager(mock_charm.model, config)

        assert manager.ssh_private_key == "private-key-content"
        mock_charm.model.get_secret.assert_called_once_with(id="secret-123")

    @patch("config.subprocess.run")
    def test_rsync_success(self, mock_subprocess_run, mock_charm, tmp_path):
        """Test rsync success."""
        config = CharmConfig(setting_repo="git+ssh://github.com/user/repo.git")
        manager = SettingRepoManager(mock_charm.model, config)

        source = str(tmp_path / "source/")
        destination = str(tmp_path / "dest/")

        manager._rsync(source, destination)

        mock_subprocess_run.assert_called_once()
        args = mock_subprocess_run.call_args[0][0]
        assert "/usr/bin/rsync" in args
        assert "-av" in args
        assert "--delete" in args
        assert source in args
        assert destination in args

    @patch("config.subprocess.run")
    def test_rsync_failure(self, mock_subprocess_run, mock_charm, tmp_path):
        """Test rsync failure."""
        import subprocess

        config = CharmConfig(setting_repo="git+ssh://github.com/user/repo.git")
        manager = SettingRepoManager(mock_charm.model, config)

        mock_subprocess_run.side_effect = subprocess.CalledProcessError(
            1, ["rsync"], stderr="rsync failed"
        )

        with pytest.raises(RsyncError, match="Rsync failed"):
            manager._rsync("/source/", "/dest/")

    def test_ssh_private_key_empty_when_no_secret_content(self, mock_charm):
        """Test ssh_private_key returns empty when secret has no value."""
        config = CharmConfig(
            setting_repo="git+ssh://github.com/user/repo.git",
        )
        # Manually set the secret ID after construction
        mock_secret = MagicMock()
        mock_secret.id = "secret-123"
        config.setting_repo_ssh_key_id = mock_secret

        mock_secret_obj = MagicMock()
        mock_secret_obj.get_content.return_value = {}  # No "value" key
        mock_charm.model.get_secret.return_value = mock_secret_obj

        manager = SettingRepoManager(mock_charm.model, config)

        assert manager.ssh_private_key == ""

    @patch("config.subprocess.check_output")
    def test_add_known_hosts_scan_failure(self, mock_subprocess_check_output, mock_charm):
        """Test SSH keyscan failure."""
        import subprocess

        config = CharmConfig(setting_repo="git+ssh://github.com/user/repo.git")
        manager = SettingRepoManager(mock_charm.model, config)

        mock_subprocess_check_output.side_effect = subprocess.CalledProcessError(
            1, ["ssh-keyscan"], stderr="scan failed"
        )

        with pytest.raises(SshKeyScanError, match="Ssh keyscan failed"):
            manager._add_known_hosts()

    @patch("config.subprocess.check_output")
    def test_add_known_hosts_returns_host_key(self, mock_subprocess_check_output, mock_charm):
        """Test SSH keyscan returns host key."""
        config = CharmConfig(setting_repo="git+ssh://github.com/user/repo.git")
        manager = SettingRepoManager(mock_charm.model, config)

        mock_subprocess_check_output.return_value = b"github.com ssh-rsa AAAAB3...\n"

        # The method writes to a file - just test it runs without error
        # We mock the file operations to avoid actual I/O
        m = mock_open()
        with patch("pathlib.Path.open", m):
            manager._add_known_hosts()
            mock_subprocess_check_output.assert_called_once()

    @patch("config.subprocess.run")
    def test_git_clone_success(self, mock_subprocess_run, mock_charm, tmp_path):
        """Test git clone success."""
        config = CharmConfig(setting_repo="git+ssh://github.com/user/repo.git?ref=main")
        manager = SettingRepoManager(mock_charm.model, config)

        manager._git_clone()

        mock_subprocess_run.assert_called_once()
        args = mock_subprocess_run.call_args[0][0]
        assert "/usr/bin/git" in args
        assert "clone" in args
        assert "--depth" in args
        assert "1" in args
        assert "--branch" in args
        assert "main" in args

    @patch("config.subprocess.run")
    def test_git_clone_without_ref(self, mock_subprocess_run, mock_charm):
        """Test git clone without ref."""
        config = CharmConfig(setting_repo="git+ssh://github.com/user/repo.git")
        manager = SettingRepoManager(mock_charm.model, config)

        manager._git_clone()

        mock_subprocess_run.assert_called_once()
        args = mock_subprocess_run.call_args[0][0]
        assert "--branch" not in args

    @patch("config.subprocess.run")
    def test_git_clone_failure(self, mock_subprocess_run, mock_charm):
        """Test git clone failure."""
        import subprocess

        config = CharmConfig(setting_repo="git+ssh://github.com/user/repo.git")
        manager = SettingRepoManager(mock_charm.model, config)

        mock_subprocess_run.side_effect = subprocess.CalledProcessError(
            1, ["git"], stderr="clone failed"
        )

        with pytest.raises(GitCloneError, match="Git clone of setting repository failed"):
            manager._git_clone()

    @patch("config.subprocess.check_output")
    def test_get_cloned_repo_url(self, mock_subprocess_check_output, mock_charm):
        """Test getting cloned repo URL."""
        config = CharmConfig(setting_repo="git+ssh://github.com/user/repo.git")
        manager = SettingRepoManager(mock_charm.model, config)

        mock_subprocess_check_output.return_value = b"git+ssh://github.com/user/repo.git\n"

        url = manager._get_cloned_repo_url()

        assert url == "git+ssh://github.com/user/repo.git"

    @patch("config.subprocess.check_output")
    def test_get_cloned_repo_url_failure(self, mock_subprocess_check_output, mock_charm):
        """Test getting cloned repo URL when not cloned."""
        import subprocess

        config = CharmConfig(setting_repo="git+ssh://github.com/user/repo.git")
        manager = SettingRepoManager(mock_charm.model, config)

        mock_subprocess_check_output.side_effect = subprocess.CalledProcessError(
            1, ["git"], stderr="not a git repo"
        )

        url = manager._get_cloned_repo_url()

        assert url == ""

    @patch("config.subprocess.check_output")
    def test_get_cloned_repo_ref(self, mock_subprocess_check_output, mock_charm):
        """Test getting cloned repo ref."""
        config = CharmConfig(setting_repo="git+ssh://github.com/user/repo.git")
        manager = SettingRepoManager(mock_charm.model, config)

        mock_subprocess_check_output.return_value = b"v1.0.0\n"

        ref = manager._get_cloned_repo_ref()

        assert ref == "v1.0.0"

    @patch("config.subprocess.check_output")
    def test_get_cloned_repo_ref_failure(self, mock_subprocess_check_output, mock_charm):
        """Test getting cloned repo ref when no tag."""
        import subprocess

        config = CharmConfig(setting_repo="git+ssh://github.com/user/repo.git")
        manager = SettingRepoManager(mock_charm.model, config)

        mock_subprocess_check_output.side_effect = subprocess.CalledProcessError(
            1, ["git"], stderr="not a tag"
        )

        ref = manager._get_cloned_repo_ref()

        assert ref == ""

    @patch.object(SettingRepoManager, "_get_cloned_repo_url")
    @patch.object(SettingRepoManager, "_get_cloned_repo_ref")
    def test_sync_already_synced(self, mock_get_ref, mock_get_url, mock_charm, falco_base_dir):
        """Test sync when repo is already synced."""
        from service import FalcoLayout

        config = CharmConfig(setting_repo="git+ssh://github.com/user/repo.git?ref=main")
        manager = SettingRepoManager(mock_charm.model, config)

        mock_get_url.return_value = "git+ssh://github.com/user/repo.git"
        mock_get_ref.return_value = "main"

        layout = FalcoLayout(falco_base_dir)
        result = manager.sync(layout)

        assert result is True

    @patch.object(SettingRepoManager, "_get_cloned_repo_url")
    @patch.object(SettingRepoManager, "_get_cloned_repo_ref")
    def test_sync_no_host_in_url(self, mock_get_ref, mock_get_url, mock_charm, falco_base_dir):
        """Test sync when URL has no host."""
        from service import FalcoLayout

        # Create a manager with a valid URL
        config = CharmConfig(setting_repo="git+ssh://github.com/user/repo.git")
        manager = SettingRepoManager(mock_charm.model, config)

        # Mock to return different URL/ref so it's not already synced
        mock_get_url.return_value = "different-url"
        mock_get_ref.return_value = "different-ref"

        # Mock the host property to return None/empty
        with patch.object(type(manager), "host", new_callable=lambda: property(lambda self: None)):
            layout = FalcoLayout(falco_base_dir)
            result = manager.sync(layout)

            assert result is False

    @patch.object(SettingRepoManager, "_get_cloned_repo_url")
    @patch.object(SettingRepoManager, "_get_cloned_repo_ref")
    @patch.object(SettingRepoManager, "_add_ssh_key")
    @patch.object(SettingRepoManager, "_add_known_hosts")
    @patch.object(SettingRepoManager, "_git_clone")
    @patch.object(SettingRepoManager, "_rsync")
    @patch("config.shutil.rmtree")
    def test_sync_full_flow_with_rules_and_configs(
        self,
        mock_rmtree,
        mock_rsync,
        mock_git_clone,
        mock_add_known_hosts,
        mock_add_ssh_key,
        mock_get_ref,
        mock_get_url,
        mock_charm,
        falco_base_dir,
        tmp_path,
    ):
        """Test full sync flow with rules and config directories."""
        from service import FalcoLayout

        config = CharmConfig(setting_repo="git+ssh://github.com/user/repo.git?sub_path=configs")
        manager = SettingRepoManager(mock_charm.model, config)

        # Mock the working directory to exist
        manager.working_dir = tmp_path / "falco_setting_repo"
        manager.working_dir.mkdir()

        # Create subdirectories
        sub_path_dir = manager.working_dir / "configs"
        sub_path_dir.mkdir()
        rules_dir = sub_path_dir / "rules.d"
        rules_dir.mkdir()
        configs_dir = sub_path_dir / "config.override.d"
        configs_dir.mkdir()

        mock_get_url.return_value = "different-url"
        mock_get_ref.return_value = "different-ref"

        layout = FalcoLayout(falco_base_dir)
        result = manager.sync(layout)

        assert result is True
        assert mock_add_ssh_key.called
        assert mock_add_known_hosts.called
        assert mock_rmtree.called
        assert mock_git_clone.called
        assert mock_rsync.call_count == 2  # Called for both rules and configs

    @patch.object(SettingRepoManager, "_get_cloned_repo_url")
    @patch.object(SettingRepoManager, "_get_cloned_repo_ref")
    @patch.object(SettingRepoManager, "_add_ssh_key")
    @patch.object(SettingRepoManager, "_add_known_hosts")
    @patch.object(SettingRepoManager, "_git_clone")
    @patch.object(SettingRepoManager, "_rsync")
    @patch("config.shutil.rmtree")
    def test_sync_with_only_configs_dir(
        self,
        mock_rmtree,
        mock_rsync,
        mock_git_clone,
        mock_add_known_hosts,
        mock_add_ssh_key,
        mock_get_ref,
        mock_get_url,
        mock_charm,
        falco_base_dir,
        tmp_path,
    ):
        """Test sync with only configs directory present (no rules)."""
        from config import RSYNC_CUSTOM_CONFIGS_KEY
        from service import FalcoLayout

        config = CharmConfig(setting_repo="git+ssh://github.com/user/repo.git")
        manager = SettingRepoManager(mock_charm.model, config)

        manager.working_dir = tmp_path / "falco_setting_repo"

        # After git clone, create the directory and subdirs
        def create_dirs():
            manager.working_dir.mkdir()
            # Only create configs dir, not rules dir
            configs_dir = manager.working_dir / RSYNC_CUSTOM_CONFIGS_KEY
            configs_dir.mkdir()

        mock_git_clone.side_effect = create_dirs
        mock_get_url.return_value = "different-url"
        mock_get_ref.return_value = "different-ref"

        layout = FalcoLayout(falco_base_dir)
        result = manager.sync(layout)

        assert result is True
        assert mock_rsync.call_count == 1  # Only called for configs

    @patch.object(SettingRepoManager, "_get_cloned_repo_url")
    @patch.object(SettingRepoManager, "_get_cloned_repo_ref")
    @patch.object(SettingRepoManager, "_add_ssh_key")
    @patch.object(SettingRepoManager, "_add_known_hosts")
    @patch.object(SettingRepoManager, "_git_clone")
    @patch.object(SettingRepoManager, "_rsync")
    def test_sync_working_dir_not_exists(
        self,
        mock_rsync,
        mock_git_clone,
        mock_add_known_hosts,
        mock_add_ssh_key,
        mock_get_ref,
        mock_get_url,
        mock_charm,
        falco_base_dir,
        tmp_path,
    ):
        """Test sync when working directory doesn't exist yet."""
        from config import RSYNC_CUSTOM_RULES_KEY
        from service import FalcoLayout

        config = CharmConfig(setting_repo="git+ssh://github.com/user/repo.git")
        manager = SettingRepoManager(mock_charm.model, config)

        # Set working_dir to a path that doesn't exist
        manager.working_dir = tmp_path / "nonexistent_falco_repo"

        # After git clone, create the directory and subdirs
        def create_dirs():
            manager.working_dir.mkdir()
            rules_dir = manager.working_dir / RSYNC_CUSTOM_RULES_KEY
            rules_dir.mkdir()

        mock_git_clone.side_effect = create_dirs
        mock_get_url.return_value = "different-url"
        mock_get_ref.return_value = "different-ref"

        layout = FalcoLayout(falco_base_dir)
        result = manager.sync(layout)

        assert result is True
        # rmtree should not be called since working_dir didn't exist
        assert mock_rsync.call_count == 1  # Called for rules

    @patch("config.Ssh_DIR")
    @patch("config.SSH_KEY_FILE")
    def test_add_ssh_key_success(self, mock_ssh_key_file, mock_ssh_dir, mock_charm, tmp_path):
        """Test successfully adding SSH key."""
        # Create a real file for testing
        mock_ssh_key_file.open = mock_open()
        mock_ssh_key_file.chmod = MagicMock()

        config = CharmConfig(setting_repo="git+ssh://github.com/user/repo.git")
        mock_secret = MagicMock()
        mock_secret.id = "secret-123"
        config.setting_repo_ssh_key_id = mock_secret

        mock_secret_obj = MagicMock()
        mock_secret_obj.get_content.return_value = {"value": "private-key-content"}
        mock_charm.model.get_secret.return_value = mock_secret_obj

        manager = SettingRepoManager(mock_charm.model, config)
        manager._add_ssh_key()

        mock_ssh_dir.mkdir.assert_called_once_with(mode=0o700, exist_ok=True)
        mock_ssh_key_file.open.assert_called_once()
        mock_ssh_key_file.chmod.assert_called_once_with(0o600)

    @patch("config.Ssh_DIR")
    @patch("config.SSH_KEY_FILE")
    def test_add_ssh_key_os_error(self, mock_ssh_key_file, mock_ssh_dir, mock_charm):
        """Test SSH key write OSError."""
        mock_ssh_key_file.open = MagicMock(side_effect=OSError("Cannot write"))

        config = CharmConfig(setting_repo="git+ssh://github.com/user/repo.git")
        mock_secret = MagicMock()
        mock_secret.id = "secret-123"
        config.setting_repo_ssh_key_id = mock_secret

        mock_secret_obj = MagicMock()
        mock_secret_obj.get_content.return_value = {"value": "private-key-content"}
        mock_charm.model.get_secret.return_value = mock_secret_obj

        manager = SettingRepoManager(mock_charm.model, config)

        with pytest.raises(SshKeyWriteError, match="Error writing Ssh key"):
            manager._add_ssh_key()

    @patch("config.subprocess.check_output")
    @patch("config.KNOWN_HOSTS_FILE")
    def test_add_known_hosts_write_success(
        self, mock_known_hosts_file, mock_subprocess_check_output, mock_charm
    ):
        """Test successfully writing known hosts."""
        mock_known_hosts_file.open = mock_open()

        config = CharmConfig(setting_repo="git+ssh://github.com/user/repo.git")
        manager = SettingRepoManager(mock_charm.model, config)

        mock_subprocess_check_output.return_value = b"github.com ssh-rsa AAAAB3...\n"

        manager._add_known_hosts()

        mock_subprocess_check_output.assert_called_once()
        mock_known_hosts_file.open.assert_called_once()

    @patch("config.subprocess.check_output")
    @patch("config.KNOWN_HOSTS_FILE")
    def test_add_known_hosts_os_error_on_write(
        self, mock_known_hosts_file, mock_subprocess_check_output, mock_charm
    ):
        """Test known hosts OSError on file write."""
        config = CharmConfig(setting_repo="git+ssh://github.com/user/repo.git")
        manager = SettingRepoManager(mock_charm.model, config)

        mock_subprocess_check_output.return_value = b"github.com ssh-rsa AAAAB3...\n"
        mock_known_hosts_file.open = MagicMock(side_effect=OSError("Cannot write"))

        with pytest.raises(SshKeyScanError, match="Error writing to known_hosts"):
            manager._add_known_hosts()
