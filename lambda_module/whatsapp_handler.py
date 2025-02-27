import json
import os
import sys
import logging
import requests
import traceback
import boto3
import base64

current_dir = os.path.dirname(os.path.abspath(__file__))
lambda_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lambda_module')
if lambda_dir not in sys.path:
    sys.path.append(lambda_dir)


try:
    from lambda_module.multiagent_handler import app, ChatState
except ImportError:
    try:
        from multiagent_handler import app, ChatState
    except ImportError:
        import logging
        logging.error("Could not import multiagent_handler. Using fallback response.")
        

logger = logging.getLogger()
logger.setLevel(logging.INFO)

conversation_history = {}

boto3_bedrock = boto3.client('bedrock-runtime', 
                             region_name=os.environ.get("AWS_DEFAULT_REGION"),
                            aws_access_key_id=os.environ.get("BEDROCK_AWS_ACCESS_KEY_ID"),
                            aws_secret_access_key=os.environ.get("BEDROCK_AWS_SECRET_ACCESS_KEY"))


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

            message_type = message.get('type')

            if message_type == 'text':
                message_text = message['text']['body'].lower()
                logger.info(f"Received message from {phone_number}: {message_text}")
                response_text = get_claude_response(phone_number, message_text)
                logger.info(f"Sending response to {phone_number}: {response_text}")

            elif message_type == 'audio' or message_type == 'voice':
                # Handle voice message
                logger.info(f"Received voice message from {phone_number}")
                media_id = message['audio']['id']
                response_text = process_voice_message(phone_number, media_id)

            else:
                logger.info(f"Received unsupported message type: {message_type}")
                response_text = "I can process text and voice messages. Please send one of those formats."
            
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
        # Initialize the chat state with the current message
        state = ChatState()
        state.query = message_text
        
        # If there's existing conversation history, add it to the state
        for msg in conversation_history[phone_number][:-1]:  # Exclude the message we just added
            state.chat_history.append(msg)
        
        # Process the message through the workflow
        result = app.invoke(state)
        
        # Extract the response
        assistant_message = result.response
        
        # Add assistant's response to conversation history
        conversation_history[phone_number].append({"role": "assistant", "content": assistant_message})
        
        return assistant_message
    except Exception as e:
        logger.error(f"Error processing message through workflow: {str(e)}")
        logger.error(f"Exception details: {type(e).__name__}, {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return "I'm sorry, I'm having trouble processing your request right now."
    
def process_voice_message(phone_number, media_id):
    """Process voice messages by transcribing and sending to AI"""
    try:
        # 1. Get the media URL from WhatsApp
        url = f"https://graph.facebook.com/v17.0/{media_id}"
        headers = {
            'Authorization': f"Bearer {os.environ['WHATSAPP_TOKEN']}",
        }
        
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            logger.error(f"Error getting media URL: {response.text}")
            return "I couldn't process your voice message. Please try again."
        
        media_url = response.json().get('url')
        
        # 2. Download the audio data
        response = requests.get(media_url, headers=headers)
        if response.status_code != 200:
            logger.error(f"Error downloading media: {response.text}")
            return "I couldn't download your voice message. Please try again."
        
        audio_data = response.content
        
        # 3. Use Bedrock with Claude to transcribe the audio
        audio_base64 = base64.b64encode(audio_data).decode('utf-8')
        
        # Call Bedrock with Claude
        response = boto3_bedrock.invoke_model(
            modelId='anthropic.claude-3-sonnet-20240229-v1:0',
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1024,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "audio",
                                "source": {
                                    "type": "base64",
                                    "media_type": "audio/ogg",  # Adjust based on WhatsApp's format
                                    "data": audio_base64
                                }
                            },
                            {
                                "type": "text",
                                "text": "Please transcribe this audio message exactly as spoken. Maintain the original language whether it's English, Chinese, Tamil, or any other language."
                            }
                        ]
                    }
                ]
            }),
            contentType='application/json'
        )
        
        # Parse the response to get the transcription
        response_body = json.loads(response['body'].read().decode('utf-8'))
        transcribed_text = response_body['content'][0]['text']
        
        logger.info(f"Transcribed text: {transcribed_text}")
        
        # 4. Process the transcribed text with your AI
        return get_claude_response(phone_number, transcribed_text)
        
    except Exception as e:
        logger.error(f"Error processing voice message: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return "I had trouble processing your voice message. Please try again or send a text message."

        
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