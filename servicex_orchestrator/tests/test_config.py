from servicex_orchestrator.config import DEFAULT_TASK_QUEUE, Settings


def test_defaults():
    settings = Settings.from_env({})
    assert settings.temporal_address == "localhost:7233"
    assert settings.temporal_namespace == "default"
    assert settings.task_queue == DEFAULT_TASK_QUEUE
    assert settings.log_level == "INFO"


def test_from_env():
    settings = Settings.from_env(
        {
            "TEMPORAL_ADDRESS": "servicex-temporal-frontend:7233",
            "TEMPORAL_NAMESPACE": "servicex",
            "TEMPORAL_TASK_QUEUE": "other-queue",
            "LOG_LEVEL": "debug",
        }
    )
    assert settings == Settings(
        temporal_address="servicex-temporal-frontend:7233",
        temporal_namespace="servicex",
        task_queue="other-queue",
        log_level="DEBUG",
    )
