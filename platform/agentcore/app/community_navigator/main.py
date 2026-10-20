"""AgentCore Runtime entrypoint. `navigator/` is copied in by scripts/sync_runtime.sh before deploy."""

from navigator.agents.runtime import create_app

app = create_app()

if __name__ == "__main__":
    app.run()
