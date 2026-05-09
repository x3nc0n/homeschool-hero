from pathlib import Path

from backend.config import Settings
from backend.services.capabilities import CapabilityRegistry


def test_capability_detection_uses_mocked_service_checks(monkeypatch, tmp_path: Path) -> None:
    config = Settings(
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'app.db').resolve().as_posix()}",
        secret_key='required-test-secret',
        upload_dir=str(tmp_path / 'uploads'),
        ai_provider='ollama',
        ollama_host='http://ollama.test:11434',
        ollama_model='llama3.2',
        smtp_host='smtp.test',
        smtp_port=2525,
        smtp_from_email='robot@test.local',
        backup_target=str(tmp_path / 'backup'),
        testing=True,
    )
    registry = CapabilityRegistry(config)

    monkeypatch.setattr(
        'backend.services.capabilities.check_ai_grading',
        lambda *_args, **_kwargs: {
            'name': 'ai_grading',
            'enabled': True,
            'configured': True,
            'status': 'enabled',
            'reason': 'AI reachable',
            'details': {'provider': 'ollama'},
            'checked_at': '2026-05-08T00:00:00+00:00',
        },
    )
    monkeypatch.setattr(
        'backend.services.capabilities.check_email',
        lambda *_args, **_kwargs: {
            'name': 'email',
            'enabled': False,
            'configured': True,
            'status': 'disabled',
            'reason': 'SMTP test failed',
            'details': {'host': 'smtp.test'},
            'checked_at': '2026-05-08T00:00:00+00:00',
        },
    )
    monkeypatch.setattr(
        'backend.services.capabilities.check_backup',
        lambda *_args, **_kwargs: {
            'name': 'backup',
            'enabled': True,
            'configured': True,
            'status': 'enabled',
            'reason': 'Backup target mounted',
            'details': {'target': str(tmp_path / 'backup')},
            'checked_at': '2026-05-08T00:00:00+00:00',
        },
    )
    monkeypatch.setattr(
        'backend.services.capabilities.check_ocr',
        lambda *_args, **_kwargs: {
            'name': 'ocr',
            'enabled': False,
            'configured': False,
            'status': 'disabled',
            'reason': 'Tesseract missing',
            'details': {},
            'checked_at': '2026-05-08T00:00:00+00:00',
        },
    )

    result = registry.check_all_sync()

    assert result['ai_grading']['enabled'] is True
    assert result['email']['enabled'] is False
    assert result['backup']['enabled'] is True
    assert result['ocr']['reason'] == 'Tesseract missing'
