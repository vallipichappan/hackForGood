import json
import os
import boto3
from datetime import datetime
import logging
import requests
import multiagent_handler

logger = logging.getLogger()
logger.setLevel(logging.INFO)

conversation_history = {}

def handle(event, context):
    # Handle webhook verification
    if event['httpMethod'] == 'GET':
        query_params = event.get('queryStringParameters', {})
        logger.info(f"GET request with params: {query_params}")
        if query_params:
            mode = query_params.get('hub.mode')
            token = query_params.get('hub.verify_token')
            challenge = query_params.get('hub.challenge')
            
            # Replace 'your_verify_token' with your chosen verification token
            verify_token = os.environ.get('VERIFY_TOKEN', '12344321')
            
            if mode == 'subscribe' and token == verify_token:
                logger.info("Webhook verified successfully")
                return {
                    'statusCode': 200,
                    'body': challenge
                }
            else:
                return {
                    'statusCode': 403,
                    'body': 'Verification failed'
                }

    # Handle incoming messages (your existing POST logic)
    if event['httpMethod'] == 'POST':
        body = json.loads(event['body'])
        logger.info(f"Received WhatsApp webhook: {json.dumps(body)}")
        # Extract message data
        if 'messages' in body['entry'][0]['changes'][0]['value']:
            message = body['entry'][0]['changes'][0]['value']['messages'][0]
            phone_number = message['from']
            message_text = message['text']['body'].lower()
            
            logger.info(f"Received message from {phone_number}: {message_text}")
            
            # if 'hello' in message_text:
            #     response_text = "👋 Hi there! How can I help you today?"
            # elif 'help' in message_text:
            #     response_text = "Here's what I can do:\n1. Say hello\n2. Tell time\n3. Help you"
            # elif 'time' in message_text:
            #     current_time = datetime.now().strftime("%H:%M:%S")
            #     response_text = f"The current time is {current_time}"
            # else:
            #     response_text = "I received your message: " + message_text
            
            # logger.info(f"Sending response to {phone_number}: {response_text}")
            
            # # Send response back to WhatsApp
            # response = send_whatsapp_message(phone_number, response_text)
            # logger.info(f"WhatsApp API response: {json.dumps(response)}")

            response_text = get_claude_response(phone_number, message_text)
            
            logger.info(f"Sending response to {phone_number}: {response_text}")
            
            # Send response back to WhatsApp
            response = send_whatsapp_message(phone_number, response_text)
            logger.info(f"WhatsApp API response: {json.dumps(response)}")
          
          
            
        return {
            'statusCode': 200,
            'body': json.dumps({'status': 'ok'})
        }

    return {
        'statusCode': 405,
        'body': 'Method not allowed'
    }

def get_claude_response(phone_number, message_text):
    if phone_number not in conversation_history:
        conversation_history[phone_number] = []
    
    # Add user message to history
    conversation_history[phone_number].append({"role": "user", "content": message_text})
    
    # Limit conversation history to last 10 messages to avoid token limits
    if len(conversation_history[phone_number]) > 10:
        conversation_history[phone_number] = conversation_history[phone_number][-10:]
    
    try:
        # Get the Jurassic-2 Ultra model ID
        # bedrock = boto3.client('bedrock', region_name='eu-west-2')  # Update region if needed
        # foundation_models = bedrock.list_foundation_models()
        # matching_model = next((model for model in foundation_models["modelSummaries"] 
        #                       if model.get("modelName") == "Jurassic-2 Ultra"), None)
        
        # if not matching_model:
        #     logger.error("Jurassic-2 Ultra model not found")
        #     return "I'm sorry, I'm having trouble accessing my language model right now."
        
        # Create a prompt that includes conversation history
        prompt = ""
        for message in conversation_history[phone_number]:
            role = message["role"]
            content = message["content"]
            if role == "user":
                prompt += f"User: {content}\n"
            else:
                prompt += f"Assistant: {content}\n"
                
        prompt += "Assistant: "
        
        # # The payload to be provided to Bedrock
        # body = json.dumps({
        #     "prompt": prompt,
        #     "maxTokens": 500,
        #     "temperature": 0.7,
        #     "topP": 1,
        # })


         # The payload w/o json
        body = {"prompt": prompt,
                "maxTokens": 500,
                "temperature": 0.7,
                "topP": 1,
                }
        
        # # Call Bedrock Runtime to invoke the model
        # bedrock_runtime = boto3.client('bedrock-runtime', region_name='eu-west-2')  # Update region if needed
        # response = bedrock_runtime.invoke_model(
        #     body=body,
        #     modelId=matching_model["modelId"],
        #     accept='application/json',
        #     contentType='application/json'
        # )

        #TO DO: integrate with agent handler
        state = multiagent_handler.trigger_workflow(body)
        return state.response

        # # Parse the response
        # response_body = json.loads(response.get('body').read())
        # assistant_message = response_body.get('completions', [{}])[0].get('data', {}).get('text', "").strip()
        
        # # Add assistant's response to conversation history
        # conversation_history[phone_number].append({"role": "assistant", "content": assistant_message})
        
        # return assistant_message
    except Exception as e:
        logger.error(f"Error getting response from Jurassic-2: {str(e)}")
        logger.error(f"Exception details: {type(e).__name__}, {str(e)}")
        return "I'm sorry, I'm having trouble processing your request right now."
      
def send_whatsapp_message(to_number, message):
    
    url = f"https://graph.facebook.com/v17.0/599525519903076/messages"
    headers = {
        'Authorization': f"Bearer {os.environ['WHATSAPP_TOKEN']}",
        'Content-Type': 'application/json'
    }
    data = {
        'messaging_product': 'whatsapp',
        'to': to_number,
        'type': 'text',
        'text': {'body': message}
    }
    
    response = requests.post(url, headers=headers, json=data)
    return response.json()