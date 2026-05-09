import json
import os
import glob
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition, FileSearchTool, FunctionTool, MCPTool, Tool
from openai.types.responses.response_input_param import FunctionCallOutput, ResponseInputParam

load_dotenv()

vector_store_id = ""  # Set to your vector store ID if you already have one

## Configure Project Client
project_client = AIProjectClient(
    endpoint=os.environ["PROJECT_ENDPOINT"],
    credential=DefaultAzureCredential(),
)
openai_client = project_client.get_openai_client()


## -- FILE SEARCH -- ##

if vector_store_id:
    vector_store = openai_client.vector_stores.retrieve(vector_store_id)
    print(f"Using existing vector store (id: {vector_store.id})")
else:
    # Create vector store for file search
    vector_store = openai_client.vector_stores.create(name="ContosoPizzaStores")
    print(f"Vector store created (id: {vector_store.id})")

    # Upload file to vector store
    for file_path in glob.glob("documents/*.md"):
        file = openai_client.vector_stores.files.upload_and_poll(
            vector_store_id=vector_store.id, file=open(file_path, "rb")
        )
        print(f"File uploaded to vector store (id: {file.id})")
## -- FILE SEARCH -- ##


## -- Function Calling Tool -- ##
func_tool = FunctionTool(
    name="get_pizza_quantity",
    parameters={
        "type": "object",
        "properties": {
            "people": {
                "type": "integer",
                "description": "The number of people to order pizza for",
            },
        },
        "required": ["people"],
        "additionalProperties": False,
    },
    description="Get the quantity of pizza to order based on the number of people.",
    strict=True,
)

def get_pizza_quantity(people: int) -> str:
    """Calculate the number of pizzas to order based on the number of people.
        Assumes each pizza can feed 2 people.
    Args:
        people (int): The number of people to order pizza for.
    Returns:
        str: A message indicating the number of pizzas to order.
    """
    print(f"[FUNCTION CALL:get_pizza_quantity] Calculating pizza quantity for {people} people.")
    return f"For {people} you need to order {people // 2 + people % 2} pizzas."
## -- Function Calling Tool -- ##


## -- MCP -- ##
mcpTool = MCPTool(
    server_label="contoso-pizza-mcp",
    server_url="https://pizza-mcp-server.prouddune-f79ccb2b.westeurope.azurecontainerapps.io/mcp",
    require_approval="never"
)
## -- MCP -- ##


## Define the toolset for the agent
toolset: list[Tool] = []
toolset.append(FileSearchTool(vector_store_ids=[vector_store.id]))
toolset.append(func_tool)
toolset.append(mcpTool)


## Create a Foundry Agent
agent = project_client.agents.create_version(
    agent_name="hello-world-agent",
    definition=PromptAgentDefinition(
        model=os.environ["MODEL_DEPLOYMENT_NAME"],
        instructions=open("instructions.txt").read(),
        tools=toolset,
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

    # Handle function calls in the response
    input_list: ResponseInputParam = []
    for item in response.output:
        if item.type == "function_call":
            if item.name == "get_pizza_quantity":
                # Execute the function logic for get_pizza_quantity
                pizza_quantity = get_pizza_quantity(**json.loads(item.arguments))
                # Provide function call results to the model
                input_list.append(
                    FunctionCallOutput(
                        type="function_call_output",
                        call_id=item.call_id,
                        output=json.dumps({"pizza_quantity": pizza_quantity}),
                    )
                )

    if input_list:
        response = openai_client.responses.create(
            previous_response_id=response.id,
            input=input_list,
            extra_body={"agent": {"name": agent.name, "type": "agent_reference"}},
        )    

    # Print the agent response
    print(f"Assistant: {response.output_text}")