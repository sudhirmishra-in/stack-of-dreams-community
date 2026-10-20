"""Guards against template regressions that unit tests with fakes cannot catch."""

from pathlib import Path

TEMPLATE = (Path(__file__).resolve().parents[1] / "infra" / "template.yaml").read_text()


def test_api_role_can_invoke_the_runtime_for_a_user():
    # The gateway always passes runtimeUserId, which AgentCore authorizes with a separate action.
    assert "bedrock-agentcore:InvokeAgentRuntime," in TEMPLATE
    assert "bedrock-agentcore:InvokeAgentRuntimeForUser" in TEMPLATE


def test_api_role_can_only_reach_the_runtime_given_as_a_parameter():
    # No hard-coded AgentCore ARNs: the only invokable runtime is the AgentRuntimeArn parameter.
    assert "arn:aws:bedrock-agentcore" not in TEMPLATE
    assert TEMPLATE.count("bedrock-agentcore:InvokeAgentRuntime") == 2  # the two actions, on one statement


def test_invoker_error_keeps_the_aws_reason_for_logs():
    from navigator.gateway.invoker import AgentCoreInvoker, InvokerError

    class Denied(Exception):
        response = {"Error": {"Code": "AccessDeniedException", "Message": "not authorized to perform: bedrock-agentcore:InvokeAgentRuntimeForUser"}}

    class Client:
        def invoke_agent_runtime(self, **kw):
            raise Denied("x")

    try:
        AgentCoreInvoker("us-east-2", "arn", client=Client()).invoke({}, "s" * 64, "u", 5)
    except InvokerError as e:
        assert "InvokeAgentRuntimeForUser" in str(e)
    else:
        raise AssertionError("expected InvokerError")
