import os
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition

load_dotenv()

## Configure Project Client
project_client = AIProjectClient(
    endpoint=os.environ["PROJECT_ENDPOINT"],
    credential=DefaultAzureCredential(),
)
openai_client = project_client.get_openai_client()


## Create a Foundry Agent
agent = project_client.agents.create_version(
    agent_name="hello-world-agent",
    definition=PromptAgentDefinition(
        model=os.environ["MODEL_DEPLOYMENT_NAME"],
    ),
)
print(f"Agent created (id: {agent.id}, name: {agent.name}, version: {agent.version})")


## Create a conversation for the agent interaction
conversation = openai_client.conversations.create()
print(f"Created conversation (id: {conversation.id})")

## Chat with the agent

while True:
    # Get the user input
    user_input = input("You: ")

    if user_input.lower() in ["exit", "quit"]:
        print("Exiting the chat.")
        break

    # Get the agent response
    response = openai_client.responses.create(
        conversation=conversation.id,
        input=user_input,
        extra_body={"agent": {"name": agent.name, "type": "agent_reference"}},
    )

    # Print the agent response
    print(f"Assistant: {response.output_text}")