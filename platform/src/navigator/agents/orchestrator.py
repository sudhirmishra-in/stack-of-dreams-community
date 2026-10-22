"""Strands orchestrator with agent-as-tool specialists, all running inside ONE AgentCore runtime.

Design rules:
 * Deterministic tools do the lookups. The LLM interprets and explains.
 * Specialists exist as agent-tools but the orchestrator is told to use them only for multi-step analysis, and
   `maxSpecialistCalls` is a hard per-request cap.
 * A LimitsHook cancels any model/tool call once the invocation, token, tool or time limit is reached.
 * Every model call's tokens are metered, including specialists'.
"""

from __future__ import annotations

from typing import Any, Callable

from strands import Agent, tool
from strands.hooks import BeforeModelCallEvent, BeforeToolCallEvent, HookProvider, HookRegistry

from . import prompts
from .meter import LimitExceeded, UsageMeter
from .tools import ToolBox

ModelFactory = Callable[[int], Any]  # max_tokens -> strands Model
SPECIALIST_MAX_OUTPUT = 300
SPECIALIST_REPLY_CHARS = 1500


def _usage_of(agent_or_result: Any) -> tuple[int, int]:
    metrics = getattr(agent_or_result, "metrics", None) or getattr(agent_or_result, "event_loop_metrics", None)
    acc = getattr(metrics, "accumulated_usage", None) or {}
    return int(acc.get("inputTokens", 0)), int(acc.get("outputTokens", 0))


class LimitsHook(HookProvider):
    def __init__(self, meter: UsageMeter, owner: str, orchestrator_ref: list[Agent] | None = None):
        self.meter, self.owner, self.orch_ref = meter, owner, orchestrator_ref or []

    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        registry.add_callback(BeforeModelCallEvent, self._before_model)
        registry.add_callback(BeforeToolCallEvent, self._before_tool)

    def _before_model(self, event: BeforeModelCallEvent) -> None:
        own_in, own_out = _usage_of(event.agent)
        inflight = own_in + own_out
        if self.owner != "orchestrator" and self.orch_ref:
            o_in, o_out = _usage_of(self.orch_ref[0])  # the orchestrator is paused but its tokens count
            inflight += o_in + o_out
        self.meter.set_inflight(inflight)
        reason = self.meter.block_model_call(int(getattr(event, "projected_input_tokens", 0) or 0))
        if reason:
            event.cancel = f"Stopped: {reason} reached."

    def _before_tool(self, event: BeforeToolCallEvent) -> None:
        reason = self.meter.block_tool_call()
        if reason:
            event.cancel_tool = f"Stopped: {reason} reached."


def build_direct_tools(box: ToolBox) -> list[Any]:
    @tool
    def search_resources(zip_code: str, resource_type: str, radius_miles: float | None = None, include_demo: bool = False) -> str:
        """Search the resource directory (no AI). resource_type is one of baby_formula, groceries, diapers, food_assistance.
        include_demo=true also returns fictional demo records that carry sample inventory. Returns up to 8 results with sources."""
        return box.search_resources(zip_code, resource_type, radius_miles, include_demo)

    @tool
    def get_resource_details(resource_id: str) -> str:
        """Get the stored details, source and verification status of one resource by id."""
        return box.get_resource_details(resource_id)

    @tool
    def get_inventory(resource_id: str) -> str:
        """Get inventory for one resource. Real providers have no inventory data; demo providers have fictional sample data."""
        return box.get_inventory(resource_id)

    @tool
    def get_capacity_context(resource_id: str | None = None) -> str:
        """Get weekly capacity (demo records only) and citywide historical service activity with its exact meaning."""
        return box.get_capacity_context(resource_id)

    @tool
    def route_info(from_zip: str, resource_id: str, mode: str = "Car") -> str:
        """Get real distance and travel time from a ZIP code to a resource via Amazon Location. mode is Car or Pedestrian."""
        return box.route_info(from_zip, resource_id, mode)

    return [search_resources, get_resource_details, get_inventory, get_capacity_context, route_info]


def build_specialists(box: ToolBox, meter: UsageMeter, model_factory: ModelFactory, model_id: str, orch_ref: list[Agent], agent_cls: type = Agent) -> list[Any]:
    direct = {t.tool_name: t for t in build_direct_tools(box)}

    def run_specialist(label: str, system: str, tool_names: list[str], task: str) -> str:
        try:
            meter.take_specialist()
        except LimitExceeded:
            return "Specialist call limit reached for this request. Answer using the information already gathered."
        agent = agent_cls(
            name=label,  # shows up as gen_ai.agent.name so traces can tell the specialists apart
            model=model_factory(SPECIALIST_MAX_OUTPUT),
            system_prompt=system,
            tools=[direct[n] for n in tool_names],
            hooks=[LimitsHook(meter, label, orch_ref)],
            callback_handler=None,
        )
        try:
            result = agent(task[:600])
        except Exception:
            return "The specialist could not complete this task."
        meter.add_usage(model_id, *_usage_of(result))
        return str(result)[:SPECIALIST_REPLY_CHARS]

    @tool
    def resource_discovery_agent(task: str) -> str:
        """Specialist for multi-step discovery across several searches. Use only when direct search_resources is not enough."""
        return run_specialist("resource_discovery", prompts.RESOURCE_DISCOVERY, ["search_resources", "get_resource_details"], task)

    @tool
    def inventory_agent(task: str) -> str:
        """Specialist for comparing inventory across providers. Use only for multi-provider inventory analysis."""
        return run_specialist("inventory", prompts.INVENTORY, ["get_inventory", "search_resources"], task)

    @tool
    def capacity_agent(task: str) -> str:
        """Specialist for interpreting capacity versus historical service activity. Use for analysis, not simple lookups."""
        return run_specialist("capacity", prompts.CAPACITY, ["get_capacity_context"], task)

    @tool
    def location_agent(task: str) -> str:
        """Specialist for geographic filtering and travel questions that need several location lookups."""
        return run_specialist("location", prompts.LOCATION, ["search_resources", "route_info"], task)

    return [resource_discovery_agent, inventory_agent, capacity_agent, location_agent]


def build_orchestrator(box: ToolBox, meter: UsageMeter, model_factory: ModelFactory, model_id: str, agent_cls: type = Agent) -> Agent:
    orch_ref: list[Agent] = []
    tools = build_direct_tools(box) + build_specialists(box, meter, model_factory, model_id, orch_ref, agent_cls)
    agent = agent_cls(
        name="orchestrator",
        model=model_factory(meter.limits["mainMaxOutputTokens"]),
        system_prompt=prompts.ORCHESTRATOR,
        tools=tools,
        hooks=[LimitsHook(meter, "orchestrator", orch_ref)],
        callback_handler=None,
    )
    orch_ref.append(agent)
    return agent
