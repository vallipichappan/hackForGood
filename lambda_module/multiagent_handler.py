from langchain_aws import ChatBedrock, BedrockEmbeddings
from langchain_elasticsearch import ElasticsearchStore, DenseVectorScriptScoreStrategy
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, END
from langdetect import detect
from typing import List, Dict, Optional, TypedDict
import boto3
from dotenv import load_dotenv
import os

load_dotenv()

bedrock_client = boto3.client('bedrock-runtime', 
                             region_name=os.environ.get("AWS_DEFAULT_REGION"),
                            aws_access_key_id=os.environ.get("BEDROCK_AWS_ACCESS_KEY_ID"),
                            aws_secret_access_key=os.environ.get("BEDROCK_AWS_SECRET_ACCESS_KEY"))

bedrock_chat = ChatBedrock(
        client=bedrock_client,
        model_id=os.environ.get("BEDROCK_CHAT_MODEL_ID")
)

bedrock_embeddings = BedrockEmbeddings(
    client=bedrock_client,
    model_id=os.environ.get("BEDROCK_EMBEDDING_MODEL_ID")
)

#Instantiate ElasticsearchStore From Langchain
def elasticsearch_store(index_name: str, embeddings: BedrockEmbeddings):
    return ElasticsearchStore(
        es_url=os.environ.get("ELASTIC_URL"),
        es_api_key=os.environ.get("ELASTIC_API_KEY"),
        embedding=embeddings,
        index_name=index_name,
        strategy=DenseVectorScriptScoreStrategy()
    )


finance_kb = elasticsearch_store(index_name=os.environ.get("FINANCE_KB_INDEX"),
                                 embeddings=bedrock_embeddings)

food_kb = elasticsearch_store(index_name=os.environ.get("FOOD_KB_INDEX"),
                                 embeddings=bedrock_embeddings)

healthcare_kb = elasticsearch_store(index_name=os.environ.get("HEALTHCARE_KB_INDEX"),
                                 embeddings=bedrock_embeddings)

#Multi-Agent RAG Workflow

#Intent Detection
def detect_question_intent(query: str):
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
    intent_messages = intent_prompt.format_messages(query=query)
    intent_response = bedrock_chat.invoke(intent_messages)
    intent = intent_response.content.strip()
    return intent

def identify_language(query: str):
    return detect(query)

#Translation Agent
def translate_query(query: str, source_language_code: str, target_language_code: str):
    boto3_translate = boto3.client(service_name="translate",
                               region_name=os.environ.get("AWS_DEFAULT_REGION"),
                            aws_access_key_id=os.environ.get("TRANSLATE_AWS_ACCESS_KEY_ID"),
                            aws_secret_access_key=os.environ.get("TRANSLATE_AWS_SECRET_ACCESS_KEY"))
    translated_query_response = boto3_translate.translate_text(Text=query, SourceLanguageCode=source_language_code, TargetLanguageCode=target_language_code)
    return translated_query_response['TranslatedText']

#Document Retrieval Agent
def document_retrieval(intent: str, query: str):
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
class ChatState(TypedDict):
    query: str
    chat_history: List[Dict[str,str]]
    context: Optional[List[str]]
    response: Optional[str]

#Define the nodes

#Node 1: Add user query to chat history
def add_user_query_node(state: ChatState) -> ChatState:
    state["chat_history"].append({"role": "user", "content": state["query"]})
    return state

#Node 2: Generate response

def generate_response_node(state: ChatState) -> ChatState:
    PROMPT_TEMPLATE = """The following is a helpful conversation between a social worker AI and a human. 
    The AI provides detailed and accurate information based on available resources. If unsure, it transparently states it does not know.

    Always reply in the original user language.

    AI's Role:
    - You are a social worker specializing in Financial Support, Medical Support, and Food Bank Aid in Singapore.
    - Your mission is to assist users by providing guidance on government schemes, Care Corner Singapore programs, and relevant community support.
    - If the user's question is unrelated, politely redirect them to relevant topics.

    Guidelines:
    1. If you don’t have an answer, say: "I’m sorry, I don’t have that information. Would you like help with financial aid, healthcare support, or food assistance?"
    2. Ensure responses are **clear, actionable, and concise**.
    3. Avoid generic responses—refer to **specific** government and non-profit programs when possible.
    4. Keep the tone **empathetic and supportive**.

    ### Example Conversations:

    #### **English Example**  
    User: "Can I get financial assistance for my mother’s medical bills?"
    AI: "Yes! You can check the **MediFund scheme**, which helps low-income individuals with medical costs. You may also qualify for **ComCare Short-to-Medium-Term Assistance (SMTA)**. Would you like help checking your eligibility?"

    User: "What are some food aid programs available?"
    AI: "There are several food assistance programs! **Meals-on-Wheels** delivers free meals to homebound elderly, and **Willing Hearts** provides daily meals. Would you like details on eligibility or how to apply?"

    ---

    #### **Mandarin (华语) Example**  
    用户: *我可以申请医疗费用的经济援助吗？*  
    AI: *可以！您可以查看 **MediFund 计划**，它为低收入人士提供医疗费用援助。此外，您可能符合 **ComCare 短期到中期援助 (SMTA)** 的资格。您需要我帮您检查资格吗？*  

    用户: *新加坡有哪些食品援助计划？*  
    AI: *有几个食品援助计划！**Meals-on-Wheels** 为行动不便的老年人提供免费膳食，**Willing Hearts** 每天提供餐食。您想了解申请资格吗？*  

    ---

    #### **Malay (Bahasa Melayu) Example**  
    Pengguna: *Bagaimana saya boleh mendapatkan bantuan kewangan untuk bil perubatan ibu saya?*  
    AI: *Anda boleh memohon **skim MediFund**, yang membantu individu berpendapatan rendah menampung kos perubatan. Anda juga mungkin layak untuk **Bantuan Jangka Pendek hingga Sederhana ComCare (SMTA)**. Mahu saya bantu menyemak kelayakan anda?*  

    Pengguna: *Apakah program bantuan makanan yang tersedia?*  
    AI: *Terdapat beberapa program bantuan makanan! **Meals-on-Wheels** menghantar makanan percuma kepada warga emas yang uzur, dan **Willing Hearts** menyediakan makanan harian. Adakah anda ingin tahu tentang kelayakan atau cara memohon?*  

    ---

    #### **Tamil (தமிழ்) Example**  
    பயனர்: *என் அம்மாவின் மருத்துவ செலவுகளுக்காக நான் நிதி உதவியை பெற முடியுமா?*  
    AI: *ஆமாம்! **MediFund திட்டம்** குறைந்த வருமானம் உள்ளவர்களுக்கு மருத்துவ செலவுகளை உதவுகிறது. நீங்கள் **ComCare குறுகிய முதல் நடுத்தர கால உதவிக்கு (SMTA)** தகுதியானவராக இருக்கலாம். உங்கள் தகுதியை நான் சரிபார்க்க வேண்டுமா?*  

    பயனர்: *உணவு உதவித் திட்டங்கள் என்னென்ன?*  
    AI: *பல உணவு உதவித் திட்டங்கள் உள்ளன! **Meals-on-Wheels** கண்காணிக்க முடியாத வயதானவர்களுக்கு இலவச உணவை வழங்குகிறது, மற்றும் **Willing Hearts** தினசரி உணவை வழங்குகிறது. தகுதி பற்றியும் விண்ணப்பிக்க பற்றியும் மேலும் தகவல் வேண்டுமா?*  

    ---

    <example>
    User: Hi, what do you do?
    Bot: Hello! I am here to assist with Financial Support, Medical Assistance, and Food Bank Aid in Singapore. How can I help you today?
    </example>

    Context from knowledge base:
    <context>{context}</context>

    Conversation history:
    <messages>{history}</messages>

    User's current question:
    <question>{question}</question>

    ### **How to Respond**
    - Think carefully before responding. 
    - Ensure your response is **helpful, specific, and relevant**.
    - Wrap your response inside `<response>...</response>` tags.
    """

    chat_prompt = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)

    #Format the prompt with the query, context, and chat history
    messages = chat_prompt.format_messages(
        question=state["query"],
        context=state["context"],  # Retrieved documents or context
        history="\n".join([f"{msg['role']}: {msg['content']}" for msg in state["chat_history"]])
    )
    
    #Invoke Bedrock Chat
    response = bedrock_chat.invoke(messages)
    
    # Extract the response from <response> tags
    response_text = response.content.strip().split("<response>")[1].split("</response>")[0].strip()
    
    # Add the bot's response to the chat history
    state["chat_history"].append({"role": "bot", "content": response_text})
    
    # Update the state with the response
    state["response"] = response_text
    return state

#Define graph
def graph():
    #Create the graph
    workflow = StateGraph(ChatState)

    #Add nodes to the graph
    workflow.add_node("add_user_query", add_user_query_node)
    workflow.add_node("generate_response", generate_response_node)

    #Define edges (order of execution)
    workflow.add_edge("add_user_query", "generate_response")
    workflow.add_edge("generate_response", END)

    #Set entry point
    workflow.set_entry_point("add_user_query")

    #Compile the graph
    app = workflow.compile()
    return app