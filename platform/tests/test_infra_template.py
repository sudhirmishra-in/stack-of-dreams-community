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


def _block(name: str) -> str:
    start = TEMPLATE.index(f"\n  {name}:")
    nxt = [TEMPLATE.find("\n  " + c + ":", start + 1) for c in ("SignupLogGroup", "SignupInvokePermission", "SchedulerRole")]
    return TEMPLATE[start : min(i for i in nxt if i > 0)]


def test_signup_trigger_function_is_minimal_and_fits_the_cognito_time_limit():
    full = _block("SignupFunction")
    block = "\n".join(line for line in full.splitlines() if not line.strip().startswith("#"))  # code, not comments
    assert "navigator.signup.handler.handler" in block
    assert "Timeout: 4" in block  # Cognito allows triggers 5 seconds
    assert "ReservedConcurrentExecutions" in block
    assert "Action: [dynamodb:GetItem]" in block  # read one item; no writes, no other services
    assert "GetAtt UsageTable.Arn" in block and "DataTable" not in block
    assert "bedrock" not in block.lower() and "cognito-idp:" not in block


def test_only_this_user_pool_may_invoke_the_signup_trigger():
    block = _block("SignupInvokePermission")
    assert "Principal: cognito-idp.amazonaws.com" in block
    assert "userpool/${CognitoUserPoolId}" in block


def test_stack_never_modifies_the_user_pool():
    # Attaching the trigger re-sends every pool setting, so it stays a manual, reviewed step outside this stack.
    assert "AWS::Cognito::UserPool" not in TEMPLATE


def test_signup_function_is_built_like_the_other_lambdas():
    assert "build-SignupFunction" in (Path(__file__).resolve().parents[1] / "infra" / "Makefile").read_text()
