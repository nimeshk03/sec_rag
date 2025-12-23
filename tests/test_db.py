import os
import pytest
from unittest.mock import patch, MagicMock
from src.data.supabase import SupabaseClient, get_supabase

@patch("src.data.supabase.create_client")
def test_supabase_client_initialization(mock_create_client):
    """Test Supabase client can be initialized with valid env vars."""
    with patch.dict(os.environ, {
        "SUPABASE_URL": "https://example.supabase.co",
        "SUPABASE_KEY": "test-key"
    }):
        # Reset singleton
        SupabaseClient._instance = None
        
        # Setup mock
        mock_instance = MagicMock()
        mock_create_client.return_value = mock_instance
        
        client = get_supabase()
        
        assert client is mock_instance
        mock_create_client.assert_called_once_with("https://example.supabase.co", "test-key")

def test_supabase_client_missing_env():
    """Test Supabase client raises error when env vars missing."""
    with patch.dict(os.environ, {}, clear=True):
        # Reset singleton
        SupabaseClient._instance = None
        
        with pytest.raises(ValueError, match="SUPABASE_URL and SUPABASE_KEY must be set"):
            get_supabase()

def test_supabase_client_default_values():
    """Test Supabase client raises error with default placeholder values."""
    with patch.dict(os.environ, {
        "SUPABASE_URL": "https://your-project.supabase.co",
        "SUPABASE_KEY": "your-anon-key-here"
    }):
        # Reset singleton
        SupabaseClient._instance = None
        
        with pytest.raises(ValueError, match="SUPABASE_URL and SUPABASE_KEY must be set"):
            get_supabase()

@patch("src.data.supabase.create_client")
def test_supabase_singleton(mock_create_client):
    """Test that get_supabase returns the same instance."""
    with patch.dict(os.environ, {
        "SUPABASE_URL": "https://example.supabase.co",
        "SUPABASE_KEY": "test-key"
    }):
        # Reset singleton
        SupabaseClient._instance = None
        
        # Setup mock
        mock_instance = MagicMock()
        mock_create_client.return_value = mock_instance
        
        client1 = get_supabase()
        client2 = get_supabase()
        
        assert client1 is client2
        # create_client should only be called once
        mock_create_client.assert_called_once()
