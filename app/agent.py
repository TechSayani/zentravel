# ruff: noqa
import os
import re
from pydantic import BaseModel
from google.adk.workflow import Workflow, START, node, JoinNode, FunctionNode
from google.adk.agents import LlmAgent
from google.adk.tools import AgentTool
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, StdioServerParameters
from google.adk.events.event import Event
from google.adk.events.request_input import RequestInput
from google.adk.agents.context import Context
from google.adk.models import Gemini
from google.genai import types

from app.config import config

# Define output schema for orchestrator
class OrchestratorOutput(BaseModel):
    response: str
    needs_approval: bool
    booking_details: str | None = None

# Initialize Model
model_instance = Gemini(model=config.model)

# Define MCP Toolset
mcp_toolset = MCPToolset(
    connection_params=StdioServerParameters(
        command="uv",
        args=["run", "app/mcp_server.py"]
    )
)

# Define sub-agents
itinerary_planner = LlmAgent(
    name="itinerary_planner",
    model=model_instance,
    instruction=(
        "You are ZenTravel's Itinerary Planner. You create beautiful, detailed, "
        "personalized travel itineraries based on destination, dates, preferences, and weather data. "
        "Keep your descriptions engaging, clear, and structured. Always incorporate weather details if provided."
    ),
    tools=[mcp_toolset],
)

booking_coordinator = LlmAgent(
    name="booking_coordinator",
    model=model_instance,
    instruction=(
        "You are ZenTravel's Booking Coordinator. You search for flight and hotel options "
        "using available MCP tools. You provide precise options with names, dates, and prices. "
        "Do not book anything; only search and format the results."
    ),
    tools=[mcp_toolset],
)

# Define orchestrator LlmAgent (runs inside the workflow)
orchestrator = LlmAgent(
    name="orchestrator",
    model=model_instance,
    instruction=(
        "You are the ZenTravel main orchestrator. You help users plan trips and find travel options.\n"
        "Your task is to coordinate the workflow:\n"
        "1. For creating/planning itineraries, use the itinerary_planner tool.\n"
        "2. For searching flights/hotels or checking prices, use the booking_coordinator tool.\n"
        "3. If the user wants to book a flight/hotel, or has selected a flight/hotel to book, set needs_approval=True "
        "and provide the booking details in booking_details. Otherwise, set needs_approval=False.\n"
        "Provide a helpful summary of the itinerary or flight/hotel choices in the response field."
    ),
    tools=[AgentTool(itinerary_planner), AgentTool(booking_coordinator)],
    output_schema=OrchestratorOutput,
)

# Security checkpoint node
def security_checkpoint(ctx: Context, node_input: types.Content) -> Event:
    import json
    import sys
    
    # Extract text from START input
    text = ""
    if node_input and node_input.parts:
        text = "".join(part.text for part in node_input.parts if part.text)
    
    # Structured JSON audit log
    audit_log = {
        "event": "input_evaluation",
        "severity": "INFO",
        "session_id": ctx.session.id,
        "input_length": len(text)
    }
    sys.stderr.write(json.dumps(audit_log) + "\n")
    
    # 1. Prompt Injection detection
    injection_keywords = ["system override", "ignore previous instructions", "bypass security"]
    for kw in injection_keywords:
        if kw in text.lower():
            warn_log = {
                "event": "prompt_injection_detected",
                "severity": "CRITICAL",
                "session_id": ctx.session.id,
                "keyword": kw
            }
            sys.stderr.write(json.dumps(warn_log) + "\n")
            return Event(output=f"Prompt injection pattern '{kw}' detected.", route="security_event")
            
    # 2. Domain-Specific Rule: Sanctioned Country Check
    sanctioned_countries = ["north korea", "syria", "sudan", "cuba", "iran"]
    for country in sanctioned_countries:
        if country in text.lower():
            block_log = {
                "event": "sanctioned_destination_blocked",
                "severity": "WARNING",
                "session_id": ctx.session.id,
                "country": country
            }
            sys.stderr.write(json.dumps(block_log) + "\n")
            return Event(output=f"Travel planning to sanctioned country '{country.title()}' is prohibited.", route="security_event")

    # 3. PII Scrubbing (passport, credit card numbers, email)
    passport_regex = r"\b[A-Z0-9]{9}\b"
    cc_regex = r"\b(?:\d[ -]*?){13,16}\b"
    email_regex = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
    
    scrubbed_text = text
    scrubbed_text = re.sub(cc_regex, "[REDACTED CREDIT CARD]", scrubbed_text)
    scrubbed_text = re.sub(passport_regex, "[REDACTED PASSPORT]", scrubbed_text)
    scrubbed_text = re.sub(email_regex, "[REDACTED EMAIL]", scrubbed_text)
    
    if scrubbed_text != text:
        pii_log = {
            "event": "pii_scrubbed",
            "severity": "WARNING",
            "session_id": ctx.session.id,
            "details": "Scrubbed credit card, passport, or email address"
        }
        sys.stderr.write(json.dumps(pii_log) + "\n")
        
    return Event(output=scrubbed_text, route="clean")

def security_failure(ctx: Context, node_input: str):
    msg = f"⚠️ Security Block: {node_input}"
    yield Event(content=types.Content(role='model', parts=[types.Part.from_text(text=msg)]))
    yield Event(output=msg)

def routing_node(ctx: Context, node_input: dict):
    # node_input is the dict parsed from OrchestratorOutput
    needs_approval = node_input.get("needs_approval", False)
    ctx.state["last_response"] = node_input.get("response")
    ctx.state["booking_details"] = node_input.get("booking_details")
    
    if needs_approval:
        return Event(output=node_input, route="needs_approval")
    return Event(output=node_input, route="done")

async def request_approval(ctx: Context, node_input: dict):
    if not ctx.resume_inputs or "approval" not in ctx.resume_inputs:
        details = ctx.state.get("booking_details") or "No details"
        yield RequestInput(
            interrupt_id="approval", 
            message=f"✋ ZenTravel Approval Gate: Please review your booking details:\n\n{details}\n\nDo you approve? (Yes/No)"
        )
        return
    
    user_response = ctx.resume_inputs["approval"].strip().lower()
    if user_response in ["yes", "y", "approve", "confirm"]:
        yield Event(output="Approved", route="approved")
    else:
        yield Event(output="Rejected", route="rejected")

def finalize_plan(ctx: Context, node_input: str):
    details = ctx.state.get("booking_details") or "No details"
    msg = f"🎉 Booking Confirmed!\n\nDetails:\n{details}\n\nThank you for choosing ZenTravel!"
    ctx.state["last_response"] = msg
    yield Event(content=types.Content(role='model', parts=[types.Part.from_text(text=msg)]))
    yield Event(output=msg)

def final_output(ctx: Context, node_input):
    response_text = ctx.state.get("last_response") or "Trip planning complete."
    yield Event(content=types.Content(role='model', parts=[types.Part.from_text(text=response_text)]))
    yield Event(output=response_text)

# Define workflow graph
workflow = Workflow(
    name="zentravel_workflow",
    edges=[
        ('START', security_checkpoint),
        (security_checkpoint, {"security_event": security_failure, "clean": orchestrator}),
        (orchestrator, routing_node),
        (routing_node, {"needs_approval": request_approval, "done": final_output}),
        (request_approval, {"approved": finalize_plan, "rejected": orchestrator}),
        (finalize_plan, final_output),
    ],
    description="ZenTravel workflow agent",
)

# App wrapping
from google.adk.apps import App, ResumabilityConfig
app = App(
    root_agent=workflow,
    name="app",
    resumability_config=ResumabilityConfig(enabled=True)
)
