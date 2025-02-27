from langchain_aws import ChatBedrock, BedrockEmbeddings
from langchain_elasticsearch import ElasticsearchStore, DenseVectorScriptScoreStrategy
from langchain_core.prompts import ChatPromptTemplate,  MessagesPlaceholder
from langgraph.graph import Graph
from langdetect import detect
from typing import List, Dict, Any
import boto3
from dotenv import load_dotenv
import os

load_dotenv()

#Instantiate Bedrock From AWS Client

# AWS Bedrock Client
boto3_bedrock = boto3.client('bedrock-runtime', 
                             region_name=os.environ.get("AWS_DEFAULT_REGION"),
                            aws_access_key_id=os.environ.get("BEDROCK_AWS_ACCESS_KEY_ID"),
                            aws_secret_access_key=os.environ.get("BEDROCK_AWS_SECRET_ACCESS_KEY"))

# Define Bedrock ChatBedrock
bedrock_chat = ChatBedrock(
    client=boto3_bedrock,
    model_id=os.environ.get("BEDROCK_CHAT_MODEL_ID")
)

#Define Bedrock Embeddings
bedrock_embeddings = BedrockEmbeddings(
    client=boto3_bedrock,
    model_id=os.environ.get("BEDROCK_EMBEDDING_MODEL_ID")
)

#Instantiate ElasticsearchStore From Langchain
finance_kb = ElasticsearchStore(
    es_url=os.environ.get("ELASTIC_URL"),
    es_api_key=os.environ.get("ELASTIC_API_KEY"),
    embedding=bedrock_embeddings,
    index_name=os.environ.get("FINANCE_KB_INDEX"),
    strategy=DenseVectorScriptScoreStrategy()
)

healthcare_kb = ElasticsearchStore(
    es_url=os.environ.get("ELASTIC_URL"),
    es_api_key=os.environ.get("ELASTIC_API_KEY"),
    embedding=bedrock_embeddings,
    index_name=os.environ.get("HEALTHCARE_KB_INDEX"),
    strategy=DenseVectorScriptScoreStrategy()
)

food_kb = ElasticsearchStore(
    es_url=os.environ.get("ELASTIC_URL"),
    es_api_key=os.environ.get("ELASTIC_API_KEY"),
    embedding=bedrock_embeddings,
    index_name=os.environ.get("FOOD_KB_INDEX"),
    strategy=DenseVectorScriptScoreStrategy()
)

#Multi-Agent RAG Workflow

#Intent Detection
intent_prompt = ChatPromptTemplate.from_messages([
    ("system", """
    You are an intent detection system for a chatbot that helps elderly users access support services. Your task is to classify user queries into one of the following intents:

    1. **financial_aid**: Questions about financial assistance programs, vouchers, or payouts.
       - Example (English): "How do I apply for ComCare?"
       - Example (Simplified Chinese): "如何申请社区关怀计划？"
       - Example (Malay): "Bagaimana cara memohon ComCare?"
       - Example (Tamil): "கோம்கேர் விண்ணப்பிக்க எப்படி?"

    2. **healthcare**: Questions about healthcare services, dementia care, or teleconsultation.
       - Example (English): "Where can I find a doctor for dementia care?"
       - Example (Simplified Chinese): "哪里可以找到治疗痴呆症的医生？"
       - Example (Malay): "Di mana saya boleh mencari doktor untuk penjagaan demensia?"
       - Example (Tamil): "மனதளவு பராமரிப்புக்கான மருத்துவரை எங்கே கண்டுபிடிப்பது?"

    3. **food_security**: Questions about food banks, budget meals, or grocery assistance.
       - Example (English): "Where is the nearest food bank?"
       - Example (Simplified Chinese): "最近的食品银行在哪里？"
       - Example (Malay): "Di manakah bank makanan yang terdekat?"
       - Example (Tamil): "அருகிலுள்ள உணவு வங்கி எங்கே?"

    4. **other**: Any query that does not fit into the above categories.
       - Example (English): "What is the weather today?"
       - Example (Simplified Chinese): "今天天气怎么样？"
       - Example (Malay): "Bagaimana cuaca hari ini?"
       - Example (Tamil): "இன்றைய வானிலை என்ன?"

    For each query, respond with ONLY the intent name (e.g., "financial_aid"). If you are unsure, respond with "other".
    """),
    ("human", "Query: {query}\nIntent:")
])

def detect_question_intent(query):
    intent_messages = intent_prompt.format_messages(query=query)
    intent_response = bedrock_chat.invoke(intent_messages)
    intent = intent_response.content.strip()
    return intent

def identify_language(query):
    return detect(query)

#Translation Agent
def translate_query(query, source_language_code, target_language_code):
    boto3_translate = boto3.client(service_name="translate",
                               region_name=os.environ.get("AWS_DEFAULT_REGION"),
                            aws_access_key_id=os.environ.get("TRANSLATE_AWS_ACCESS_KEY_ID"),
                            aws_secret_access_key=os.environ.get("TRANSLATE_AWS_SECRET_ACCESS_KEY"))
    translated_query_response = boto3_translate.translate_text(Text=query, SourceLanguageCode=source_language_code, TargetLanguageCode=target_language_code)
    return translated_query_response['TranslatedText']

#Document Retrieval Agent
def document_retrieval(intent, query):
    if (intent == "financial_aid"):
        similar_response = finance_kb.similarity_search(query=query,k=3)
    elif (intent == "healthcare"):
        similar_response = healthcare_kb.similarity_search(query=query,k=3)
    elif (intent == "food_security"):
        similar_response = food_kb.similarity_search(query=query,k=3)
    else:
        documents = []
        
    if (intent not in ["financial_aid","healthcare","food_security"]):
        documents = []

    documents = [document.page_content for document in similar_response]
    
    return documents

#Search Agent

#Define the state
class ChatState:
    def __init__(self):
        self.query: str = ""
        self.chat_history: List[Dict[str, str]] = []

#Define the nodes

#Node 1: Add user query to chat history
def add_user_query_node(state: ChatState) -> ChatState:
    state.chat_history.append({"role": "user", "content": state.query})
    return state

#Node 2: Generate response
chat_prompt = ChatPromptTemplate.from_messages([
    ("system", """
    You are a helpful assistant for elderly users. Your task is to answer their questions in the same language as the query. Follow these steps:

    1. **Understand the Context**: Review the chat history to understand the conversation so far.
    2. **Answer the Question**: Provide a clear and concise answer to the question based on the context.
    3. **Provide Additional Help**: If applicable, suggest next steps or additional resources.
    """),
    MessagesPlaceholder(variable_name="chat_history"),  # Include chat history
    ("human", "{query}")  # Current user query
])

def generate_response_node(state: ChatState) -> ChatState:
    # Format the chat history into a list of messages
    messages = chat_prompt.format_messages(
        query=state.query,
        chat_history=state.chat_history
    )
    
    # Invoke Claude 3.5 Haiku
    response = bedrock_chat(messages)
    
    # Add the bot's response to the chat history
    state.chat_history.append({"role": "bot", "content": response.content})
    
    # Update the state with the response
    state.response = response.content
    return state

#Define graph
# Create the graph
workflow = Graph()

# Add nodes to the graph
workflow.add_node("add_user_query", add_user_query_node)
workflow.add_node("generate_response", generate_response_node)

# Define edges (order of execution)
workflow.add_edge("add_user_query", "generate_response")

# Set entry and exit points
workflow.set_entry_point("add_user_query")
workflow.set_exit_point("generate_response")

# Compile the graph
app = workflow.compile()