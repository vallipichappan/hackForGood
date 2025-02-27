import json
import os
import boto3
from datetime import datetime
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)


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
            
            if 'hello' in message_text:
                response_text = "👋 Hi there! How can I help you today?"
            elif 'help' in message_text:
                response_text = "Here's what I can do:\n1. Say hello\n2. Tell time\n3. Help you"
            elif 'time' in message_text:
                current_time = datetime.now().strftime("%H:%M:%S")
                response_text = f"The current time is {current_time}"
            else:
                response_text = "I received your message: " + message_text
            
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

def send_whatsapp_message(to_number, message):
    import requests
    
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