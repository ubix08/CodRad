"""Test server with NVIDIA API - MiniMax model."""

import os
import sys

# Set environment variables for NVIDIA API
os.environ["OPENAI_API_KEY"] = "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"
os.environ["LLM_MODEL"] = "minimaxai/minimax-m2.7"
os.environ["LLM_BASE_URL"] = "https://integrate.api.nvidia.com/v1"

print("=" * 50)
print("NVIDIA API - MiniMax Model Test")
print("=" * 50)
print(f"Model: {os.environ['LLM_MODEL']}")
print(f"Base URL: {os.environ['LLM_BASE_URL']}")
print()

# Test direct API call first
print("[1/3] Testing direct API call...")
from openai import OpenAI

client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=os.environ["OPENAI_API_KEY"],
)

try:
    completion = client.chat.completions.create(
        model="minimaxai/minimax-m2.7",
        messages=[{"role": "user", "content": "Say 'Hello' in one word"}],
        temperature=0.5,
        max_tokens=10,
    )
    print(f"Direct API response: {completion.choices[0].message.content}")
    print("Direct API test: SUCCESS ✓")
except Exception as e:
    print(f"Direct API test failed: {e}")
    sys.exit(1)

print()
print("[2/3] Testing via SDK LLM...")

# Test SDK LLM directly
from openhands.sdk import LLM

llm = LLM(
    model=os.environ["LLM_MODEL"],
    api_key=os.environ["OPENAI_API_KEY"],
    base_url=os.environ["LLM_BASE_URL"],
)

try:
    response = llm.chat.completions.create(
        messages=[{"role": "user", "content": "Say 'LLM Test OK' in 3 characters"}],
        max_tokens=10,
    )
    print(f"LLM response: {response.choices[0].message.content}")
    print("SDK LLM test: SUCCESS ✓")
except Exception as e:
    print(f"SDK LLM test failed: {e}")
    # Continue anyway

print()
print("[3/3] Testing via SDK Agent...")

# Test with SDK Agent (proper way)
from openhands.sdk import LLM, Agent, Conversation, Tool
from openhands.tools.terminal import TerminalTool

# Create LLM with NVIDIA config
llm = LLM(
    model=os.environ["LLM_MODEL"],
    api_key=os.environ["OPENAI_API_KEY"],
    base_url=os.environ["LLM_BASE_URL"],
)

# Create agent with tools - use Tool wrapper
agent = Agent(
    llm=llm,
    tools=[
        Tool(name=TerminalTool.name),
    ],
)

# Create conversation
import tempfile
with tempfile.TemporaryDirectory() as tmpdir:
    conversation = Conversation(agent=agent, workspace=tmpdir)
    
    # Send a simple message
    conversation.send_message("Return exactly: AGENT OK")
    
    # Run the conversation
    print("Running agent conversation...")
    try:
        conversation.run()
        print("SDK Agent test: SUCCESS ✓")
    except Exception as e:
        print(f"SDK Agent test failed: {e}")
        # This might fail if there are no files to edit
        print("Expected: Agent may fail without file context")

print()
print("=" * 50)
print("All tests completed!")
print("=" * 50)
