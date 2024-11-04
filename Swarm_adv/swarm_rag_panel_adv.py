from swarm import Swarm, Agent, Result
import os
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, StorageContext, load_index_from_storage
from llama_index.embeddings.fireworks import FireworksEmbedding
from llama_index.core import Settings
from llama_index.llms.openai import OpenAI

import panel as pn

os.environ["OPENAI_API_KEY"] = "sk-your-openai-api-key"
os.environ["FIREWORKS_API_KEY"] = "fw-your-fireworks-api-key"

Settings.embed_model = FireworksEmbedding()
Settings.llm = OpenAI("gpt-4o")

PERSIST_DIR = "storage"

def load_or_create_rag_index(pdf_filepath="data"):
    if not os.path.exists(PERSIST_DIR):
        os.makedirs(PERSIST_DIR)
        documents = SimpleDirectoryReader(pdf_filepath).load_data()
        index = VectorStoreIndex.from_documents(documents)
        print("Index created and persisted.")
        index.storage_context.persist(persist_dir=PERSIST_DIR)
    else:
        storage_context = StorageContext.from_defaults(persist_dir=PERSIST_DIR)
        # load index
        index = load_index_from_storage(storage_context)
        print("Index loaded from persistence.")
    return index

rag_index = load_or_create_rag_index()

def query_rag(query_str):
    query_engine = rag_index.as_query_engine()
    response = query_engine.query(query_str)
    return str(response)

context_variables = {'last_response': ""}

def triage_agent_instructions(context_variables):
    return """You are a triage agent.
    If the user asks a question related to the document, hand off to the RAG agent.
    """
def rag_agent_instructions(context_variables):
    return """You are a RAG agent. Answer user questions by using the `query_rag` function to retrieve information.
    If the user asks to tweet the content, hand off to the tweet agent.
    """
def tweet_agent_instructions(context_variables):
    return f"""You are a tweet agent.
    You are responsible for introducing the content in a tweet post with the tone of Deadpool.
    Content: {context_variables['last_response']}"""

def handoff_to_rag_agent():
    return Result(agent=rag_agent)

def handoff_to_tweet_agent(context_variables):
    return Result(agent=tweet_agent, context_variables=context_variables)

triage_agent = Agent(
    name="Triage Agent",
    instructions=triage_agent_instructions,
    functions=[handoff_to_rag_agent]
    )
rag_agent = Agent(
    name="RAG Agent",
    instructions=rag_agent_instructions,
    functions=[query_rag, handoff_to_tweet_agent]
    )
tweet_agent = Agent(
    name="Tweet Agent",
    instructions=tweet_agent_instructions,
    functions=[]
    )

client = Swarm()

pn.extension(design="material")

file_input = pn.widgets.FileInput(accept='.pdf')
chat_input = pn.chat.ChatAreaInput(placeholder="Input your question here...")
chat_interface = pn.chat.ChatInterface(widgets=[file_input, chat_input])

chat_interface.send("Welcome to the RAG Swarm App!", user="System", respond=False)  
chat_interface.active = False

current_agent = triage_agent
messages = []

def process_user_message(contents, user: str, instance: pn.chat.ChatInterface):
    global context_variables
    global current_agent
    global messages
    
    print("Welcome to the RAG Swarm App!")
    
    while True:
        if chat_interface.active == False:
            chat_interface.active = True
            contents.seek(0)
            with open("data/uploaded_file.pdf", "wb") as f:
                f.write(contents.read())

            chat_interface.send(f"Document loaded. You can now ask questions!", user="System", respond=False)

            return
        
        messages.append({"role": "user", "content": contents})
        response = client.run(
            agent=current_agent,
            messages=messages,
            )
        
        chat_interface.send(response.messages[-1]['content'], user=response.agent.name, avatar="🤖", respond=False)

        messages = response.messages
        current_agent = response.agent
        context_variables = response.context_variables
        context_variables['last_response'] = response.messages[-1]['content']

chat_interface.callback = process_user_message
chat_interface.servable()